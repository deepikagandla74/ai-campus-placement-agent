"""
Tests for Asynchronous Agent Pipeline & Real-Time Progress Streaming
"""

import json
import time
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import pytest

import config
from app import app
from utils.database import init_db, get_analysis
from utils.async_pipeline import (
    AnalysisTask,
    create_analysis_task,
    get_analysis_task,
    start_async_analysis,
    _run_analysis_pipeline,
)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


SAMPLE_RESUME_TEXT = (
    "John Doe\n"
    "Education: B.Tech Computer Science, GPA: 8.8\n"
    "Skills: Python, React, Docker, SQL, Git, REST APIs\n"
    "Experience: Software Engineer Intern at Tech Corp\n"
    "- Developed microservices using Python and Flask\n"
    "- Built responsive UI components with React\n"
    "Projects: E-Commerce Web App with full checkout flow\n"
)

SAMPLE_ANALYSIS_PAYLOAD = {
    "resume_analysis": {"ats_score": 88, "strengths": ["Clean layout"], "improvements": []},
    "job_match": {"match_percentage": 85, "matching_skills": ["Python"], "missing_skills": []},
    "skill_gap": [],
    "learning_roadmap": [],
    "interview_questions": {"hr": [], "technical": [], "behavioral": []},
    "overall_recommendation_summary": "Strong candidate."
}


def test_analysis_task_lifecycle():
    task = create_analysis_task(company_name="Google", resume_filename="test_resume.pdf")
    assert task.task_id is not None
    assert task.company_name == "Google"
    assert task.resume_filename == "test_resume.pdf"
    assert task.status == "queued"
    assert task.progress == 0
    assert len(task.get_milestones()) == 0

    # Emit milestone
    task.emit(step="step1", agent="Resume Parser", message="Parsing resume...", progress=15)
    assert task.current_step == "step1"
    assert task.progress == 15
    assert task.status == "in_progress"
    assert len(task.get_milestones()) == 1

    # Check to_dict
    task_dict = task.to_dict()
    assert task_dict["task_id"] == task.task_id
    assert task_dict["company_name"] == "Google"
    assert task_dict["progress"] == 15
    assert len(task_dict["milestones"]) == 1

    # Emit completion
    task.emit(
        step="completed",
        agent="CoordinatorAgent",
        message="Done!",
        progress=100,
        status="completed",
        extra={"analysis_id": "aid-123", "redirect_url": "/dashboard/aid-123"}
    )
    assert task.status == "completed"
    assert task.analysis_id == "aid-123"
    assert task.redirect_url == "/dashboard/aid-123"


def test_analysis_task_error_state():
    task = AnalysisTask("task-err", "Amazon", "resume.pdf")
    task.emit(
        step="error",
        agent="CoordinatorAgent",
        message="Gemini quota exceeded",
        progress=0,
        status="error"
    )
    assert task.status == "error"
    assert task.error_message == "Gemini quota exceeded"


def test_get_analysis_task_retrieval():
    task = create_analysis_task("Microsoft", "my_resume.docx")
    retrieved = get_analysis_task(task.task_id)
    assert retrieved is task
    assert get_analysis_task("nonexistent-id-999") is None


def test_api_analysis_start_success(client):
    response = client.post(
        "/api/analysis/start",
        data={
            "resume_text": SAMPLE_RESUME_TEXT,
            "company": "Google",
            "job_description": "Software Engineering Role"
        }
    )
    assert response.status_code == 202
    data = response.get_json()
    assert data["success"] is True
    assert data["status"] == "started"
    assert "task_id" in data
    assert "stream_url" in data
    assert "status_url" in data
    assert data["stream_url"] == f"/api/analysis/stream/{data['task_id']}"
    assert data["status_url"] == f"/api/analysis/status/{data['task_id']}"


def test_api_analysis_start_missing_input(client):
    response = client.post("/api/analysis/start", data={})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Please upload a PDF resume or paste your resume text." in data["error"]


