# app.py
import os
import uuid
import logging
from datetime import datetime, timedelta
from collections import Counter
from flask import (
    Flask, render_template, request, jsonify, send_from_directory,
    redirect, url_for, flash, make_response
)
from supabase import create_client, Client

# ---------- Basic logging ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("amoled-vault")

# ---------- App + config ----------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-change-in-production")

UPLOAD_FOLDER = "static/wallpapers"   # fallback if you keep local files
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
SECRET_CODE = os.environ.get("ADMIN_SECRET", "7017")
INSTAGRAM_URL = os.environ.get("INSTAGRAM_URL", "https://www.instagram.com/amoled_vault/")
DOWNLOAD_NAME_SUFFIX = os.environ.get("DOWNLOAD_SUFFIX", "Amoled Vault")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- Supabase init (safe) ----------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://pasetesvrkifdxfolcoq.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE")
    or os.environ.get("SUPABASE_ANON_KEY")
    or os.environ.get("SUPABASE_KEY")
    or None
)

def init_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.warning("SUPABASE_URL or SUPABASE_KEY not configured; Supabase client won't be available.")
        return None
    try:
        client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        log.info("Supabase client initialized.")
        return client
    except Exception as e:
        log.exception("Failed to initialize Supabase client: %s", e)
        return None

supabase = init_supabase()
BUCKET_NAME = os.environ.get("BUCKET_NAME", "wallpapers")  # ensure this bucket exists & is public if you plan to use get_public_url

# ---------- Small local JSON fallback (for reads) ----------
# This lets read endpoints work if Supabase is temporarily unavailable.
DB_JSON = "database.json"

def load_database():
    try:
        with open(DB_JSON, "r") as f:
            return json.load(f)
    except Exception:
        return {"wallpapers": [], "downloads": []}

def save_database(data):
    with open(DB_JSON, "w") as f:
        json.dump(data, f, indent=2)

# ---------- Helpers ----------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def public_storage_url(path: str) -> str:
    """
    Construct the conventional public storage URL:
    https://<project>.supabase.co/storage/v1/object/public/<bucket>/<path>
    (This is stable and works when the bucket is public.)
    """
    return f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{BUCKET_NAME}/{path}"

def _res_error(resp):
    """Try to extract an error from Supabase SDK result (many shapes)"""
    if resp is None:
        return "no_response"
    if isinstance(resp, dict):
        if resp.get("error"):
            return resp.get("error")
    if hasattr(resp, "error") and getattr(resp, "error"):
        return getattr(resp, "error")
    # some SDK calls return objects with 'status_code' and 'data'
    return None

# ---------- Routes ----------
@app.route("/")
def index():
    device_type = request.args.get("device", "mobile")
    wallpapers = []

    if supabase:
        try:
            q = supabase.table("wallpapers").select("*")
            if device_type in ("mobile", "pc"):
                q = q.eq("device_type", device_type)
            res = q.execute()
            wallpapers = res.data or []
        except Exception as e:
            log.exception("Error querying supabase wallpapers: %s", e)
            wallpapers = []
    else:
        db = load_database()
        wallpapers = db.get("wallpapers", [])
        if device_type in ("mobile", "pc"):
            wallpapers = [w for w in wallpapers if w.get("device_type", "mobile") == device_type]

    # categories
    categories = sorted({w.get("category", "") for w in wallpapers if w.get("category")})

    # latest 5
    latest_wallpapers = sorted(
        wallpapers, key=lambda x: x.get("upload_date") or "", reverse=True
    )[:5]

    # popular top 6
    popular_wallpapers = sorted(
        wallpapers,
        key=lambda x: int(x.get("download_count") or 0),
        reverse=True
    )[:6]

    return render_template(
        "index.html",
        wallpapers=wallpapers,
        categories=categories,
        latest_wallpapers=latest_wallpapers,
        popular_wallpapers=popular_wallpapers,
        instagram_url=INSTAGRAM_URL,
        current_device=device_type
    )

@app.route("/manifest.json")
def manifest():
    try:
        return send_from_directory(".", "manifest.json")
    except Exception:
        return jsonify({"name": "Amoled Vault", "start_url": "/", "display": "standalone"})

