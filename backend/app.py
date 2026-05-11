import os
import traceback

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

from analyzer import AcademicAnalyzer

# =========================================================
# LOAD ENV
# =========================================================

load_dotenv()

# =========================================================
# PATHS
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FRONTEND_FOLDER = os.path.join(BASE_DIR, "../frontend")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

REPORTS_FOLDER = os.path.join(BASE_DIR, "reports")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)

# =========================================================
# APP
# =========================================================

app = Flask(
    __name__,
    static_folder=FRONTEND_FOLDER,
    static_url_path=""
)

CORS(app, resources={r"/*": {"origins": "*"}})

app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# =========================================================
# GLOBAL FILE PATHS
# =========================================================

LAST_GRADEBOOK_PATH = None
LAST_ANALYTICS_PATH = None

# =========================================================
# FRONTEND ROUTES
# =========================================================

@app.route("/")
def home():
    return send_file(
        os.path.join(
            FRONTEND_FOLDER,
            "login.html"
        )
    )


@app.route("/dashboard")
def dashboard():
    return send_file(
        os.path.join(
            FRONTEND_FOLDER,
            "dashboard.html"
        )
    )


@app.route("/<path:path>")
def serve_frontend(path):

    if path.startswith("api"):
        return jsonify({
            "error": "Not found"
        }), 404

    full_path = os.path.join(
        FRONTEND_FOLDER,
        path
    )

    if os.path.exists(full_path):
        return send_file(full_path)

    return jsonify({
        "error": "File not found"
    }), 404

# =========================================================
# HEALTH
# =========================================================

@app.route("/api/health", methods=["GET"])
def health():

    return jsonify({
        "status": "ok",
        "message": "Academic Analytics System Running"
    })

# =========================================================
# ANALYZE
# =========================================================

@app.route("/api/analyze", methods=["POST"])
def analyze_api():

    global LAST_GRADEBOOK_PATH
    global LAST_ANALYTICS_PATH

    try:

        # -------------------------------------------------
        # VALIDATE FILES
        # -------------------------------------------------

        if "gradebook" not in request.files:
            return jsonify({
                "error": "Gradebook file missing"
            }), 400

        if "analytics" not in request.files:
            return jsonify({
                "error": "Analytics file missing"
            }), 400

        gradebook_file = request.files["gradebook"]

        analytics_file = request.files["analytics"]

        if gradebook_file.filename == "":
            return jsonify({
                "error": "Gradebook file is empty"
            }), 400

        if analytics_file.filename == "":
            return jsonify({
                "error": "Analytics file is empty"
            }), 400

        # -------------------------------------------------
        # EXTENSIONS
        # -------------------------------------------------

        gb_ext = os.path.splitext(
            gradebook_file.filename
        )[1].lower()

        an_ext = os.path.splitext(
            analytics_file.filename
        )[1].lower()

        allowed_extensions = [
            ".csv",
            ".xls",
            ".xlsx"
        ]

        if gb_ext not in allowed_extensions:
            return jsonify({
                "error": f"Unsupported Gradebook format: {gb_ext}"
            }), 400

        if an_ext not in allowed_extensions:
            return jsonify({
                "error": f"Unsupported Analytics format: {an_ext}"
            }), 400

        # -------------------------------------------------
        # SAVE FILES
        # -------------------------------------------------

        gradebook_path = os.path.join(
            UPLOAD_FOLDER,
            f"gradebook{gb_ext}"
        )

        analytics_path = os.path.join(
            UPLOAD_FOLDER,
            f"analytics{an_ext}"
        )

        gradebook_file.save(gradebook_path)

        analytics_file.save(analytics_path)

        LAST_GRADEBOOK_PATH = gradebook_path
        LAST_ANALYTICS_PATH = analytics_path

        # -------------------------------------------------
        # ANALYZE
        # -------------------------------------------------

        analyzer = AcademicAnalyzer(
            gradebook_path,
            analytics_path
        )

        report = analyzer.generate_full_report()

        return jsonify(report)

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error": str(e)
        }), 500

# =========================================================
# DOWNLOAD REPORT
# =========================================================

@app.route("/api/download-report", methods=["POST"])
def download_report():

    global LAST_GRADEBOOK_PATH
    global LAST_ANALYTICS_PATH

    try:

        if not LAST_GRADEBOOK_PATH:
            return jsonify({
                "error": "Gradebook file not found"
            }), 400

        if not LAST_ANALYTICS_PATH:
            return jsonify({
                "error": "Analytics file not found"
            }), 400

        analyzer = AcademicAnalyzer(
            LAST_GRADEBOOK_PATH,
            LAST_ANALYTICS_PATH
        )

        report_path = analyzer.export_excel_report(
            REPORTS_FOLDER
        )

        return send_file(
            report_path,
            as_attachment=True,
            download_name="academic_analytics_report.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error": f"Download error: {str(e)}"
        }), 500

# =========================================================
# SEND EMAIL
# =========================================================

@app.route("/api/send-email", methods=["POST"])
def send_email():

    global LAST_GRADEBOOK_PATH
    global LAST_ANALYTICS_PATH

    try:

        data = request.get_json()

        required_fields = [
            "student_id",
            "student_name",
            "risk_level",
            "recommendations"
        ]

        for field in required_fields:

            if field not in data:
                return jsonify({
                    "error": f"Missing field: {field}"
                }), 400

        # -------------------------------------------------
        # EMAIL CONFIG
        # -------------------------------------------------

        sender_email = os.environ.get("MAIL_SENDER")

        sender_password = os.environ.get("MAIL_PASSWORD")

        smtp_host = os.environ.get(
            "MAIL_HOST",
            "smtp.gmail.com"
        )

        smtp_port = os.environ.get(
            "MAIL_PORT",
            "587"
        )

        smtp_secure = os.environ.get(
            "MAIL_SECURE",
            "starttls"
        )

        if not sender_email or not sender_password:

            return jsonify({
                "error": "Email configuration missing in .env"
            }), 500

        # -------------------------------------------------
        # VALIDATE FILES
        # -------------------------------------------------

        if not LAST_GRADEBOOK_PATH:
            return jsonify({
                "error": "Gradebook file missing"
            }), 400

        if not LAST_ANALYTICS_PATH:
            return jsonify({
                "error": "Analytics file missing"
            }), 400

        # -------------------------------------------------
        # SEND EMAIL
        # -------------------------------------------------

        analyzer = AcademicAnalyzer(
            LAST_GRADEBOOK_PATH,
            LAST_ANALYTICS_PATH
        )

        success, message = analyzer.send_email_notification(
            data["student_id"],
            data["student_name"],
            data["risk_level"],
            data["recommendations"],
            sender_email,
            sender_password,
            smtp_host,
            smtp_port,
            smtp_secure
        )

        if success:

            return jsonify({
                "message": message
            })

        return jsonify({
            "error": message
        }), 500

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error": f"Email error: {str(e)}"
        }), 500

# =========================================================
# FAVICON
# =========================================================

@app.route("/favicon.ico")
def favicon():
    return "", 204

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )