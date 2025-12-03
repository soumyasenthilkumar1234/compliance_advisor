import os
import uuid
import json
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from extractor import extract_text_from_file
from nlp_utils import analyze_documents, generate_checklist_csv

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
ALLOWED_EXT = {".pdf", ".docx", ".txt", ".xlsx", ".xls"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB max upload

@app.route("/")
def index():
    return render_template("index.html")


def _allowed_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXT


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Accepts files via multipart/form-data (input name 'files[]') and returns JSON analysis.
    """
    files = request.files.getlist("files[]")
    if not files or files == [None]:
        return jsonify({"error": "No files uploaded"}), 400

    saved = []
    for f in files:
        filename = f.filename
        if not filename:
            continue
        ext = os.path.splitext(filename)[1].lower()
        uid = uuid.uuid4().hex
        save_name = f"{uid}_{filename}"
        path = os.path.join(UPLOAD_FOLDER, save_name)
        f.save(path)
        supported = ext in ALLOWED_EXT
        saved.append({"path": path, "name": filename, "supported": supported})

    docs = []
    for s in saved:
        if not s["supported"]:
            docs.append({
                "filename": s["name"],
                "supported": False,
                "errors": "Unsupported file type"
            })
            continue
        try:
            text = extract_text_from_file(s["path"])
            docs.append({
                "filename": s["name"],
                "supported": True,
                "text": text
            })
        except Exception as e:
            docs.append({
                "filename": s["name"],
                "supported": False,
                "errors": f"Extraction error: {str(e)}"
            })

    analysis = analyze_documents(docs)
    job_id = uuid.uuid4().hex[:8]
    out_json_path = os.path.join(OUTPUT_FOLDER, f"analysis_{job_id}.json")
    with open(out_json_path, "w", encoding="utf8") as fh:
        json.dump(analysis, fh, ensure_ascii=False, indent=2)

    csv_path = os.path.join(OUTPUT_FOLDER, f"checklist_{job_id}.csv")
    generate_checklist_csv(analysis, csv_path)

    # Provide relative download URL for CSV
    download_url = f"/download/{os.path.basename(csv_path)}"
    return jsonify({"analysis": analysis, "csv": download_url}), 200


@app.route("/download/<path:filename>")
def download_file(filename):
    path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(path):
        return "File not found", 404
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    # Production: use gunicorn; here for demo use debug True
    app.run(debug=True, port=5000)
