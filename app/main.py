"""WattWise Flask Application - Stateless Electricity Unit Planner Backend."""
import os
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

# Load local .env if available
load_dotenv()

from app.calc import generate_reduction_plan, calculate_baseline
from app.ollama_client import extract_appliances, analyze_and_plan

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB max upload


@app.route("/")
def index():
    """Serves the WattWise single-page frontend."""
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "demo_mode": os.environ.get("DEMO_MODE", "true").lower() in ("true", "1", "yes"),
        "text_model": os.environ.get("TEXT_MODEL", "phi3:latest")
    })


@app.route("/api/extract", methods=["POST"])
def api_extract():
    """Step 2: OCR -> JSON
    Accepts multipart image uploads in-memory.
    Returns extracted appliances: {"appliances": [{"name": str, "watts": float}]}.
    """
    image_files = request.files.getlist("images")
    image_bytes_list = []

    for file_storage in image_files:
        if file_storage and file_storage.filename:
            # Read in-memory only (stateless, no disk storage)
            content = file_storage.read()
            if content:
                image_bytes_list.append(content)

    result = extract_appliances(image_bytes_list)
    return jsonify(result)


@app.route("/api/plan", methods=["POST"])
def api_plan():
    """Step 3: GOAL -> PLAN
    Accepts JSON:
    {
      "appliances": [{"name": str, "watts": float, "hours_per_day": float, "essential": bool}],
      "target_units": float
    }
    Calculates plan and requests LLM energy reduction analysis.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON payload."}), 400

    appliances = data.get("appliances", [])
    if not isinstance(appliances, list) or len(appliances) == 0:
        return jsonify({"error": "At least one appliance is required to generate a plan."}), 400

    try:
        target_units = float(data.get("target_units", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Target units must be a valid number."}), 400

    # 1. Generate math-based appliance plan
    plan_result = generate_reduction_plan(appliances, target_units)
    baseline_units = plan_result["baseline_units"]
    gap_units = plan_result["gap_units"]
    need = round(baseline_units - target_units, 2)

    # 2. Call LLM for expert analysis, friendly explanation, and tips
    llm_analysis = analyze_and_plan(
        appliances=appliances,
        target_units=target_units,
        baseline_units=baseline_units,
        need=need,
        calc_plan_items=plan_result["items"]
    )

    response_payload = {
        "baseline_units": baseline_units,
        "target_units": target_units,
        "gap_units": gap_units,
        "items": plan_result["items"],
        "explanation": llm_analysis.get("explanation", ""),
        "tips": llm_analysis.get("tips", []),
        "message": plan_result.get("message", "Plan generated")
    }

    return jsonify(response_payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
