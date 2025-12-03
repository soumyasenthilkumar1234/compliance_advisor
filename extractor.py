import pdfplumber
import docx
import pandas as pd
import os

def extract_text_from_pdf(path):
    text_chunks = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            try:
                txt = page.extract_text()
            except Exception:
                txt = ""
            if txt:
                text_chunks.append(txt)
    return "\n".join(text_chunks).strip()

def extract_text_from_docx(path):
    doc = docx.Document(path)
    lines = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n".join(lines)

def extract_text_from_txt(path):
    with open(path, "r", encoding="utf8", errors="ignore") as fh:
        return fh.read()

def extract_text_from_excel(path):
    chunks = []
    try:
        sheets = pd.read_excel(path, sheet_name=None)
        for name, sheet in sheets.items():
            # join each row into lines
            rows = sheet.fillna("").astype(str).apply(lambda r: " ".join(r.values.astype(str)), axis=1).tolist()
            if rows:
                chunks.append("\n".join(rows))
    except Exception:
        pass
    return "\n".join(chunks)

def extract_text_from_file(path):
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    elif ext == ".docx":
        return extract_text_from_docx(path)
    elif ext == ".txt":
        return extract_text_from_txt(path)
    elif ext in (".xlsx", ".xls"):
        return extract_text_from_excel(path)
    else:
        raise ValueError("Unsupported file type for extraction.")
