"""
Comprehensive unit and integration test suite for:
- Multi-Version Resume Comparison & Longitudinal Progress Tracker
- Database candidate profile and version indexing (student_id, version_number)
- Delta analysis engine calculating ATS score improvements and newly matched keywords
- Longitudinal Chart.js trend series serialization
- Side-by-side diff comparison endpoint and modal rendering
"""

import tempfile
from pathlib import Path
import pytest
from flask import json

import config
from app import app
from utils.database import (
    init_db,
    save_analysis,
    get_analysis,
    get_student_versions,
    get_previous_analysis
)
from utils.progress_tracker import (
    calculate_version_delta,
    build_longitudinal_series,
    generate_side_by_side_diff
)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def test_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_progress.db"
        monkeypatch.setattr(config, "DATABASE_PATH", db_path)
        init_db()
        yield db_path


# ==============================================================================
# Database Student ID & Version Indexing Tests
# ==============================================================================

def test_database_version_indexing_auto_increment(test_db):
    """Test that saving multiple analyses for the same student increments version numbers."""
    student = "student_alex_01"
    
    # Save version 1
    save_analysis(
        analysis_id="aid-v1",
        resume_filename="resume_v1.pdf",
        company_name="Google",
        job_description="SWE Role",
        results_dict={"resume_analysis": {"ats_score": 65}, "job_match": {"match_percentage": 60}},
        student_id=student
    )

    # Save version 2
    save_analysis(
        analysis_id="aid-v2",
        resume_filename="resume_v2.pdf",
        company_name="Google",
        job_description="SWE Role",
        results_dict={"resume_analysis": {"ats_score": 80}, "job_match": {"match_percentage": 75}},
        student_id=student
    )

    # Save version 3
    save_analysis(
        analysis_id="aid-v3",
        resume_filename="resume_v3.pdf",
        company_name="Google",
        job_description="SWE Role",
        results_dict={"resume_analysis": {"ats_score": 92}, "job_match": {"match_percentage": 88}},
        student_id=student
    )

    versions = get_student_versions(student)
    assert len(versions) == 3
    assert [v["version_number"] for v in versions] == [1, 2, 3]
    assert [v["ats_score"] for v in versions] == [65, 80, 92]


def test_database_get_previous_analysis(test_db):
    """Test fetching the preceding iteration for delta calculations."""
    student = "student_maya"
    for i in range(1, 4):
        save_analysis(
            analysis_id=f"maya-v{i}",
            resume_filename=f"maya_v{i}.pdf",
            company_name="Amazon",
            job_description="SDE",
            results_dict={"resume_analysis": {"ats_score": 50 + i * 10}},
            student_id=student
        )

    # Preceding version for v3 should be v2
    prev_v3 = get_previous_analysis(student, current_version=3)
    assert prev_v3 is not None
    assert prev_v3["version_number"] == 2
    assert prev_v3["id"] == "maya-v2"

    # Preceding version for v1 should be None (baseline)
    prev_v1 = get_previous_analysis(student, current_version=1)
    assert prev_v1 is None


# ==============================================================================
# Delta Analysis Engine Unit Tests
# ==============================================================================

def test_calculate_version_delta_baseline_version():
    """Test delta calculation when no previous version exists (baseline)."""
    rec_v1 = {
        "id": "v1-uuid",
        "version_number": 1,
        "results": {
            "resume_analysis": {
                "ats_score": 60,
                "keywords_found": ["Python", "Git"],
                "keywords_missing": ["Docker", "Kubernetes"]
            },
            "job_match": {
                "match_percentage": 55,
                "matched_skills": ["Python"]
            },
            "skill_gap": [{"skill": "Containers & Docker"}, {"skill": "Cloud Deployment"}]
        }
    }

    delta = calculate_version_delta(current_record=rec_v1, previous_record=None)
    assert delta["has_previous"] is False
    assert delta["ats_delta"] == 0
    assert delta["match_delta"] == 0
    assert delta["ats_current"] == 60
    assert "Baseline" in delta["badge_text"]
    assert len(delta["remaining_skill_gaps"]) == 2


def test_calculate_version_delta_with_improvements():
    """Test delta calculation when ATS score, keywords, and skill gaps improve."""
    rec_v1 = {
        "id": "v1-uuid",
        "version_number": 1,
        "results": {
            "resume_analysis": {
                "ats_score": 65,
                "keywords_found": ["Python", "SQL"],
                "keywords_missing": ["Docker", "CI/CD", "AWS"]
            },
            "job_match": {
                "match_percentage": 58,
                "matched_skills": ["Python", "SQL"]
            },
            "skill_gap": [{"skill": "Docker & Containers"}, {"skill": "AWS Cloud"}]
        }
    }

    rec_v2 = {
        "id": "v2-uuid",
        "version_number": 2,
        "results": {
            "resume_analysis": {
                "ats_score": 82,
                "keywords_found": ["Python", "SQL", "Docker", "CI/CD"],
                "keywords_missing": ["AWS"]
            },
            "job_match": {
                "match_percentage": 75,
                "matched_skills": ["Python", "SQL", "Docker & Containers"]
            },
            "skill_gap": [{"skill": "AWS Cloud"}]
        }
    }

    delta = calculate_version_delta(current_record=rec_v2, previous_record=rec_v1)
    assert delta["has_previous"] is True
    assert delta["ats_delta"] == 17  # 82 - 65
    assert delta["match_delta"] == 17  # 75 - 58
    assert "Docker" in delta["newly_matched_keywords"] or "CI/CD" in delta["newly_matched_keywords"]
    assert "Docker & Containers" in delta["resolved_skill_gaps"]
    assert "AWS Cloud" in delta["remaining_skill_gaps"]
    assert "Significant Improvement" in delta["badge_text"]


