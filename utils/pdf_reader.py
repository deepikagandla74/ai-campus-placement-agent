"""
Document reader utilities for PDF and DOCX resume parsing and validation.

Supports extracting clean, structured textual representations from uploaded .pdf
and .docx documents, checking page/paragraph constraints, handling corrupt or
encrypted files gracefully, and validating word/character thresholds.
"""

import io
import logging
import os
from typing import List, Optional, Tuple, Union
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

try:
    import docx
    from docx.opc.exceptions import PackageNotFoundError
except ImportError:  # pragma: no cover
    docx = None
    PackageNotFoundError = Exception

logger = logging.getLogger(__name__)

# Constants for document processing limits
MAX_PDF_PAGES = 10
MAX_DOCX_PARAGRAPHS = 1000
MAX_RESUME_TEXT_CHARS = 25000
MIN_RESUME_TEXT_CHARS = 50
MIN_RESUME_WORD_COUNT = 10
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx"}


def validate_resume_text(text: str) -> Tuple[bool, str]:
    """
    Validates whether resume text satisfies length, word count, and content criteria.
    Returns (is_valid, error_message).
    """
    if not text or not text.strip():
        return False, "Resume content cannot be empty. Please provide your resume details."

    cleaned = text.strip()
    if len(cleaned) < MIN_RESUME_TEXT_CHARS:
        return False, f"Resume content is too short (minimum {MIN_RESUME_TEXT_CHARS} characters required for analysis)."

    words = [w for w in cleaned.split() if w.strip()]
    if len(words) < MIN_RESUME_WORD_COUNT:
        return False, f"Resume content must contain at least {MIN_RESUME_WORD_COUNT} words (education, skills, or experience)."

    return True, ""


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts and returns text content from a PDF file using PyPDF2.
    Enforces maximum page limits, verifies encryption status, and validates extracted text.
    """
    text_content = ""
    try:
        logger.info(f"Initiating text extraction from PDF: {pdf_path}")
        reader = PdfReader(pdf_path)

        if getattr(reader, "is_encrypted", False):
            raise ValueError(
                "The uploaded PDF is password-protected or encrypted. Please upload an unprotected PDF."
            )

        num_pages = len(reader.pages)
        if num_pages == 0:
            raise ValueError("The PDF file contains no readable pages.")

        if num_pages > MAX_PDF_PAGES:
            raise ValueError(
                f"The uploaded PDF contains {num_pages} pages, exceeding the {MAX_PDF_PAGES}-page limit for resumes. "
                "Please upload a standard concise campus placement resume."
            )

        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_content += page_text + "\n"

        cleaned_text = text_content.strip()
        is_valid, validation_msg = validate_resume_text(cleaned_text)
        if not is_valid:
            logger.warning(f"Extracted PDF text validation failed: {validation_msg}")
            raise ValueError(
                f"Could not extract sufficient text from PDF: {validation_msg} "
                "Ensure your document is a text-based PDF rather than a scanned image."
            )

        # Enforce maximum character boundary to avoid excessive token consumption
        if len(cleaned_text) > MAX_RESUME_TEXT_CHARS:
            logger.warning(
                f"PDF text length ({len(cleaned_text)} chars) exceeded limit. Truncating to {MAX_RESUME_TEXT_CHARS} chars."
            )
            cleaned_text = cleaned_text[:MAX_RESUME_TEXT_CHARS]

        logger.info(f"PDF text extraction completed successfully ({len(cleaned_text)} characters).")
        return cleaned_text

    except FileNotFoundError:
        logger.error(f"File not found: {pdf_path}")
        raise FileNotFoundError(f"Resume file was not found at path: {pdf_path}")
    except ValueError as ve:
        logger.error(f"Validation error reading PDF: {str(ve)}")
        raise ve
    except PdfReadError as pre:
        logger.error(f"PyPDF2 ReadError encountered: {str(pre)}")
        raise ValueError(f"Could not read PDF file (corrupted or malformed): {str(pre)}")
    except Exception as e:
        logger.error(f"Unexpected error reading PDF: {str(e)}")
        raise RuntimeError(f"Failed to parse PDF file: {str(e)}")


def extract_text_from_docx(docx_source: Union[str, io.BytesIO]) -> str:
    """
    Extracts structured text content from a Microsoft Word (.docx) document.

    Iterates through body paragraphs, tables (rows and cells), and section headers/footers
    where applicable to assemble a complete textual resume profile.

    Parameters:
        docx_source: File path (str) or binary stream (io.BytesIO) pointing to the .docx file.

    Returns:
        Cleaned, extracted text string from the DOCX document.

    Raises:
        ImportError: If python-docx library is not installed in the environment.
        FileNotFoundError: If the specified file path does not exist on disk.
        ValueError: If file is malformed, password-locked, empty, or fails validation checks.
        RuntimeError: For other unexpected document processing errors.
    """
    if docx is None:
        logger.error("python-docx package is not available for DOCX parsing.")
        raise ImportError(
            "DOCX parsing support requires the 'python-docx' library. Please install python-docx."
        )

    logger.info(f"Initiating text extraction from DOCX source: {docx_source}")
    if isinstance(docx_source, str) and not os.path.exists(docx_source):
        logger.error(f"DOCX file not found: {docx_source}")
        raise FileNotFoundError(f"Resume file was not found at path: {docx_source}")

    try:
        doc = docx.Document(docx_source)
    except FileNotFoundError:
        logger.error(f"DOCX file not found: {docx_source}")
        raise FileNotFoundError(f"Resume file was not found at path: {docx_source}")
    except PackageNotFoundError as pnfe:
        logger.error(f"DOCX package corrupted or not a valid zip archive: {pnfe}")
        raise ValueError(
            "The uploaded file is not a valid or readable Word document (.docx). "
            "Please ensure it is not corrupt or saved in legacy binary .doc format."
        )
    except Exception as exc:
        logger.error(f"Unexpected error opening DOCX document: {exc}")
        raise ValueError(f"Unable to read Word document (.docx): {str(exc)}")

    extracted_lines: List[str] = []

    try:
        # Extract paragraph text
        paragraph_count = len(doc.paragraphs)
        if paragraph_count > MAX_DOCX_PARAGRAPHS:
            logger.warning(
                f"DOCX contains {paragraph_count} paragraphs, which is unusually long for a resume."
            )

        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if text:
                extracted_lines.append(text)

        # Extract text from tables (common in resume templates for education/skills)
        for table in doc.tables:
            for row in table.rows:
                row_cells_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells_text:
                    # Deduplicate adjacent merged cells having identical text
                    deduped_cells = []
                    for c_text in row_cells_text:
                        if not deduped_cells or deduped_cells[-1] != c_text:
                            deduped_cells.append(c_text)
                    if deduped_cells:
                        extracted_lines.append(" | ".join(deduped_cells))

        # Extract header and footer text if present
        for section in doc.sections:
            try:
                for header_para in section.header.paragraphs:
                    h_text = header_para.text.strip()
                    if h_text and h_text not in extracted_lines:
                        extracted_lines.insert(0, h_text)
            except Exception as hdr_err:
                logger.debug(f"Could not read section header: {hdr_err}")

        combined_text = "\n".join(extracted_lines).strip()

        # Validate extracted text content
        is_valid, validation_msg = validate_resume_text(combined_text)
        if not is_valid:
            logger.warning(f"Extracted DOCX text validation failed: {validation_msg}")
            raise ValueError(
                f"Could not extract sufficient text from DOCX document: {validation_msg} "
                "Ensure your Word document contains actual text rather than embedded images or empty sections."
            )

        # Enforce maximum character boundary
        if len(combined_text) > MAX_RESUME_TEXT_CHARS:
            logger.warning(
                f"DOCX text length ({len(combined_text)} chars) exceeded limit. Truncating to {MAX_RESUME_TEXT_CHARS} chars."
            )
            combined_text = combined_text[:MAX_RESUME_TEXT_CHARS]

        logger.info(
            f"DOCX text extraction completed successfully ({len(combined_text)} characters, "
            f"{len(extracted_lines)} content blocks)."
        )
        return combined_text

    except ValueError as ve:
        raise ve
    except Exception as e:
        logger.error(f"Error parsing DOCX content: {str(e)}")
        raise RuntimeError(f"Failed to parse Word document: {str(e)}")


def extract_text_from_file(file_path: str) -> str:
    """
    Unified resume text extractor that routes automatically based on file extension (.pdf or .docx).

    Parameters:
        file_path: Filesystem path to the resume file.

    Returns:
        Validated text extracted from the document.

    Raises:
        ValueError: If file extension is unsupported or content fails validation.
        FileNotFoundError: If the file does not exist.
        RuntimeError: For parsing failures.
    """
    lower_path = file_path.lower()
    if lower_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif lower_path.endswith(".docx"):
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(
            "Unsupported file format. Only PDF (.pdf) and Word documents (.docx) are supported."
        )
