import tempfile
from pathlib import Path
import pytest
from flask import json

import config
from app import app
from agents.coding_agent import CodingAssessmentAgent, DEFAULT_CODING_CHALLENGES
from utils.database import init_db, save_analysis


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def agent():
    return CodingAssessmentAgent()


# ==============================================================================
# CodingAssessmentAgent Unit Tests
# ==============================================================================

def test_get_fallback_problem_companies(agent):
    """Test retrieving fallback problems for various companies."""
    for company in ["Google", "Amazon", "Microsoft", "TCS", "Infosys", "UnknownCorp"]:
        prob = agent.get_fallback_problem(company)
        assert isinstance(prob, dict)
        assert "title" in prob
        assert "description" in prob
        assert "constraints" in prob
        assert "starter_code" in prob
        assert "python" in prob["starter_code"]
        assert "cpp" in prob["starter_code"]
        assert "java" in prob["starter_code"]
        assert "test_cases" in prob
        assert len(prob["test_cases"]) >= 3


def test_generate_problem_with_mocked_gemini(agent, monkeypatch):
    """Test AI problem generation when Gemini responds with valid JSON."""
    mock_problem = {
        "title": "Mock Binary Search Challenge",
        "difficulty": "Easy",
        "category": "Searching",
        "company": "Amazon",
        "description": "Find target in sorted array.",
        "input_format": "nums: List[int], target: int",
        "output_format": "int",
        "constraints": ["1 <= nums.length <= 10^4"],
        "examples": [{"input": "nums = [1, 2, 3], target = 2", "output": "1", "explanation": "Found at index 1"}],
        "starter_code": {
            "python": "def search(nums, target): pass",
            "cpp": "class Solution {};",
            "java": "class Solution {}"
        },
        "test_cases": [
            {"id": 1, "input": "nums = [1, 2, 3], target = 2", "expected_output": "1", "is_hidden": False}
        ]
    }

    monkeypatch.setattr("agents.coding_agent.generate_json_response", lambda *args, **kwargs: mock_problem)
    prob = agent.generate_problem(company_name="Amazon", difficulty="Easy")

    assert prob["title"] == "Mock Binary Search Challenge"
    assert prob["difficulty"] == "Easy"
    assert "python" in prob["starter_code"]
    assert len(prob["test_cases"]) == 1


def test_generate_problem_fallback_on_gemini_error(agent, monkeypatch):
    """Test graceful fallback when Gemini raises an exception."""
    def raise_err(*args, **kwargs):
        raise RuntimeError("Gemini API rate limit or network issue")

    monkeypatch.setattr("agents.coding_agent.generate_json_response", raise_err)
    prob = agent.generate_problem(company_name="Google", difficulty="Hard")

    assert isinstance(prob, dict)
    assert "title" in prob
    assert "starter_code" in prob
    assert prob["company"] == "Google"


def test_evaluate_code_empty_submission(agent):
    """Test evaluation when candidate submits empty or whitespace code."""
    problem = agent.get_fallback_problem("Amazon")
    eval_res = agent.evaluate_code(problem=problem, language="python", code="")

    assert eval_res["correctness_score"] == 0
    assert eval_res["code_quality_score"] == 0
    assert eval_res["all_passed"] is False
    assert len(eval_res["test_case_results"]) > 0
    assert all(not tc["passed"] for tc in eval_res["test_case_results"])
    assert "empty" in eval_res["feedback"].lower()


def test_evaluate_code_mocked_gemini(agent, monkeypatch):
    """Test evaluation parsing when Gemini responds with valid evaluation JSON."""
    mock_eval = {
        "correctness_score": 95,
        "code_quality_score": 90,
        "all_passed": True,
        "test_case_results": [
            {"id": 1, "input": "nums=[2,7], target=9", "expected": "[0,1]", "actual": "[0,1]", "passed": True, "explanation": "Correct"}
        ],
        "time_complexity": "O(N)",
        "time_complexity_explanation": "Hash map single pass.",
        "space_complexity": "O(N)",
        "space_complexity_explanation": "Seen dictionary storage.",
        "optimization_suggestions": ["Good job."],
        "feedback": "Optimal solution."
    }

    monkeypatch.setattr("agents.coding_agent.generate_json_response", lambda *args, **kwargs: mock_eval)
    problem = agent.get_fallback_problem("Amazon")
    code = "def twoSum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i\n"

    result = agent.evaluate_code(problem=problem, language="python", code=code)

    assert result["correctness_score"] == 95
    assert result["all_passed"] is True
    assert result["time_complexity"] == "O(N)"
    assert len(result["test_case_results"]) == 1
    assert result["test_case_results"][0]["passed"] is True