def test_build_longitudinal_series_for_chartjs():
    """Test data packaging for Chart.js longitudinal trend display."""
    versions = [
        {"version_number": 1, "created_at": "2026-11-01 10:00:00", "ats_score": 60, "match_percentage": 50, "results": {"skill_gap": [1, 2, 3]}},
        {"version_number": 2, "created_at": "2026-11-05 14:00:00", "ats_score": 75, "match_percentage": 68, "results": {"skill_gap": [1]}},
        {"version_number": 3, "created_at": "2026-11-10 16:00:00", "ats_score": 88, "match_percentage": 85, "results": {"skill_gap": []}},
    ]

    series = build_longitudinal_series(versions)
    assert series["labels"] == ["v1", "v2", "v3"]
    assert series["ats_scores"] == [60, 75, 88]
    assert series["match_scores"] == [50, 68, 85]
    assert series["gap_counts"] == [3, 1, 0]
    assert series["total_versions"] == 3


def test_generate_side_by_side_diff():
    """Test generating side-by-side modal diff structure between two versions."""
    rec_a = {
        "id": "id-a",
        "version_number": 1,
        "resume_filename": "res_v1.pdf",
        "results": {
            "resume_analysis": {"ats_score": 70, "keywords_found": ["Java"], "keywords_missing": ["Spring"]},
            "job_match": {"match_percentage": 65},
            "skill_gap": [{"skill": "Spring Boot"}]
        }
    }
    rec_b = {
        "id": "id-b",
        "version_number": 2,
        "resume_filename": "res_v2.pdf",
        "results": {
            "resume_analysis": {"ats_score": 85, "keywords_found": ["Java", "Spring"], "keywords_missing": []},
            "job_match": {"match_percentage": 80, "matched_skills": ["Spring Boot"]},
            "skill_gap": []
        }
    }

    diff = generate_side_by_side_diff(rec_a, rec_b)
    assert "version_a" in diff
    assert "version_b" in diff
    assert diff["version_a"]["ats_score"] == 70
    assert diff["version_b"]["ats_score"] == 85
    assert diff["delta"]["ats_delta"] == 15
    assert "Spring" in diff["delta"]["newly_matched_keywords"]


# ==============================================================================
# API Endpoints & Dashboard Template Integration Tests
# ==============================================================================

def test_api_student_progress_endpoint(client, test_db):
    """Test GET /api/progress/<student_id> endpoint."""
    student_id = "test_student_prog"
    save_analysis(
        analysis_id="prog-1",
        resume_filename="r1.pdf",
        company_name="Google",
        job_description="Dev",
        results_dict={"resume_analysis": {"ats_score": 72}, "job_match": {"match_percentage": 68}},
        student_id=student_id
    )
    save_analysis(
        analysis_id="prog-2",
        resume_filename="r2.pdf",
        company_name="Google",
        job_description="Dev",
        results_dict={"resume_analysis": {"ats_score": 86}, "job_match": {"match_percentage": 82}},
        student_id=student_id
    )

    res = client.get(f"/api/progress/{student_id}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["student_id"] == student_id
    assert data["total_versions"] == 2
    assert "trend_series" in data
    assert data["trend_series"]["ats_scores"] == [72, 86]


def test_api_progress_diff_endpoint(client, test_db):
    """Test GET /api/progress/diff/<id_a>/<id_b> endpoint."""
    save_analysis(
        analysis_id="diff-a",
        resume_filename="v1.pdf",
        company_name="TCS",
        job_description="SE",
        results_dict={"resume_analysis": {"ats_score": 60, "keywords_found": ["C++"]}},
        student_id="student_diff"
    )
    save_analysis(
        analysis_id="diff-b",
        resume_filename="v2.pdf",
        company_name="TCS",
        job_description="SE",
        results_dict={"resume_analysis": {"ats_score": 78, "keywords_found": ["C++", "STL"]}},
        student_id="student_diff"
    )

    res = client.get("/api/progress/diff/diff-a/diff-b")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "diff" in data
    assert data["diff"]["delta"]["ats_delta"] == 18


def test_dashboard_renders_progress_tracker_and_diff_modal(client, test_db):
    """Verify that dashboard.html renders the longitudinal tracker, trend canvas, and diff modal."""
    student_id = "dash_student_tracker"
    save_analysis(
        analysis_id="dash-v1",
        resume_filename="cv_v1.pdf",
        company_name="Microsoft",
        job_description="Cloud Engineer",
        results_dict={
            "resume_analysis": {"ats_score": 68, "strengths": ["Clean layout"], "keywords_found": ["Azure"]},
            "job_match": {"match_percentage": 64},
            "skill_gap": [{"skill": "Terraform"}],
            "learning_roadmap": []
        },
        student_id=student_id
    )
    save_analysis(
        analysis_id="dash-v2",
        resume_filename="cv_v2.pdf",
        company_name="Microsoft",
        job_description="Cloud Engineer",
        results_dict={
            "resume_analysis": {"ats_score": 84, "strengths": ["Added IaC projects"], "keywords_found": ["Azure", "Terraform"]},
            "job_match": {"match_percentage": 80, "matched_skills": ["Terraform"]},
            "skill_gap": [],
            "learning_roadmap": []
        },
        student_id=student_id
    )

    res = client.get("/dashboard/dash-v2")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    assert "progressTrackerCard" in html
    assert "progressTrendChart" in html
    assert "chart.js" in html.lower()
    assert "versionDiffModal" in html
    assert "Side-by-Side Diff" in html
    assert "Iteration Versions" in html
    assert "+16" in html  # 84 - 68 ATS delta
    assert "Newly Matched Keywords" in html

