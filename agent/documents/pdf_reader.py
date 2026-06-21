from __future__ import annotations

import base64
import io

import pdfplumber

MIN_TEXT_CHARS = 150


def extract_text(content: bytes, content_type: str) -> str:
    """
    Extract plain text from an uploaded file.
    - PDF: pdfplumber first; if < MIN_TEXT_CHARS (scanned), fall back to Claude Vision.
    - Image (PNG/JPG/etc.): Claude Vision directly.
    - Everything else: UTF-8 decode.
    """
    if "pdf" in content_type:
        return _from_pdf(content)
    if content_type.startswith("image/"):
        return _from_image(content, content_type)
    return content.decode("utf-8", errors="ignore")


def _from_pdf(content: bytes) -> str:
    text = _pdfplumber(content)
    if len(text.strip()) >= MIN_TEXT_CHARS:
        return text
    # Scanned PDF — use Claude Vision via the native PDF document type
    return _claude_vision_pdf(content)


def _pdfplumber(content: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(pages)
    except Exception as exc:
        print(f"[pdf_reader] pdfplumber failed: {exc}")
        return ""


def _claude_vision_pdf(content: bytes) -> str:
    from llm.claude import get_client, DOCUMENT_MODEL

    pdf_b64 = base64.standard_b64encode(content).decode()
    try:
        response = get_client().messages.create(
            model=DOCUMENT_MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Transcribe the full text of this document verbatim. "
                            "Preserve all names, dates, numbers, addresses, and legal language exactly. "
                            "Do not summarize or omit anything."
                        ),
                    },
                ],
            }],
        )
        return response.content[0].text
    except Exception as exc:
        print(f"[pdf_reader] Claude Vision PDF failed: {exc}")
        return ""


def _from_image(content: bytes, content_type: str) -> str:
    from llm.claude import get_client, DOCUMENT_MODEL

    img_b64 = base64.standard_b64encode(content).decode()
    try:
        response = get_client().messages.create(
            model=DOCUMENT_MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": content_type,
                            "data": img_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Transcribe the full text of this document verbatim. "
                            "Preserve all names, dates, numbers, addresses, and legal language exactly. "
                            "Do not summarize or omit anything."
                        ),
                    },
                ],
            }],
        )
        return response.content[0].text
    except Exception as exc:
        print(f"[pdf_reader] Claude Vision image failed: {exc}")
        return ""
