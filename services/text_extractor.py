from io import BytesIO

from docx import Document
from PyPDF2 import PdfReader


def extract_text_from_upload(uploaded_file) -> str:
    suffix = uploaded_file.name.lower().split(".")[-1]
    raw_bytes = uploaded_file.getvalue()

    if suffix == "txt":
        return raw_bytes.decode("utf-8", errors="ignore").strip()

    if suffix == "pdf":
        reader = PdfReader(BytesIO(raw_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text.strip()

    if suffix == "docx":
        document = Document(BytesIO(raw_bytes))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return text.strip()

    raise ValueError("Unsupported file format. Please upload PDF, DOCX, or TXT.")