def test_evaluate_code_offline_heuristic_fallback(agent, monkeypatch):
    """Test offline heuristic code evaluation fallback when AI API is unavailable."""
    def raise_err(*args, **kwargs):
        raise ConnectionError("No internet connection")

    monkeypatch.setattr("agents.coding_agent.generate_json_response", raise_err)
    problem = agent.get_fallback_problem("Amazon")
    code = "def twoSum(nums, target):\n    for i in range(len(nums)):\n        for j in range(i+1, len(nums)):\n            if nums[i] + nums[j] == target:\n                return [i, j]\n"

    result = agent.evaluate_code(problem=problem, language="python", code=code)

    assert result["correctness_score"] > 0
    assert "time_complexity" in result
    assert "space_complexity" in result
    assert len(result["test_case_results"]) > 0


# ==============================================================================
# API Endpoints & Interview View Integration Tests
# ==============================================================================

def test_api_coding_problem_get(client, monkeypatch):
    """Test GET /api/interview/<analysis_id>/coding-problem endpoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_placement.db"
        monkeypatch.setattr(config, "DATABASE_PATH", test_db_path)
        init_db()

        aid = "coding-test-aid-001"
        sample_results = {
            "resume_analysis": {"ats_score": 85},
            "job_match": {"match_percentage": 80},
            "interview_questions": {"hr": [], "technical": [], "behavioral": []}
        }
        save_analysis(aid, "resume.pdf", "Microsoft", "Software Engineer", sample_results)

        # GET problem for this analysis
        res = client.get(f"/api/interview/{aid}/coding-problem?difficulty=Medium")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "success"
        assert "problem" in data
        assert "title" in data["problem"]
        assert "starter_code" in data["problem"]
        assert "python" in data["problem"]["starter_code"]


def test_api_evaluate_code_post(client, monkeypatch):
    """Test POST /api/interview/evaluate-code endpoint."""
    problem = CodingAssessmentAgent().get_fallback_problem("Amazon")
    payload = {
        "problem": problem,
        "language": "python",
        "code": "def twoSum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        diff = target - num\n        if diff in seen:\n            return [seen[diff], i]\n        seen[num] = i\n    return []\n"
    }

    res = client.post(
        "/api/interview/evaluate-code",
        data=json.dumps(payload),
        content_type="application/json"
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "evaluation" in data
    assert "correctness_score" in data["evaluation"]
    assert "test_case_results" in data["evaluation"]
    assert "time_complexity" in data["evaluation"]
    assert "space_complexity" in data["evaluation"]


def test_api_evaluate_code_empty_code_post(client):
    """Test POST /api/interview/evaluate-code with empty code."""
    problem = CodingAssessmentAgent().get_fallback_problem("TCS")
    payload = {
        "problem": problem,
        "language": "python",
        "code": ""
    }

    res = client.post(
        "/api/interview/evaluate-code",
        data=json.dumps(payload),
        content_type="application/json"
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["evaluation"]["correctness_score"] == 0
    assert data["evaluation"]["all_passed"] is False


def test_interview_view_contains_coding_sandbox(client, monkeypatch):
    """Ensure the mock interview page renders the coding sandbox tab, editor, and Monaco script."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_placement.db"
        monkeypatch.setattr(config, "DATABASE_PATH", test_db_path)
        init_db()

        aid = "interview-sandbox-view-test"
        sample_results = {
            "resume_analysis": {"ats_score": 80},
            "job_match": {"match_percentage": 75},
            "interview_questions": {
                "hr": [f"HR Q{i}" for i in range(1, 6)],
                "technical": [f"Tech Q{i}" for i in range(1, 6)],
                "behavioral": [f"Beh Q{i}" for i in range(1, 6)],
            },
        }
        save_analysis(aid, "resume.pdf", "Google", "SWE", sample_results)

        res = client.get(f"/interview/{aid}")
        assert res.status_code == 200
        html = res.data.decode("utf-8")

        assert "btnModeCoding" in html
        assert "btnModeQA" in html
        assert "codingSandboxSection" in html
        assert "monacoEditorContainer" in html
        assert "codingLanguageSelect" in html
        assert "btnRunCode" in html
        assert "codingResultsPanel" in html
        assert "monaco-editor" in html

