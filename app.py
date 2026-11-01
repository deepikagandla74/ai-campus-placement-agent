import os
import uuid
import json
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename


import config
from utils.database import (
    init_db,
    get_db_connection,
    save_analysis,
    get_analysis,
    get_recent_analyses,
    delete_analysis,
    create_interview_session,
    get_interview_session,
    update_interview_session
)
from utils.pdf_reader import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_file,
    validate_resume_text,
    MAX_RESUME_TEXT_CHARS,
    ALLOWED_RESUME_EXTENSIONS,
)
from utils.gemini import (
    AIAnalysisError,
    AIRateLimitError,
    format_ai_error_for_user,
)
from utils.report_generator import generate_pdf_report
from agents.coordinator import CoordinatorAgent
from agents.interview_agent import InterviewAgent

# Configure structured application logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH


@app.errorhandler(413)
def request_entity_too_large(error):
    flash("Uploaded file exceeds the 16MB size limit. Please upload a smaller PDF.", "error")
    return redirect(url_for("index"))

# Ensure directories exist
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.REPORT_FOLDER, exist_ok=True)

# Run database schema migrations/initializations
try:
    init_db()
except Exception as db_err:
    logger.critical(f"Critical: Database initialization failed: {str(db_err)}")

# Instantiate coordination and specialized interview agents
coordinator_agent = CoordinatorAgent()
live_interview_agent = InterviewAgent()

