import os
import uuid
import threading
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, render_template, send_file, current_app
from werkzeug.utils import secure_filename
from app.config import Config
from app.models import Conversion
from app.storage import get_storage_usage_gb, cleanup_if_needed, delete_conversion_files
from app.extractors import extract_text_from_file
from app.tts import convert_text_to_speech, TTSError

main_bp = Blueprint("main", __name__)

# In-memory job status tracking
conversion_jobs = {}


def cleanup_old_jobs():
    """Remove jobs older than 1 hour."""
    cutoff = datetime.utcnow() - timedelta(hours=1)
    old_jobs = [job_id for job_id, job in conversion_jobs.items()
                if job.get("created_at", datetime.utcnow()) < cutoff]
    for job_id in old_jobs:
        del conversion_jobs[job_id]


@main_bp.route("/")
def index():
    return render_template("index.html",
                           voices=Config.VOICES,
                           speeds=Config.SPEEDS,
                           default_voice=Config.DEFAULT_VOICE,
                           default_speed=Config.DEFAULT_SPEED)


@main_bp.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "storage_used_gb": round(get_storage_usage_gb(), 2),
        "storage_max_gb": Config.MAX_STORAGE_GB
    })


@main_bp.route("/api/voices")
def get_voices():
    return jsonify({"voices": Config.VOICES})


@main_bp.route("/api/convert", methods=["POST"])
def start_conversion():
    # Cleanup old jobs to prevent memory leak
    cleanup_old_jobs()

    # Get input
    text = None
    original_filename = None
    input_type = None

    if "file" in request.files and request.files["file"].filename:
        file = request.files["file"]
        original_filename = secure_filename(file.filename)
        ext = os.path.splitext(original_filename)[1].lower()

        if ext not in [".txt", ".md", ".pdf"]:
            return jsonify({"error": "Unsupported file type. Use .txt, .md, or .pdf"}), 400

        # Save uploaded file
        file_id = str(uuid.uuid4())
        source_path = os.path.join(Config.DATA_DIR, "sources", f"{file_id}{ext}")
        file.save(source_path)

        try:
            text = extract_text_from_file(source_path)
        except Exception as e:
            os.remove(source_path)
            return jsonify({"error": f"Failed to extract text: {str(e)}"}), 400

        input_type = "upload"
    elif request.form.get("text"):
        text = request.form.get("text", "").strip()
        input_type = "paste"

        # Save pasted text
        file_id = str(uuid.uuid4())
        source_path = os.path.join(Config.DATA_DIR, "sources", f"{file_id}.txt")
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        return jsonify({"error": "No text or file provided"}), 400

    if not text:
        return jsonify({"error": "Empty content"}), 400

    voice = request.form.get("voice", Config.DEFAULT_VOICE)
    try:
        speed = float(request.form.get("speed", Config.DEFAULT_SPEED))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid speed value"}), 400

    if voice not in Config.VOICES:
        return jsonify({"error": f"Invalid voice: {voice}"}), 400
    if speed < 0.25 or speed > 4.0:
        return jsonify({"error": "Speed must be between 0.25 and 4.0"}), 400

    # Create job
    job_id = str(uuid.uuid4())
    audio_path = os.path.join(Config.DATA_DIR, "audio", f"{job_id}.mp3")

    conversion_jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "total_chunks": 0,
        "current_chunk": 0,
        "error": None,
        "created_at": datetime.utcnow()
    }

    # Start conversion in background
    def run_conversion():
        try:
            def progress_callback(current, total):
                conversion_jobs[job_id]["current_chunk"] = current
                conversion_jobs[job_id]["total_chunks"] = total
                conversion_jobs[job_id]["progress"] = int((current / total) * 100)

            # Check storage and cleanup if needed
            cleanup_if_needed(len(text) * 10)  # Rough estimate

            duration = convert_text_to_speech(
                text=text,
                voice=voice,
                speed=speed,
                output_path=audio_path,
                progress_callback=progress_callback
            )

            audio_size = os.path.getsize(audio_path)

            # Save to database
            conversion = Conversion.create(
                input_type=input_type,
                original_filename=original_filename,
                source_path=source_path,
                full_text=text,
                voice=voice,
                speed=speed,
                audio_path=audio_path,
                audio_duration=duration,
                audio_size=audio_size
            )

            conversion_jobs[job_id]["status"] = "completed"
            conversion_jobs[job_id]["result_id"] = conversion.id
            conversion_jobs[job_id]["progress"] = 100

        except TTSError as e:
            conversion_jobs[job_id]["status"] = "failed"
            conversion_jobs[job_id]["error"] = str(e)
        except Exception as e:
            conversion_jobs[job_id]["status"] = "failed"
            conversion_jobs[job_id]["error"] = f"Unexpected error: {str(e)}"

    thread = threading.Thread(target=run_conversion)
    thread.start()

    return jsonify({
        "job_id": job_id,
        "content_length": len(text),
        "warning": "Large input may take a while to process" if len(text) > Config.LARGE_INPUT_WARNING else None
    })


@main_bp.route("/api/status/<job_id>")
def get_status(job_id):
    if job_id not in conversion_jobs:
        return jsonify({"error": "Job not found"}), 404

    job = conversion_jobs[job_id]
    return jsonify({
        "status": job["status"],
        "progress": job["progress"],
        "current_chunk": job["current_chunk"],
        "total_chunks": job["total_chunks"],
        "error": job["error"],
        "result_id": job.get("result_id")
    })


@main_bp.route("/api/result/<conversion_id>")
def get_result(conversion_id):
    conversion = Conversion.get_by_id(conversion_id)
    if not conversion:
        return jsonify({"error": "Conversion not found"}), 404

    return jsonify({
        "id": conversion.id,
        "audio_url": f"/api/audio/{conversion.id}",
        "audio_duration": conversion.audio_duration,
        "created_at": conversion.created_at.isoformat()
    })


@main_bp.route("/api/audio/<conversion_id>")
def get_audio(conversion_id):
    conversion = Conversion.get_by_id(conversion_id)
    if not conversion:
        return jsonify({"error": "Conversion not found"}), 404

    if not os.path.exists(conversion.audio_path):
        return jsonify({"error": "Audio file not found"}), 404

    return send_file(
        conversion.audio_path,
        mimetype="audio/mpeg",
        as_attachment=request.args.get("download") == "1",
        download_name=f"tinytts-{conversion.id[:8]}.mp3"
    )


@main_bp.route("/api/history")
def get_history():
    query = request.args.get("q", "").strip()
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    try:
        page = int(request.args.get("page", 1))
    except (ValueError, TypeError):
        page = 1
    limit = 20
    offset = (page - 1) * limit

    if query:
        conversions = Conversion.search(query, from_date, to_date, limit, offset)
    else:
        conversions = Conversion.get_all(limit, offset)

    return jsonify({
        "items": [c.to_dict() for c in conversions],
        "page": page
    })


@main_bp.route("/api/history/<conversion_id>")
def get_history_detail(conversion_id):
    conversion = Conversion.get_by_id(conversion_id)
    if not conversion:
        return jsonify({"error": "Conversion not found"}), 404

    return jsonify(conversion.to_dict(include_full_text=True))


@main_bp.route("/api/history/<conversion_id>", methods=["DELETE"])
def delete_history(conversion_id):
    conversion = Conversion.get_by_id(conversion_id)
    if not conversion:
        return jsonify({"error": "Conversion not found"}), 404

    delete_conversion_files(conversion)
    conversion.delete()

    return jsonify({"success": True})
