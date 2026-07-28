"""Sleep Detector Web App - deploy with: gunicorn app:app"""

import base64
import os
import secrets
import uuid
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory

from detector_core import BASE_DIR, DetectorSession
from report_pdf import build_report_pdf

load_dotenv()  # reads the ".env" file and loads its values into os.environ

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))

sessions = {}
REPORTS_FOLDER = os.path.join(BASE_DIR, "session_reports")
os.makedirs(REPORTS_FOLDER, exist_ok=True)


def get_session(session_id):
    if session_id not in sessions:
        sessions[session_id] = DetectorSession()
    return sessions[session_id]


def build_report(report_data):
    """
    Use pandas to analyze the session's event log, export a companion CSV,
    then hand the enriched data off to reportlab for the PDF.
    """
    events = report_data.get("events") or []

    if events:
        events_df = pd.DataFrame(events)

        # How many of each event type occurred (Series -> plain dict for easy use)
        event_counts = events_df["type"].value_counts().to_dict()

        # Average gap (in seconds) between consecutive alert events
        gaps = events_df["elapsed_seconds"].diff().dropna()
        avg_gap_seconds = round(gaps.mean(), 1) if not gaps.empty else None
    else:
        events_df = pd.DataFrame(columns=["time", "elapsed_seconds", "type"])
        event_counts = {}
        avg_gap_seconds = None

    report_data["event_counts"] = event_counts
    report_data["avg_gap_seconds"] = avg_gap_seconds

    # Save a CSV copy of the event log alongside the PDF report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"session_events_{timestamp}.csv"
    events_df.to_csv(os.path.join(REPORTS_FOLDER, csv_filename), index=False)

    return build_report_pdf(report_data, REPORTS_FOLDER)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video/<path:filename>")
def bg_video(filename):
    return send_from_directory(os.path.join(BASE_DIR, "video"), filename)


@app.route("/logo.png")
def logo():
    return send_from_directory(os.path.join(BASE_DIR, "image"), "logo.png")


@app.route("/sleep-alert.mp3")
def alert_sound():
    return send_from_directory(os.path.join(BASE_DIR, "Audio"), "sleep-alert.mp3")


@app.route("/audio/<path:filename>")
def app_audio(filename):
    return send_from_directory(os.path.join(BASE_DIR, "Audio"), filename)


@app.route("/api/detect", methods=["POST"])
def detect():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id") or str(uuid.uuid4())
    image_data = data.get("image")

    if not image_data:
        return jsonify({"error": "No image provided"}), 400

    try:
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"error": "Invalid image data"}), 400
    except Exception:
        return jsonify({"error": "Could not decode image"}), 400

    session = get_session(session_id)
    result = session.process_frame(frame)

    _, buffer = cv2.imencode(".jpg", result["annotated_frame"], [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    encoded_image = base64.b64encode(buffer).decode("utf-8")

    return jsonify(
        {
            "session_id": session_id,
            "alert_level": result["alert_level"],
            "image": encoded_image,
            "eyes_found": result["eyes_found"],
            "face_detected": result["face_detected"],
            "sleep_events": result["sleep_events"],
            "session_time": result["session_time"],
            "play_sound": result["play_sound"],
            "new_event": result["new_event"],
        }
    )


@app.route("/api/reset", methods=["POST"])
def reset_session():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    report_url = None

    if session_id and session_id in sessions:
        session = sessions[session_id]
        report_data = session.generate_report()
        filename = build_report(report_data)
        report_url = f"/reports/{filename}"
        del sessions[session_id]

    return jsonify({"ok": True, "report_url": report_url})


@app.route("/reports/<path:filename>")
def download_report(filename):
    return send_from_directory(
        REPORTS_FOLDER, filename, as_attachment=True, mimetype="application/pdf"
    )


if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", os.environ.get("PORT", 5000)))
    debug_mode = os.environ.get("FLASK_DEBUG", "True") == "True"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)