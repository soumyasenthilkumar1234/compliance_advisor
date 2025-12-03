import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import re
import pandas as pd

# dateparser import with fallback for search
try:
    from dateparser.search import search_dates
except Exception:
    try:
        from dateparser import search_dates
    except Exception:
        search_dates = None

import dateparser

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Domain keywords
DOMAINS = {
    "Data Privacy": ["gdpr", "personal data", "data protection", "privacy", "ccpa", "personal information"],
    "Finance": ["invoice", "tax", "financial statement", "balance sheet", "auditor", "sox", "audit"],
    "HR / Labour": ["employee", "employee handbook", "termination", "leave", "hr policy", "wage"],
    "Safety / Environmental": ["safety", "haccp", "environment", "osha", "hazard", "safety manual"],
}

def classify_text(text):
    t = text.lower()
    scores = {}
    for d, kws in DOMAINS.items():
        s = sum(t.count(k) for k in kws)
        scores[d] = s
    top = max(scores.items(), key=lambda x: x[1])
    if top[1] == 0:
        return "Other"
    return top[0]

def extract_sentences(text):
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents if sent.text.strip()]

def simple_extractive_summary(text, n_sentences=3):
    sentences = extract_sentences(text)
    if not sentences:
        return ""
    if len(sentences) <= n_sentences:
        return " ".join(sentences)
    vectorizer = TfidfVectorizer(stop_words="english")
    X = vectorizer.fit_transform(sentences)
    scores = np.asarray(X.sum(axis=1)).ravel()
    top_idx = np.argsort(scores)[-n_sentences:][::-1]
    top_idx_sorted = sorted(top_idx)
    summary = " ".join([sentences[i] for i in top_idx_sorted])
    return summary

OBLIGATION_PATTERNS = [
    r"\bmust\b",
    r"\bshall\b",
    r"\bis required to\b",
    r"\bare required to\b",
    r"\bshould\b",
    r"\bdeadline\b",
    r"\bdue by\b",
    r"\bby\s+\w+\s+\d{4}\b",
    r"\bdue\s+on\b",
]

def find_obligations(text):
    sentences = extract_sentences(text)
    obligations = []
    for s in sentences:
        lowered = s.lower()
        if any(re.search(p, lowered) for p in OBLIGATION_PATTERNS):
            dates = []
            doc = nlp(s)
            for ent in doc.ents:
                if ent.label_ == "DATE":
                    parsed = dateparser.parse(ent.text)
                    if parsed:
                        try:
                            dates.append(parsed.date().isoformat())
                        except Exception:
                            pass
            # use search_dates if available
            if search_dates:
                try:
                    parsed_any = search_dates(s)
                    if parsed_any:
                        for _, dt in parsed_any:
                            try:
                                dates.append(dt.date().isoformat())
                            except Exception:
                                pass
                except Exception:
                    pass
            obligations.append({
                "sentence": s,
                "dates": list(sorted(set(dates)))
            })
    return obligations

def analyze_documents(docs):
    """
    docs: list of dicts with keys: filename, supported (bool), text (if supported)
    Returns a combined analysis dict
    """
    result = {"files": [], "combined_checklist": []}
    checklist_counter = 0
    for d in docs:
        entry = {"filename": d.get("filename"), "supported": d.get("supported", False)}
        if not d.get("supported"):
            entry["note"] = d.get("errors", "unsupported file")
            result["files"].append(entry)
            continue
        text = d.get("text", "")
        if not text or len(text.strip()) == 0:
            entry["note"] = "No text found"
            result["files"].append(entry)
            continue
        domain = classify_text(text)
        summary = simple_extractive_summary(text, n_sentences=3)
        obligations = find_obligations(text)
        # basic risk assignment based on keywords
        def _risk_level(sentence):
            s = sentence.lower()
            if any(k in s for k in ["penalty", "fine", "criminal", "suspend", "terminate"]):
                return "High"
            if any(k in s for k in ["required", "must", "shall", "deadline"]):
                return "Medium"
            return "Low"

        entry.update({
            "domain": domain,
            "summary": summary,
            "obligations": obligations
        })
        for o in obligations:
            checklist_counter += 1
            item = {
                "id": checklist_counter,
                "document": d.get("filename"),
                "sentence": o["sentence"],
                "dates": o["dates"],
                "assigned_to": "",
                "status": "Open",
                "risk": _risk_level(o["sentence"])
            }
            result["combined_checklist"].append(item)
        result["files"].append(entry)
    return result

def generate_checklist_csv(analysis, outpath):
    rows = []
    for item in analysis.get("combined_checklist", []):
        rows.append({
            "id": item.get("id"),
            "document": item.get("document"),
            "sentence": item.get("sentence"),
            "dates": ";".join(item.get("dates") or []),
            "assigned_to": item.get("assigned_to"),
            "status": item.get("status"),
            "risk": item.get("risk")
        })
    df = pd.DataFrame(rows)
    df.to_csv(outpath, index=False)