def test_api_analysis_start_invalid_file(client):
    from io import BytesIO
    fake_file = (BytesIO(b"malicious executable"), "test.exe")
    response = client.post(
        "/api/analysis/start",
        data={"resume": fake_file, "company": "TCS"},
        content_type="multipart/form-data"
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Invalid file format" in data["error"]


def test_api_analysis_stream_not_found(client):
    response = client.get("/api/analysis/stream/nonexistent-task-id")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False


def test_api_analysis_stream_milestones(client):
    task = create_analysis_task("Apple", "resume.pdf")
    task.emit(step="step1", agent="Resume Parser", message="Parsed", progress=15)
    task.emit(
        step="completed",
        agent="CoordinatorAgent",
        message="Complete",
        progress=100,
        status="completed",
        extra={"analysis_id": "apple-123", "redirect_url": "/dashboard/apple-123"}
    )

    response = client.get(f"/api/analysis/stream/{task.task_id}")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["Content-Type"]

    raw_data = response.data.decode("utf-8")
    assert "data: " in raw_data
    lines = [line for line in raw_data.split("\n") if line.startswith("data: ")]
    assert len(lines) >= 2

    first_event = json.loads(lines[0].replace("data: ", ""))
    assert first_event["step"] == "step1"
    assert first_event["progress"] == 15

    last_event = json.loads(lines[1].replace("data: ", ""))
    assert last_event["status"] == "completed"
    assert last_event["analysis_id"] == "apple-123"


def test_api_analysis_status_endpoint(client):
    task = create_analysis_task("Netflix", "resume.pdf")
    task.emit(step="step2", agent="ResumeAgent", message="Analyzing ATS", progress=30)

    # Valid task status query
    response = client.get(f"/api/analysis/status/{task.task_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["company_name"] == "Netflix"
    assert data["progress"] == 30
    assert len(data["milestones"]) == 1

    # Non-existent task status query
    not_found = client.get("/api/analysis/status/unknown-task-id")
    assert not_found.status_code == 404


def test_analyze_route_async_mode(client):
    response = client.post(
        "/analyze?async=true",
        data={
            "resume_text": SAMPLE_RESUME_TEXT,
            "company": "Amazon",
            "job_description": "Cloud Engineer"
        }
    )
    assert response.status_code == 202
    data = response.get_json()
    assert data["success"] is True
    assert data["status"] == "started"
    assert "stream_url" in data
    assert "task_id" in data


def test_run_analysis_pipeline_worker_success(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_async.db"
        monkeypatch.setattr(config, "DATABASE_PATH", test_db_path)
        init_db()

        mock_coordinator = MagicMock()
        mock_coordinator.analyze.return_value = SAMPLE_ANALYSIS_PAYLOAD

        task = create_analysis_task("Meta", "resume.pdf")
        aid = "meta-async-123"

        _run_analysis_pipeline(
            task=task,
            coordinator_agent=mock_coordinator,
            save_analysis_func=lambda **kwargs: None,
            resume_text=SAMPLE_RESUME_TEXT,
            job_description="AI Engineer",
            company_name="Meta",
            resume_filename="resume.pdf",
            analysis_id=aid
        )

        assert task.status == "completed"
        assert task.progress == 100
        assert task.analysis_id == aid
        assert task.redirect_url == f"/dashboard/{aid}"

        milestone_steps = [m["step"] for m in task.get_milestones()]
        assert "step1" in milestone_steps
        assert "step2" in milestone_steps
        assert "step3" in milestone_steps
        assert "step4" in milestone_steps
        assert "step5" in milestone_steps
        assert "step6" in milestone_steps
        assert "completed" in milestone_steps


def test_run_analysis_pipeline_worker_error():
    mock_coordinator = MagicMock()
    mock_coordinator.analyze.side_effect = RuntimeError("Simulated API failure")

    task = create_analysis_task("Google", "resume.pdf")
    _run_analysis_pipeline(
        task=task,
        coordinator_agent=mock_coordinator,
        save_analysis_func=lambda **kwargs: None,
        resume_text=SAMPLE_RESUME_TEXT,
        job_description="",
        company_name="Google",
        resume_filename="resume.pdf",
        analysis_id="err-123"
    )

    assert task.status == "error"
    assert task.error_message is not None
    assert "Simulated API failure" in task.milestones[-1]["extra"]["error_details"]

