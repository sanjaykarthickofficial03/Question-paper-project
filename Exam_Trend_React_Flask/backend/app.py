import os,uuid
from pathlib import Path
import truststore
truststore.inject_into_ssl()
import requests
from flask import Flask,jsonify,request,send_file
from flask_cors import CORS
from analyzer import analyze,result,report
from flask import jsonify, request
from config import UPLOAD_FOLDER,REPORT_FOLDER
CURRENT_RESULTS = None
CURRENT_DF = None
app=Flask(__name__); CORS(app); os.makedirs(UPLOAD_FOLDER,exist_ok=True); os.makedirs(REPORT_FOLDER,exist_ok=True); LAST=None
@app.get('/api/health')
def health(): return jsonify(status='ok')
@app.post('/api/analyze')
def run():

    global CURRENT_DF, CURRENT_RESULTS

    files = request.files.getlist('files')

    if not files:
        return jsonify({
            "error": "Upload at least one PDF."
        }), 400

    paths = []

    try:

        # -----------------------------------------
        # Save uploaded PDFs
        # -----------------------------------------

        for f in files:

            if not f.filename:
                continue

            if not f.filename.lower().endswith(".pdf"):
                continue

            filename = (
                f"{uuid.uuid4().hex}_"
                f"{os.path.basename(f.filename)}"
            )

            path = os.path.join(
                UPLOAD_FOLDER,
                filename
            )

            f.save(path)
            paths.append(path)

        if not paths:
            return jsonify({
                "error": "No valid PDF files uploaded."
            }), 400

        # -----------------------------------------
        # Analyze
        # -----------------------------------------

        df, errors = analyze(paths)

        # DEBUG: verify dataframe structure
        print("\n========== DATAFRAME DEBUG ==========")
        print("Columns:", df.columns.tolist())
        print("Shape:", df.shape)
        print(df.head())
        print("=====================================\n")

        # -----------------------------------------
        # Build result
        # -----------------------------------------

        result_data = result(df)

        result_data["errors"] = errors

        # -----------------------------------------
        # NOW store the data
        # -----------------------------------------

        CURRENT_DF = df
        CURRENT_RESULTS = result_data

        return jsonify(result_data)

    except Exception as e:

        import traceback
        traceback.print_exc()

        return jsonify({
            "error": str(e)
        }), 500
    
@app.route(
    "/api/emerging-topics",
    methods=["GET"]
)
def get_emerging_topics():

    if CURRENT_DF is None:
        return jsonify({
            "error": "Run analysis first."
        }), 400

    from pattern_analysis import (
        emerging_topics
    )

    return jsonify({
        "emerging_topics":
            emerging_topics(
                CURRENT_DF,
                top_k=10
            )
    })
@app.get('/api/topic/<path:topic>')
def topic_details(topic):

    global CURRENT_DF

    if CURRENT_DF is None:
        return jsonify({
            "error":
                "Run research analysis first."
        }), 400

    from pattern_analysis import pattern_analysis

    patterns = pattern_analysis(
        CURRENT_DF
    )

    evolution = patterns[
        "topic_evolution"
    ].get(topic)

    blueprint = patterns[
        "question_blueprints"
    ].get(topic)

    if evolution is None:
        return jsonify({
            "error": "Topic not found."
        }), 404

    return jsonify({

        "topic": topic,

        "evolution": evolution,

        "blueprint": blueprint

    })
@app.post('/api/generate-practice-question')
def generate_practice_question():

    global CURRENT_DF

    if CURRENT_DF is None:
        return jsonify({
            "error":
                "Run research analysis first."
        }), 400

    data = request.get_json(
        silent=True
    ) or {}

    topic = data.get("topic")

    if not topic:
        return jsonify({
            "error": "Topic is required."
        }), 400

    from pattern_analysis import pattern_analysis

    patterns = pattern_analysis(
        CURRENT_DF
    )

    blueprint = patterns[
        "question_blueprints"
    ].get(topic)

    if not blueprint:
        return jsonify({
            "error":
                "No historical blueprint available."
        }), 404

    prompt = f"""
Generate ONE original practice examination
question based on the historical examination
pattern below.

Topic:
{topic}

Historical question type:
{blueprint['recent_question_type']}

Historical Bloom level:
{blueprint['recent_bloom_level']}

Historical difficulty:
{blueprint['estimated_difficulty']}

Typical marks:
{blueprint['common_marks']}

The output MUST be appropriate for
{blueprint['common_marks']} marks.

Do NOT claim that the generated question
will appear in the actual examination.

Return ONLY the question text.
"""

    try:

        import requests

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "phi4-mini",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        return jsonify({
    "topic": topic,
    "marks": blueprint["common_marks"],
    "part": blueprint["recent_part"],
    "question": data.get(
        "response",
        ""
    ).strip()
})

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500
@app.post('/api/report')
def generate_report():

    global CURRENT_RESULTS

    if CURRENT_RESULTS is None:
        return jsonify({
            "error":
                "Run research analysis first."
        }), 400

    report_path = os.path.join(
        REPORT_FOLDER,
        "exam_trend_research_report.pdf"
    )

    try:

        report(
            CURRENT_RESULTS,
            report_path
        )

        return send_file(
            report_path,
            as_attachment=True,
            download_name=
                "exam_trend_research_report.pdf"
        )

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500
if __name__=='__main__':app.run(host='127.0.0.1',port=5000,debug=True)
