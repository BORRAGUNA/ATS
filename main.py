import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google import genai
import PyPDF2

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

API_KEY = os.getenv("GENAI_API_KEY") or "YOUR_API_KEY"
client = genai.Client(api_key=API_KEY)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
CORS(app)


def extract_text_from_pdf(path):
    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)

        if reader.is_encrypted:
            reader.decrypt("")

        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"

    return text.strip()


def ask_gemini(prompt):
    r = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return r.text


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    if "resume" not in request.files:
        return jsonify({"error": "Resume file missing"}), 400

    resume_file = request.files["resume"]
    jd_text = request.form.get("job_description")

    if not jd_text:
        return jsonify({"error": "Job Description is required"}), 400

    save_path = os.path.join(UPLOAD_FOLDER, resume_file.filename)
    resume_file.save(save_path)

    resume_text = extract_text_from_pdf(save_path)
    if resume_text == "":
        return jsonify({"error": "Cannot read text. Upload text-based PDF"}), 400

    resume_prompt = f"""
Extract resume details strictly in JSON:
skills, experience_summary, education, tools

Resume:
{resume_text}
    """

    parsed_resume = ask_gemini(resume_prompt)

    jd_prompt = f"""
Extract job description details in JSON:
required_skills, responsibilities, preferred_qualifications

JD:
{jd_text}
"""

    parsed_jd = ask_gemini(jd_prompt)

    ats_prompt = f"""
Compare Resume vs Job Description.
Return STRICT JSON only:
{{
 "match_score": number(0-100),
 "matching_skills": [],
 "missing_skills": [],
 "strengths": [],
 "improvements": []
}}

Resume:
{parsed_resume}

JD:
{parsed_jd}
"""

    ats_result = ask_gemini(ats_prompt)

    return jsonify({
        "resume": parsed_resume,
        "job_description": parsed_jd,
        "ats_result": ats_result
    })


if __name__ == "__main__":
    app.run(debug=True, port=8080)
