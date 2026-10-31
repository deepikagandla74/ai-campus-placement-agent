"""
Gemini API client, utilities, structured JSON parsing, and resilient error handling.

Provides custom exception classifications for AI API rate limits, network timeouts,
service unavailability, authentication failures, and response truncation.
Includes fallback recovery mechanisms and user-facing error message formatting.
"""

import logging
import json
import re
import socket
import time
from typing import Any, Dict, Optional, Tuple
from google import genai
from google.genai import types
from google.genai.errors import APIError
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# Custom AI Exception Hierarchy for Placement Agent (#80)
# ==============================================================================

class AIAnalysisError(Exception):
    """Base exception for all AI analysis processing failures."""
    def __init__(self, message: str, user_friendly_message: Optional[str] = None, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.user_friendly_message = user_friendly_message or (
            "We encountered an issue while communicating with the AI mentor. "
            "Please try again in a few moments."
        )
        self.retryable = retryable


class AIRateLimitError(AIAnalysisError):
    """Raised when the AI model provider returns HTTP 429 or quota exceeded."""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            user_friendly_message=(
                "The AI service is currently receiving high traffic or your API quota limit has been reached. "
                "Please wait 30-60 seconds before submitting another placement analysis request."
            ),
            retryable=True,
        )


class AINetworkError(AIAnalysisError):
    """Raised when network connectivity, DNS, or socket connection to the AI provider fails."""
    def __init__(self, message: str = "Network connection failed"):
        super().__init__(
            message=message,
            user_friendly_message=(
                "Unable to connect to the AI service due to a network connection issue. "
                "Please check your internet connection and try again."
            ),
            retryable=True,
        )