@app.route("/api/wallpapers")
def api_wallpapers():
    category = request.args.get("category", "all")
    device_type = request.args.get("device", "mobile")
    search = (request.args.get("search") or "").strip().lower()

    wallpapers = []
    if supabase:
        try:
            q = supabase.table("wallpapers").select("*")
            if device_type in ("mobile", "pc"):
                q = q.eq("device_type", device_type)
            if category != "all":
                # ilike might require wildcard, but we'll leave as direct filter for simplicity
                q = q.ilike("category", category)
            res = q.execute()
            wallpapers = res.data or []
        except Exception as e:
            log.exception("Error fetching wallpapers from supabase: %s", e)
            wallpapers = []
    else:
        db = load_database()
        wallpapers = db.get("wallpapers", [])
        if device_type in ("mobile", "pc"):
            wallpapers = [w for w in wallpapers if w.get("device_type") == device_type]
        if category != "all":
            wallpapers = [w for w in wallpapers if w.get("category", "").lower() == category.lower()]

    if search:
        s = search
        wallpapers = [w for w in wallpapers if s in (w.get("title","").lower()) or s in (w.get("category","").lower())]

    return jsonify(wallpapers)

@app.route("/api/activity")
def api_activity():
    activity_type = request.args.get("type", "all")
    device_type = request.args.get("device", "mobile")
    activity = []

    wallpapers = []
    if supabase:
        try:
            wq = supabase.table("wallpapers").select("*")
            if device_type in ("mobile","pc"):
                wq = wq.eq("device_type", device_type)
            wres = wq.execute()
            wallpapers = wres.data or []
        except Exception as e:
            log.exception("Error reading wallpapers: %s", e)
            wallpapers = []
    else:
        db = load_database()
        wallpapers = db.get("wallpapers", [])

    by_id = {w["id"]: w for w in wallpapers if w.get("id")}
    wallpaper_ids = set(by_id.keys())

    # uploads
    if activity_type in ("all","uploads"):
        for w in wallpapers:
            if w.get("upload_date"):
                activity.append({"type":"upload","title":w.get("title"),"filename":w.get("filename"),"date":w.get("upload_date")})

    # downloads
    if activity_type in ("all","downloads"):
        if supabase:
            try:
                dres = supabase.table("downloads").select("*").order("timestamp", desc=True).limit(200).execute()
                downloads = dres.data or []
            except Exception as e:
                log.exception("Error reading downloads: %s", e)
                downloads = []
        else:
            db = load_database()
            downloads = db.get("downloads", [])
        for d in downloads:
            wid = d.get("wallpaper_id")
            if wid in wallpaper_ids:
                w = by_id.get(wid)
                activity.append({"type":"download","title":w.get("title") if w else None,"filename":w.get("filename") if w else None,"date": d.get("timestamp")})

    activity.sort(key=lambda x: x.get("date") or "", reverse=True)
    return jsonify(activity[:30])

@app.route("/download/<filename>")
def download_wallpaper(filename):
    # find wallpaper row
    if supabase:
        try:
            res = supabase.table("wallpapers").select("*").eq("filename", filename).limit(1).execute()
            rows = res.data or []
        except Exception as e:
            log.exception("Error fetching wallpaper for download: %s", e)
            rows = []
    else:
        db = load_database()
        rows = [w for w in db.get("wallpapers", []) if w.get("filename") == filename]

    if not rows:
        return "File not found", 404

    w = rows[0]
    path = w.get("file_path") or f"{w.get('device_type','mobile')}/{filename}"
    category = w.get("category", "wallpaper")
    ext = filename.rsplit(".",1)[-1]
    custom_name = f"{category}-{DOWNLOAD_NAME_SUFFIX}.{ext}"

    url = f"{public_storage_url(path)}?download={custom_name}"
    return redirect(url, code=302)