def get_available_companies() -> list:
    """
    Loads list of companies dynamically from data/companies.json with fallback defaults.
    """
    companies_file = config.BASE_DIR / "data" / "companies.json"
    default_companies = ["Google", "Microsoft", "Amazon", "TCS", "Infosys", "Accenture", "Capgemini", "Wipro"]
    try:
        if companies_file.exists():
            with open(companies_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    return sorted(list(data.keys()))
    except Exception as e:
        logger.warning(f"Could not load dynamic companies from {companies_file}: {e}")
    return default_companies


@app.route("/api/health")
@app.route("/health")
def health_check():
    """
    Health check endpoint verifying application uptime and database connectivity.
    """
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        db_status = "connected"
    except Exception as db_err:
        logger.error(f"Healthcheck database error: {str(db_err)}")
        db_status = f"unhealthy: {str(db_err)}"

    status_code = 200 if db_status == "connected" else 503
    return (
        jsonify(
            {
                "status": "healthy" if status_code == 200 else "degraded",
                "version": config.__version__,
                "database": db_status,
            }
        ),
        status_code,
    )

@app.route("/")
def index() -> str:
    """
    Renders the placement landing page containing the configuration forms.
    """
    companies_list = get_available_companies()
    return render_template("index.html", companies=companies_list)


@app.route("/api/company/<company_name>")
def get_company_profile(company_name: str):
    """
    Returns company hiring details from data/companies.json for the preview explorer modal.
    """
    companies_file = config.BASE_DIR / "data" / "companies.json"
    try:
        if companies_file.exists():
            with open(companies_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if company_name in data:
                    return jsonify({"success": True, "company": company_name, "details": data[company_name]})
    except Exception as e:
        logger.error(f"Error fetching company details for {company_name}: {e}")
    return jsonify({"success": False, "error": f"Profile for '{company_name}' not found."}), 404

@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Handles PDF resume uploads, processes files, calls coordinator,
    persists result states, and redirects to candidate dashboards.
    """
    try:
        pasted_text = request.form.get("resume_text", "").strip()
        uploaded_file = request.files.get("resume")
        file_uuid = str(uuid.uuid4())
        resume_filename = "pasted_resume.txt"

        if pasted_text:
            is_valid, validation_msg = validate_resume_text(pasted_text)
            if not is_valid:
                flash(validation_msg, "error")
                return redirect(url_for("index"))
            extracted_resume_text = pasted_text[:MAX_RESUME_TEXT_CHARS]
            resume_filename = "Pasted_Resume.txt"
        elif uploaded_file and uploaded_file.filename != "":
            filename_lower = uploaded_file.filename.lower()
            if not any(filename_lower.endswith(ext) for ext in ALLOWED_RESUME_EXTENSIONS):
                flash(
                    "Invalid file format. Only PDF (.pdf) and Word (.docx) resumes are supported.",
                    "error",
                )
                return redirect(url_for("index"))
            resume_filename = uploaded_file.filename
            safe_name = secure_filename(f"{file_uuid}_{uploaded_file.filename}")
            saved_file_path = os.path.join(config.UPLOAD_FOLDER, safe_name)
            uploaded_file.save(saved_file_path)
            logger.info(f"Uploaded resume saved locally at: {saved_file_path}")
            extracted_resume_text = extract_text_from_file(saved_file_path)
        else:
            flash(
                "Please upload a PDF resume or paste your resume text.",
                "error",
            )
            return redirect(url_for("index"))

        selected_company = request.form.get("company", "General").strip()
        job_description = request.form.get("job_description", "").strip()
        if len(job_description) > 15000:
            job_description = job_description[:15000]

        # Execute coordinated multi-agent analysis via single Gemini call
        analysis_payload = coordinator_agent.analyze(
            resume_text=extracted_resume_text,
            job_description=job_description,
            company_name=selected_company
        )

        # Store analysis result in SQLite database
        save_analysis(
            analysis_id=file_uuid,
            resume_filename=resume_filename,
            company_name=selected_company,
            job_description=job_description,
            results_dict=analysis_payload
        )

        # Redirect user directly to their new placement analysis dashboard
        return redirect(url_for("dashboard", analysis_id=file_uuid))

    except AIAnalysisError as aie:
        logger.warning(f"AIAnalysisError in analysis workflow: {str(aie)}")
        flash(aie.user_friendly_message, "error")
        return redirect(url_for("index"))
    except ValueError as ve:
        logger.warning(f"Validation error in analysis workflow: {str(ve)}")
        flash(str(ve), "error")
        return redirect(url_for("index"))
    except Exception as e:
        logger.error(f"Analysis workflow crashed: {str(e)}")
        friendly_message = format_ai_error_for_user(e)
        flash(friendly_message, "error")
        return redirect(url_for("index"))

@app.route("/dashboard/<analysis_id>")
def dashboard(analysis_id: str) -> str:
    """
    Loads and renders the candidate evaluation dashboard.
    """
    analysis_record = get_analysis(analysis_id)
    if not analysis_record:
        flash("The requested placement analysis report could not be found.", "error")
        return redirect(url_for("index"))

    return render_template(
        "dashboard.html",
        analysis=analysis_record,
        analysis_id=analysis_id
    )

@app.route("/interview/<analysis_id>")
def interview(analysis_id: str) -> str:
    """
    Bootstraps or loads an existing interactive mock interview session.
    Supports optional ?round=HR|Technical|Behavioral filter to practice focused rounds.
    """
    analysis_record = get_analysis(analysis_id)
    if not analysis_record:
        flash("Cannot initialize mock interview. Parent analysis not found.", "error")
        return redirect(url_for("index"))

    raw_round = request.args.get("round", "").strip().lower()
    round_map = {"hr": "HR", "technical": "Technical", "behavioral": "Behavioral"}
    active_round = round_map.get(raw_round, "All")

    session_id = f"{analysis_id}_{raw_round}" if active_round in round_map.values() else analysis_id

    # Load or initialize the interview session from DB
    interview_session = get_interview_session(session_id)

    if not interview_session:
        # Extract questions generated by Coordinator Agent
        coordinator_questions = analysis_record["results"].get("interview_questions", {})
        
        flat_questions_list = []
        q_idx = 0

        categories_to_include = (
            [active_round] if active_round in round_map.values() else ["HR", "Technical", "Behavioral"]
        )
        
        for category in categories_to_include:
            key = category.lower()
            for question_text in coordinator_questions.get(key, []):
                flat_questions_list.append({"index": q_idx, "type": category, "question": question_text})
                q_idx += 1

        # Save new session into SQLite DB
        create_interview_session(
            interview_id=session_id,
            analysis_id=analysis_id,
            questions_list=flat_questions_list
        )
        interview_session = get_interview_session(session_id)

    return render_template(
        "interview.html",
        interview=interview_session,
        analysis_id=analysis_id,
        session_id=session_id,
        active_round=active_round,
        company_name=analysis_record.get("company_name", "General"),
    )

@app.route("/interview/<analysis_id>/submit", methods=["POST"])
def submit_interview_answer(analysis_id: str):
    """
    Endpoint that evaluates a candidate response dynamically and updates session progress.
    """
    try:
        post_data = request.get_json() or {}
        session_id = (
            post_data.get("session_id")
            or request.args.get("session_id")
            or (f"{analysis_id}_{request.args.get('round', '').lower()}" if request.args.get('round') else None)
            or analysis_id
        )

        session = get_interview_session(session_id)
        if not session and session_id != analysis_id:
            session_id = analysis_id
            session = get_interview_session(session_id)

        if not session:
            return jsonify({"error": "Mock interview session was not found."}), 404

        # Read JSON POST payloads
        candidate_response = post_data.get("answer", "").strip()
        question_index = int(post_data.get("question_index", 0))

        questions_list = session["questions"]
        answers_list = session["answers"]

        if question_index < 0 or question_index >= len(questions_list):
            return jsonify({"error": "The requested question index is out of bounds."}), 400

        target_question = questions_list[question_index]

        # Call InterviewAgent to dynamically evaluate response accuracy, metrics, and suggestions
        evaluation_results = live_interview_agent.evaluate_answer(
            question_type=target_question["type"],
            question=target_question["question"],
            answer=candidate_response
        )

        # Structure response details
        response_record = {
            "question_index": question_index,
            "type": target_question["type"],
            "question": target_question["question"],
            "answer": candidate_response,
            "evaluation": evaluation_results
        }

        # Protection against duplicate submission attempts
        is_replaced = False
        for idx, past_ans in enumerate(answers_list):
            if past_ans["question_index"] == question_index:
                answers_list[idx] = response_record
                is_replaced = True
                break
        if not is_replaced:
            answers_list.append(response_record)

        # Calculate progress parameters
        next_question_index = question_index + 1
        is_completed = next_question_index >= len(questions_list)

        # Update session logs in database
        update_interview_session(
            interview_id=session_id,
            current_question_index=next_question_index if not is_completed else question_index,
            answers_list=answers_list,
            completed=is_completed
        )

        result_payload = {
            "evaluation": evaluation_results,
            "next_index": next_question_index,
            "completed": is_completed
        }

        if is_completed:
            result_payload["summary"] = live_interview_agent.calculate_session_summary(answers_list)
        else:
            result_payload["next_question"] = questions_list[next_question_index]

        return jsonify(result_payload)

    except Exception as e:
        logger.error(f"Failed to process answer submission: {str(e)}")
        return jsonify({"error": f"Internal process error evaluating response: {str(e)}"}), 500


@app.route("/interview/<analysis_id>/export")
def export_interview_json(analysis_id: str):
    """
    Exports the mock interview Q&A transcript and dynamic evaluations as a JSON download.
    """
    session_id = (
        request.args.get("session_id")
        or (f"{analysis_id}_{request.args.get('round', '').lower()}" if request.args.get('round') else None)
        or analysis_id
    )
    session = get_interview_session(session_id)
    if not session and session_id != analysis_id:
        session_id = analysis_id
        session = get_interview_session(session_id)

    analysis_record = get_analysis(analysis_id)
    if not session:
        flash("Interview session not found.", "error")
        return redirect(url_for("index"))

    company_name = analysis_record.get("company_name", "General") if analysis_record else "General"
    answers_recorded = session.get("answers", [])
    session_summary = live_interview_agent.calculate_session_summary(answers_recorded) if answers_recorded else {}

    export_data = {
        "analysis_id": analysis_id,
        "company_name": company_name,
        "completed": bool(session.get("completed", 0)),
        "total_questions": len(session.get("questions", [])),
        "answers_recorded": len(answers_recorded),
        "session_summary": session_summary,
        "transcript": answers_recorded,
    }

    response = jsonify(export_data)
    safe_company = "".join(c for c in company_name if c.isalnum() or c in ("-", "_"))
    response.headers["Content-Disposition"] = (
        f"attachment; filename=Mock_Interview_{safe_company}_{analysis_id[:8]}.json"
    )
    return response


@app.route("/certificate/<analysis_id>")
def certificate(analysis_id: str):
    """
    Renders printable placement readiness completion certificate.
    """
    analysis_record = get_analysis(analysis_id)
    if not analysis_record:
        flash("The requested placement analysis report could not be found.", "error")
        return redirect(url_for("index"))

    return render_template(
        "certificate.html",
        analysis=analysis_record,
        analysis_id=analysis_id,
    )

@app.route("/download/<analysis_id>")
def download_pdf_report(analysis_id: str):
    """
    Compiles placement metrics into a ReportLab PDF and downloads the file.
    """
    try:
        analysis_record = get_analysis(analysis_id)
        if not analysis_record:
            flash("Cannot generate PDF. Placement record not found.", "error")
            return redirect(url_for("index"))

        # Check if file has already been generated
        pdf_output_name = f"Placement_Report_{analysis_id}.pdf"
        pdf_full_path = os.path.join(config.REPORT_FOLDER, pdf_output_name)

        if not os.path.exists(pdf_full_path):
            generate_pdf_report(
                analysis_data=analysis_record,
                output_path=pdf_full_path
            )

        return send_file(
            pdf_full_path,
            as_attachment=True,
            download_name=f"Placement_Readiness_Report_{analysis_record['company_name']}.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        logger.error(f"Failed to generate and serve PDF report: {str(e)}")
        flash(f"Error compiling report file: {str(e)}", "error")
        return redirect(url_for("dashboard", analysis_id=analysis_id))

@app.route("/api/analyses/recent", methods=["GET"])
def api_recent_analyses():
    """
    Returns a list of recent placement analyses ordered by timestamp descending.
    """
    try:
        limit = request.args.get("limit", default=10, type=int)
        analyses = get_recent_analyses(limit=limit)
        return jsonify({
            "status": "success",
            "count": len(analyses),
            "analyses": analyses
        }), 200
    except Exception as e:
        logger.error(f"Error fetching recent analyses: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve recent analyses."
        }), 500

@app.route("/api/analysis/<analysis_id>", methods=["DELETE"])
def api_delete_analysis(analysis_id: str):
    """
    Deletes an analysis session and related mock interview records.
    """
    try:
        deleted = delete_analysis(analysis_id)
        if not deleted:
            return jsonify({
                "status": "error",
                "message": f"Analysis with ID {analysis_id} not found."
            }), 404
        return jsonify({
            "status": "success",
            "message": f"Analysis {analysis_id} deleted successfully."
        }), 200
    except Exception as e:
        logger.error(f"Error deleting analysis {analysis_id}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Failed to delete analysis record."
        }), 500

if __name__ == "__main__":
    # Boot Flask server locally on default port 5000
    app.run(debug=True, port=5000)