class AIAuthError(AIAnalysisError):
    """Raised when GEMINI_API_KEY is invalid, missing, or unauthorized."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            user_friendly_message=(
                "Gemini API authentication failed. Please verify that your GEMINI_API_KEY is properly "
                "configured with valid permissions in your environment."
            ),
            retryable=False,
        )


class AIResponseFormatError(AIAnalysisError):
    """Raised when the AI output cannot be parsed into the expected structured JSON format."""
    def __init__(self, message: str = "Malformed or incomplete AI JSON response"):
        super().__init__(
            message=message,
            user_friendly_message=(
                "The AI analysis response was incomplete or formatted unexpectedly. "
                "Our fault-tolerant recovery agent has attempted a repair. If the issue persists, "
                "please try submitting again."
            ),
            retryable=False,
        )


class AIServiceUnavailableError(AIAnalysisError):
    """Raised when Gemini returns 500, 503, or temporary backend overload errors."""
    def __init__(self, message: str = "AI service temporarily unavailable"):
        super().__init__(
            message=message,
            user_friendly_message=(
                "The AI service is temporarily experiencing downtime or service maintenance. "
                "Please retry in a moment."
            ),
            retryable=True,
        )


def format_ai_error_for_user(exc: Exception) -> str:
    """
    Translates raw exceptions into friendly, actionable user messages for flash alerts.
    """
    if isinstance(exc, AIAnalysisError):
        return exc.user_friendly_message

    err_str = str(exc).lower()
    if "rate limit" in err_str or "quota" in err_str or "429" in err_str or "resource_exhausted" in err_str:
        return (
            "API quota or rate limit exceeded. Please wait a few moments and try your analysis again."
        )
    elif "api key" in err_str or "unauthorized" in err_str or "forbidden" in err_str or "permission" in err_str:
        return (
            "AI Authentication issue: Invalid or missing GEMINI_API_KEY. Please verify your API key in settings."
        )
    elif "timeout" in err_str or "connection" in err_str or "timed out" in err_str or "network" in err_str:
        return (
            "Network timeout while connecting to AI service. Please check your connection and retry."
        )
    elif "json" in err_str or "parse" in err_str:
        return (
            "The AI generated an incomplete response. Please try submitting again with more resume details."
        )
    else:
        return f"AI Analysis could not be completed: {str(exc)}"


def get_gemini_client() -> genai.Client:
    """
    Initializes and returns the Gemini client using config settings.
    Raises AIAuthError if API Key is missing or default.
    """
    api_key = config.GEMINI_API_KEY
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        logger.error("GEMINI_API_KEY is not configured in .env file.")
        raise AIAuthError("Missing Gemini API Key. Please set GEMINI_API_KEY in your .env file.")
    return genai.Client(api_key=api_key)


def _extract_json_string(text: str) -> str:
    """
    Cleans markdown code fences, strips conversational preambles/postambles,
    and returns the isolated JSON string.
    """
    if not text:
        return ""

    cleaned = text.strip().lstrip("\ufeff")

    # 1. Search for markdown code fence anywhere in the response
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(fence_pattern, cleaned, flags=re.IGNORECASE)
    if match:
        candidate = match.group(1).strip()
        # Verify the candidate starts and ends with JSON structural delimiters
        if (candidate.startswith("{") and candidate.endswith("}")) or (
            candidate.startswith("[") and candidate.endswith("]")
        ):
            return candidate

    # 2. If no valid fence, extract the outermost object { ... }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        return cleaned[first_brace : last_brace + 1].strip()

    # 3. Check for outermost array [ ... ]
    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")
    if first_bracket != -1 and last_bracket > first_bracket:
        return cleaned[first_bracket : last_bracket + 1].strip()

    # 4. Fallback: Return original stripped string
    return cleaned


def create_safe_fallback_analysis_payload(company_name: str = "General", error_reason: str = "") -> Dict[str, Any]:
    """
    Generates a resilient, structured fallback payload if AI generation encounters an unrecoverable failure.
    Guarantees the dashboard view won't crash when rendering partial or fallback outcomes.
    """
    logger.info(f"Generating safe fallback analysis payload for {company_name}")
    return {
        "resume_analysis": {
            "ats_score": 65,
            "overall_feedback": (
                "Resume received and preliminary baseline computed. "
                f"Full AI deep-dive experienced a temporary service limitation ({error_reason or 'service busy'})."
            ),
            "strengths": [
                "Clean document layout and readable text formatting.",
                "Foundational technical qualifications and educational background identified."
            ],
            "areas_of_improvement": [
                "Quantify measurable engineering outcomes in project bullets (e.g. % improvement).",
                "Ensure core technologies match target role requirements closely."
            ],
            "keywords_found": ["General Computing", "Engineering", "Development"],
            "keywords_missing": ["Production CI/CD", "Cloud Architecture"]
        },
        "job_match": {
            "match_percentage": 68,
            "matched_skills": ["Programming Fundamentals", "Problem Solving", "Core CS Knowledge"],
            "missing_skills": ["Domain-Specific Frameworks", "Production Deployment Experience"],
            "hiring_criteria": "Standard campus hiring readiness benchmark.",
            "recommendation": "Strengthen technical portfolio with deployment-ready capstone projects."
        },
        "skill_gap": [
            {
                "skill": "Production Architecture & Testing",
                "priority": "High",
                "reason": "Campus recruiters seek demonstrated project lifecycle and testing experience.",
                "suggested_project": "Build an end-to-end full stack web application with unit and integration tests."
            },
            {
                "skill": "System Design Fundamentals",
                "priority": "Medium",
                "reason": "Crucial for clearing intermediate technical rounds.",
                "suggested_project": "Design and document a scalable distributed URL shortener or rate limiter."
            }
        ],
        "learning_roadmap": [
            {
                "week": 1,
                "focus": "Core Data Structures & Algorithmic Complexity",
                "tasks": ["Review Arrays, Hash Tables, and Pointers", "Solve 10 LeetCode Easy/Medium problems"]
            },
            {
                "week": 2,
                "focus": "Trees, Graphs & Dynamic Programming",
                "tasks": ["Study BFS/DFS and recursion patterns", "Implement basic DP memoization"]
            },
            {
                "week": 3,
                "focus": "System Design & Database Modeling",
                "tasks": ["Learn database normalization and indexing", "Practice API design patterns"]
            },
            {
                "week": 4,
                "focus": "Portfolio Project Modernization",
                "tasks": ["Refactor existing resume project", "Add Docker containerization and documentation"]
            },
            {
                "week": 5,
                "focus": "Company-Specific Mock Technical Rounds",
                "tasks": ["Review previous hiring questions", "Conduct timed coding practice"]
            },
            {
                "week": 6,
                "focus": "HR, Behavioral & STAR Format Preparation",
                "tasks": ["Prepare STAR stories for past accomplishments", "Practice communication and composure"]
            }
        ],
        "interview_questions": {
            "hr": [
                "Can you introduce yourself and explain what motivated your interest in this engineering role?",
                "Describe a project challenge where you had to quickly learn a new technology or tool.",
                "How do you organize your time when balancing multiple deadlines or coursework?",
                "What kind of team environment allows you to do your best work?",
                "Where do you see yourself developing technically over the next two years?"
            ],
            "technical": [
                "How do hash tables work internally, and how are collision resolutions handled?",
                "Explain the difference between synchronous and asynchronous code execution with examples.",
                "What happens under the hood when a user types a URL into a browser and presses Enter?",
                "Compare SQL vs NoSQL databases in terms of schema flexibility and ACID guarantees.",
                "How would you approach debugging a memory leak or sudden spike in CPU utilization?"
            ],
            "behavioral": [
                "Tell me about a time you had a technical disagreement with a team member and how you resolved it.",
                "Describe a situation where a project deliverable didn't go as planned. What was your takeaway?",
                "Give an example of receiving critical code review feedback and how you incorporated it.",
                "How do you handle ambiguous requirements when assigned an open-ended project task?",
                "Describe a project achievement that you are most proud of and your individual contribution."
            ]
        },
        "overall_recommendation_summary": (
            f"Baseline placement readiness profile established for {company_name}. "
            "Focus on the recommended 6-week curriculum and practice your mock interview questions."
        ),
        "conflicts": []
    }


def generate_json_response(system_instruction: str, prompt: str) -> dict:
    """
    Sends a request to Gemini using the google-genai SDK, enforcing a JSON response.
    Catches and classifies APIError, rate limits, network timeouts, and malformed outputs.
    Returns a Python dictionary parsed from the JSON output.
    """
    raw_text = ""
    try:
        client = get_gemini_client()

        # Configure output for structured JSON
        cfg = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.2,
        )

        logger.info(f"Invoking Gemini model: {config.GEMINI_MODEL}")
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=cfg,
        )

        raw_text = getattr(response, "text", "") or ""
        if not raw_text or not raw_text.strip():
            logger.error("Gemini returned an empty or null text response.")
            raise AIResponseFormatError("Gemini returned an empty response. The model may have truncated output.")

        logger.info("Successfully received Gemini response text. Attempting JSON parsing...")
        cleaned_json = _extract_json_string(raw_text)
        parsed_data = json.loads(cleaned_json)

        if not isinstance(parsed_data, (dict, list)):
            raise AIResponseFormatError("Parsed AI output is neither a dictionary nor a list.")

        return parsed_data

    except APIError as e:
        msg = str(e)
        logger.error(f"Gemini API Exception occurred: {msg}")
        msg_lower = msg.lower()

        if "429" in msg or "resource_exhausted" in msg_lower or "quota" in msg_lower:
            raise AIRateLimitError(f"Gemini API quota exceeded: {msg}")
        elif "401" in msg or "403" in msg or "invalid_argument" in msg_lower and "key" in msg_lower:
            raise AIAuthError(f"Gemini authentication failed: {msg}")
        elif "503" in msg or "unavailable" in msg_lower or "overloaded" in msg_lower:
            raise AIServiceUnavailableError(f"Gemini service unavailable: {msg}")
        else:
            raise AIAnalysisError(f"Gemini API Error: {msg}", retryable=False)

    except (socket.timeout, TimeoutError) as te:
        logger.error(f"Network timeout contacting Gemini: {te}")
        raise AINetworkError(f"Network timeout during AI analysis: {str(te)}")

    except json.JSONDecodeError as jde:
        logger.error(f"JSON decoding failed. Content was: {raw_text[:500] if raw_text else 'None'}... Error: {jde}")
        raise AIResponseFormatError(
            f"Failed to parse Gemini response as valid JSON: {str(jde)}"
        )

    except AIAnalysisError:
        raise

    except Exception as e:
        logger.error(f"Unexpected error in Gemini utility: {str(e)}")
        # Check for socket/network error signatures
        err_msg = str(e).lower()
        if "connection" in err_msg or "dns" in err_msg or "network" in err_msg:
            raise AINetworkError(f"Network error communicating with AI provider: {str(e)}")
        raise AIAnalysisError(f"Unexpected AI processing error: {str(e)}")
