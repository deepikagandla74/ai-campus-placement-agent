import pytest
from utils.pdf_reader import (
    validate_resume_text,
    MIN_RESUME_TEXT_CHARS,
    MIN_RESUME_WORD_COUNT,
    MAX_RESUME_TEXT_CHARS,
    MAX_PDF_PAGES,
    standardize_resume_sections,
    format_standardized_resume,
    extract_text_with_ocr_fallback,
    extract_text_from_pdf,
)
from app import app


def test_validate_resume_text_empty():
    is_valid, msg = validate_resume_text("")
    assert not is_valid
    assert "empty" in msg.lower()

    is_valid, msg = validate_resume_text("   \n\t  ")
    assert not is_valid


def test_validate_resume_text_too_short():
    short_text = "I am a programmer."
    is_valid, msg = validate_resume_text(short_text)
    assert not is_valid
    assert f"minimum {MIN_RESUME_TEXT_CHARS}" in msg


def test_validate_resume_text_insufficient_words():
    # Length > 50 chars but only 4 words
    text_few_words = "Supercalifragilisticexpialidocious " * 3
    is_valid, msg = validate_resume_text(text_few_words)
    assert not is_valid
    assert f"at least {MIN_RESUME_WORD_COUNT} words" in msg


def test_validate_resume_text_valid():
    valid_resume = (
        "BTech Computer Science graduate with strong foundation in Python, Java, Data Structures, "
        "and SQL. Developed multiple full-stack web applications and REST APIs using Flask and Docker."
    )
    is_valid, msg = validate_resume_text(valid_resume)
    assert is_valid
    assert msg == ""


def test_analyze_route_rejects_empty_and_short_pasted_text():
    app.config["TESTING"] = True
    with app.test_client() as client:
        # No input
        res = client.post("/analyze", data={}, follow_redirects=True)
        assert res.status_code == 200
        assert b"Please upload a PDF resume or paste your resume text" in res.data

        # Too short pasted text
        res = client.post("/analyze", data={"resume_text": "Hi"}, follow_redirects=True)
        assert res.status_code == 200
        assert b"too short" in res.data


def test_standardize_resume_sections_identifies_canonical_sections():
    raw_resume = """
    Jane Candidate
    Email: jane@example.com | Phone: 123-456-7890

    Education
    B.Tech Computer Science, University of Technology, 2024. CGPA: 8.8

    Technical Skills
    Python, Java, Flask, SQL, Git, Docker, System Design

    Work Experience
    Software Engineering Intern at TechCorp. Built microservices in Flask.

    Projects
    AI Placement Agent: Built multi-agent resume analysis tool with Python and LLMs.

    Certifications
    AWS Certified Cloud Practitioner, 2023.
    """
    sections = standardize_resume_sections(raw_resume)
    assert "education" in sections
    assert "B.Tech Computer Science" in sections["education"]
    assert "skills" in sections
    assert "Python, Java" in sections["skills"]
    assert "experience" in sections
    assert "TechCorp" in sections["experience"]
    assert "projects" in sections
    assert "AI Placement Agent" in sections["projects"]
    assert "certifications" in sections

    formatted = format_standardized_resume(sections)
    assert "### Education & Qualifications" in formatted
    assert "### Technical Skills & Competencies" in formatted
    assert "### Work Experience & Internships" in formatted
    assert "### Key Projects & Portfolio" in formatted


def test_standardize_resume_sections_unstructured_fallback():
    unstructured_text = (
        "Dedicated software developer with 2 years of hands-on experience in full stack "
        "development, REST APIs, and database modeling without any section headers."
    )
    sections = standardize_resume_sections(unstructured_text)
    assert "summary" in sections
    assert "Dedicated software developer" in sections["summary"]


def test_ocr_fallback_triggered_on_scanned_pdf(monkeypatch, tmp_path):
    # Create a dummy PDF with zero text (scanned PDF simulation)
    from PyPDF2 import PdfWriter
    pdf_path = tmp_path / "scanned_resume.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    # Mock extract_text_with_ocr_fallback to simulate Gemini Vision OCR success
    def mock_ocr(path):
        return (
            "John Doe - Software Engineer. Education: BS in CS from State College. "
            "Skills: Python, C++, Docker, SQL. Experience: Intern at ABC Corp building APIs."
        )

    monkeypatch.setattr("utils.pdf_reader.extract_text_with_ocr_fallback", mock_ocr)

    extracted = extract_text_from_pdf(str(pdf_path))
    assert "John Doe" in extracted
    assert "Python, C++" in extracted