# Combined GET form + POST upload to make /upload usable from browser directly
@app.route("/upload", methods=["GET","POST"])
def upload_wallpaper():
    secret = request.args.get("secret")
    if secret != SECRET_CODE:
        return "Unauthorized", 403

    if request.method == "GET":
        # render template if exists, otherwise fallback HTML
        try:
            return render_template("upload.html", secret=secret)
        except Exception:
            html = f"""
            <html>
            <body style="font-family:sans-serif;padding:24px;">
              <h2>Upload Wallpapers</h2>
              <form action="/upload?secret={secret}" method="post" enctype="multipart/form-data">
                <label>Title: <input name="title" required></label><br><br>
                <label>Category: <input name="category" required></label><br><br>
                <label>Device Type:
                  <select name="device_type" required>
                    <option value="mobile">mobile</option>
                    <option value="pc">pc</option>
                  </select>
                </label><br><br>
                <label>Files: <input type="file" name="files" multiple accept=".png,.jpg,.jpeg,.webp" required></label><br><br>
                <button type="submit">Upload</button>
              </form>
            </body>
            </html>
            """
            resp = make_response(html)
            resp.headers["Content-Type"] = "text/html"
            return resp

    # POST: handle upload
    if "files" not in request.files:
        flash("No files selected")
        return redirect(url_for("upload_page", secret=secret))

    if not supabase:
        log.error("Upload attempted but Supabase client not available.")
        flash("Server is not configured with Supabase. Uploads are disabled.")
        return redirect(url_for("upload_page", secret=secret))

    files = request.files.getlist("files")
    title_base = (request.form.get("title") or "").strip()
    category = (request.form.get("category") or "").strip()
    device_type = (request.form.get("device_type") or "").strip()

    if not files or all(f.filename == "" for f in files):
        flash("No files selected")
        return redirect(url_for("upload_page", secret=secret))

    if not title_base or not category or not device_type:
        flash("Title, category, and device type are required")
        return redirect(url_for("upload_page", secret=secret))

    if device_type not in ("mobile","pc"):
        flash("Invalid device type")
        return redirect(url_for("upload_page", secret=secret))

    uploaded_count = 0
    failed_count = 0

    for i, file in enumerate(files):
        if not (file and allowed_file(file.filename)):
            failed_count += 1
            continue
        try:
            ext = file.filename.rsplit(".",1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            file_path = f"{device_type}/{unique_filename}"
            # read bytes
            file_bytes = file.read()

            # Upload via Supabase storage (use named args to be robust)
            try:
                up_res = supabase.storage.from_(BUCKET_NAME).upload(
                    file=file_bytes,
                    path=file_path,
                    file_options={"content-type": file.mimetype, "upsert": "false"}
                )
            except TypeError:
                # some older/newer SDK shapes accept positional args - try fallback
                up_res = supabase.storage.from_(BUCKET_NAME).upload(file_path, file_bytes, {"content-type": file.mimetype})

            err = _res_error(up_res)
            if err:
                log.error("Storage upload error for %s: %s", file.filename, err)
                failed_count += 1
                continue

            public_url = public_storage_url(file_path)

            file_title = f"{title_base} #{i+1}" if len(files) > 1 else title_base

            ins_res = supabase.table("wallpapers").insert({
                "id": str(uuid.uuid4()),
                "title": file_title,
                "category": category,
                "device_type": device_type,
                "filename": unique_filename,
                "file_path": file_path,
                "file_url": public_url,
                "upload_date": datetime.utcnow().isoformat(),
                "download_count": 0
            }).execute()
            if _res_error(ins_res):
                log.error("DB insert error for %s: %s", unique_filename, _res_error(ins_res))
                failed_count += 1
                continue

            uploaded_count += 1

        except Exception as e:
            log.exception("Exception uploading file %s: %s", getattr(file, "filename", "<unknown>"), e)
            failed_count += 1

    if uploaded_count > 0 and failed_count == 0:
        flash(f"Successfully uploaded {uploaded_count} wallpaper(s)!")
    elif uploaded_count > 0 and failed_count > 0:
        flash(f"Uploaded {uploaded_count} wallpaper(s), {failed_count} failed.")
    else:
        flash("All uploads failed. Please check file types and server logs.")

    return redirect(url_for("upload_page", secret=secret))

# admin upload route (keeps compatibility)
@app.route("/admin/upload")
def upload_page():
    secret = request.args.get("secret")
    if secret != SECRET_CODE:
        return "Unauthorized", 403
    try:
        return render_template("upload.html", secret=secret)
    except Exception:
        # fallback to the same small form used above
        return redirect(url_for("upload", secret=secret))

@app.route("/api/track-download", methods=["POST"])
def track_download():
    try:
        data = request.get_json(silent=True) or {}
        wallpaper_id = data.get("wallpaper_id")
        if not wallpaper_id:
            return jsonify({"error": "Missing wallpaper_id"}), 400

        if not supabase:
            return jsonify({"error": "Server not configured with Supabase"}), 500

        supabase.table("downloads").insert({
            "wallpaper_id": wallpaper_id,
            "ip": request.remote_addr
        }).execute()

        current = supabase.table("wallpapers").select("download_count").eq("id", wallpaper_id).limit(1).execute()
        count = 0
        if current.data:
            count = int(current.data[0].get("download_count") or 0) + 1

        supabase.table("wallpapers").update({"download_count": count}).eq("id", wallpaper_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        log.exception("Error tracking download: %s", e)
        return jsonify({"error": "Failed to track download"}), 500

@app.route("/api/popular")
def get_popular_wallpapers():
    device_type = request.args.get("device", "mobile")
    wallpapers = []
    if supabase:
        try:
            q = supabase.table("wallpapers").select("*")
            if device_type in ("mobile","pc"):
                q = q.eq("device_type", device_type)
            res = q.execute()
            wallpapers = res.data or []
        except Exception as e:
            log.exception("Error fetching popular wallpapers: %s", e)
            wallpapers = []
    else:
        db = load_database()
        wallpapers = db.get("wallpapers", [])
        if device_type in ("mobile","pc"):
            wallpapers = [w for w in wallpapers if w.get("device_type")==device_type]

    popular_wallpapers = sorted(wallpapers, key=lambda x: int(x.get("download_count") or 0), reverse=True)[:6]
    return jsonify(popular_wallpapers)

@app.route("/api/stats")
def get_download_stats():
    device_type = request.args.get("device", "mobile")
    wallpapers = []
    if supabase:
        try:
            wq = supabase.table("wallpapers").select("*")
            if device_type in ("mobile","pc"):
                wq = wq.eq("device_type", device_type)
            wres = wq.execute()
            wallpapers = wres.data or []
        except Exception as e:
            log.exception("Error fetching wallpapers for stats: %s", e)
            wallpapers = []
    else:
        db = load_database()
        wallpapers = db.get("wallpapers", [])

    wallpaper_ids = {w["id"] for w in wallpapers if w.get("id")}
    downloads = []
    if supabase:
        try:
            dres = supabase.table("downloads").select("*").order("timestamp", desc=True).limit(1000).execute()
            downloads = [d for d in (dres.data or []) if d.get("wallpaper_id") in wallpaper_ids]
        except Exception as e:
            log.exception("Error fetching downloads: %s", e)
            downloads = []
    else:
        db = load_database()
        downloads = [d for d in db.get("downloads", []) if d.get("wallpaper_id") in wallpaper_ids]

    total_downloads = len(downloads)
    total_wallpapers = len(wallpapers)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_downloads = [
        d for d in downloads
        if d.get("timestamp") and datetime.fromisoformat(str(d["timestamp"]).replace("Z","")) > yesterday
    ]

    by_id = {w["id"]: w for w in wallpapers}
    cat_counts = Counter()
    for d in downloads:
        w = by_id.get(d.get("wallpaper_id"))
        if w:
            cat_counts[w.get("category", "uncategorized")] += 1

    stats = {
        "total_downloads": total_downloads,
        "total_wallpapers": total_wallpapers,
        "downloads_24h": len(recent_downloads),
        "popular_categories": dict(cat_counts.most_common(5))
    }
    return jsonify(stats)

@app.route("/api/delete-wallpaper/<wallpaper_id>", methods=["DELETE"])
def delete_wallpaper(wallpaper_id):
    try:
        if not supabase:
            return jsonify({"error":"Server not configured with Supabase"}), 500

        wres = supabase.table("wallpapers").select("*").eq("id", wallpaper_id).limit(1).execute()
        rows = wres.data or []
        if not rows:
            return jsonify({"error":"Wallpaper not found"}), 404
        w = rows[0]
        file_path = w.get("file_path")
        if file_path:
            try:
                supabase.storage.from_(BUCKET_NAME).remove([file_path])
            except Exception as stg_e:
                log.warning("Storage remove error (best-effort): %s", stg_e)
        supabase.table("downloads").delete().eq("wallpaper_id", wallpaper_id).execute()
        supabase.table("wallpapers").delete().eq("id", wallpaper_id).execute()
        return jsonify({"success": True, "message": f'Wallpaper \"{w.get("title")}\" deleted successfully'})
    except Exception as e:
        log.exception("Error deleting wallpaper: %s", e)
        return jsonify({"error": str(e)}), 500

@app.route("/admin/analytics")
def admin_analytics():
    secret = request.args.get("secret")
    if secret != SECRET_CODE:
        return "Unauthorized", 403
    return render_template("analytics.html", authorized=True)

@app.route("/health")
def health_check():
    return jsonify({"status":"healthy", "timestamp": datetime.utcnow().isoformat()})

# ---------- Entrypoint ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
