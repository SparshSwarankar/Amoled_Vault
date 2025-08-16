from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, flash, make_response
import os
import uuid
from datetime import datetime, timedelta
from collections import Counter
from supabase import create_client, Client

app = Flask(__name__)

# --- Config -------------------------------------------------------------------
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-change-in-production")

UPLOAD_FOLDER = "static/wallpapers"  # only used if you still keep local files (not needed for Supabase)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
SECRET_CODE = os.environ.get("ADMIN_SECRET", "7017")
INSTAGRAM_URL = os.environ.get("INSTAGRAM_URL", "https://www.instagram.com/amoled_vault/")
DOWNLOAD_NAME_SUFFIX = os.environ.get("DOWNLOAD_SUFFIX", "Amoled Vault")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Supabase -----------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://pasetesvrkifdxfolcoq.supabase.co")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_ROLE",  # prefer service role in backend
    os.environ.get("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBhc2V0ZXN2cmtpZmR4Zm9sY29xIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQ5MzM3ODksImV4cCI6MjA3MDUwOTc4OX0.m9X2b6t416IZQXJStpI0GbexsOiqlBM8ITjDPxTrEYM")
)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET_NAME = "wallpapers"  # must exist and be public

# --- Helpers ------------------------------------------------------------------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def public_storage_url(path: str) -> str:
    """
    Build the public URL regardless of SDK return shape.
    Requires: the bucket is public.
    """
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{path}"

# --- Pages --------------------------------------------------------------------
@app.route("/")
def index():
    """
    Homepage with carousel and gallery (data from Supabase instead of local JSON)
    """
    device_type = request.args.get("device", "mobile")

    # Base filter
    query = supabase.table("wallpapers").select("*")
    if device_type in ["mobile", "pc"]:
        query = query.eq("device_type", device_type)

    # Pull all
    result = query.execute()
    wallpapers = result.data or []

    # Build categories dynamically
    categories = sorted(list({w.get("category", "") for w in wallpapers if w.get("category")}))

    # Latest 5 (by upload_date)
    latest_wallpapers = sorted(
        wallpapers,
        key=lambda x: x.get("upload_date") or "",
        reverse=True
    )[:5]

    # Popular top 6 (by download_count)
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
    # Serve from project root if present
    try:
        return send_from_directory(".", "manifest.json")
    except Exception:
        return jsonify({"name": "Amoled Vault", "start_url": "/", "display": "standalone"})

# --- API: Wallpapers (filter/search) ------------------------------------------
@app.route("/api/wallpapers")
def api_wallpapers():
    category = request.args.get("category", "all")
    device_type = request.args.get("device", "mobile")
    search = (request.args.get("search") or "").strip().lower()

    q = supabase.table("wallpapers").select("*")

    if device_type in ["mobile", "pc"]:
        q = q.eq("device_type", device_type)

    if category != "all":
        q = q.ilike("category", category)  # case-insensitive

    res = q.execute()
    wallpapers = res.data or []

    if search:
        s = search
        wallpapers = [
            w for w in wallpapers
            if s in (w.get("title", "").lower()) or s in (w.get("category", "").lower())
        ]

    return jsonify(wallpapers)

# --- API: Activity feed (uploads + downloads) --------------------------------
@app.route("/api/activity")
def api_activity():
    activity_type = request.args.get("type", "all")
    device_type = request.args.get("device", "mobile")

    # Get filtered wallpapers
    wq = supabase.table("wallpapers").select("*")
    if device_type in ["mobile", "pc"]:
        wq = wq.eq("device_type", device_type)
    wres = wq.execute()
    wallpapers = wres.data or []
    by_id = {w["id"]: w for w in wallpapers}
    wallpaper_ids = set(by_id.keys())

    activity = []

    # uploads from wallpapers.upload_date
    if activity_type in ["all", "uploads"]:
        for w in wallpapers:
            if w.get("upload_date"):
                activity.append({
                    "type": "upload",
                    "title": w.get("title"),
                    "filename": w.get("filename"),
                    "date": w.get("upload_date")
                })

    # downloads from downloads table
    if activity_type in ["all", "downloads"]:
        dres = supabase.table("downloads").select("*").order("timestamp", desc=True).limit(200).execute()
        downloads = dres.data or []
        for d in downloads:
            wid = d.get("wallpaper_id")
            if wid in wallpaper_ids:
                w = by_id.get(wid)
                activity.append({
                    "type": "download",
                    "title": w.get("title") if w else None,
                    "filename": w.get("filename") if w else None,
                    "date": d.get("timestamp")
                })

    activity.sort(key=lambda x: x.get("date") or "", reverse=True)
    return jsonify(activity[:30])

# --- Download -----------------------------------------------------------------
@app.route("/download/<filename>")
def download_wallpaper(filename):
    """
    Redirect to Supabase public URL with a custom "download=" filename hint.
    """
    # Find wallpaper by filename
    res = supabase.table("wallpapers").select("*").eq("filename", filename).limit(1).execute()
    rows = res.data or []
    if not rows:
        return "File not found", 404

    w = rows[0]
    path = w.get("file_path") or f"{w.get('device_type','mobile')}/{filename}"
    category = w.get("category", "wallpaper")
    ext = filename.split(".")[-1]
    custom_name = f"{category}-{DOWNLOAD_NAME_SUFFIX}.{ext}"

    # Public URL + download param (forces name)
    url = f"{public_storage_url(path)}?download={custom_name}"

    # NOTE: We redirect rather than streaming bytes
    return redirect(url, code=302)

# --- Uploads to Supabase Storage + row insert --------------------------------
@app.route("/upload", methods=["POST"])
def upload_wallpaper():
    """
    Handle multiple wallpaper uploads to Supabase Storage + insert rows.
    """
    secret = request.args.get("secret")
    if secret != SECRET_CODE:
        return "Unauthorized", 403

    if "files" not in request.files:
        flash("No files selected")
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

    if device_type not in ["mobile", "pc"]:
        flash("Invalid device type")
        return redirect(url_for("upload_page", secret=secret))

    uploaded_count = 0
    failed_count = 0

    for i, file in enumerate(files):
        if not (file and allowed_file(file.filename)):
            failed_count += 1
            continue

        try:
            file_extension = file.filename.rsplit(".", 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
            file_path = f"{device_type}/{unique_filename}"

            # Read bytes for upload
            file_bytes = file.read()

            # Upload (upsert=False to avoid accidental overwrite; set True if you want)
            supabase.storage.from_(BUCKET_NAME).upload(
                file_path,
                file_bytes,
                file_options={"contentType": file.mimetype, "upsert": False}
            )

            public_url = public_storage_url(file_path)

            file_title = f"{title_base} #{i + 1}" if len(files) > 1 else title_base

            supabase.table("wallpapers").insert({
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

            uploaded_count += 1

        except Exception as e:
            print(f"Error uploading file {file.filename}: {e}")
            failed_count += 1

    if uploaded_count > 0 and failed_count == 0:
        flash(f"Successfully uploaded {uploaded_count} wallpaper(s)!")
    elif uploaded_count > 0 and failed_count > 0:
        flash(f"Uploaded {uploaded_count} wallpaper(s), {failed_count} failed.")
    else:
        flash("All uploads failed. Please check file types.")

    return redirect(url_for("upload_page", secret=secret))

# --- Track download -----------------------------------------------------------
@app.route("/api/track-download", methods=["POST"])
def track_download():
    """
    Record a download row and increment wallpaper.download_count.
    """
    try:
        data = request.get_json(silent=True) or {}
        wallpaper_id = data.get("wallpaper_id")
        if not wallpaper_id:
            return jsonify({"error": "Missing wallpaper_id"}), 400

        # Insert download row
        supabase.table("downloads").insert({
            "wallpaper_id": wallpaper_id,
            "ip": request.remote_addr
        }).execute()

        # Get current count
        current = supabase.table("wallpapers").select("download_count").eq("id", wallpaper_id).limit(1).execute()
        count = 0
        if current.data:
            count = int(current.data[0].get("download_count") or 0) + 1

        supabase.table("wallpapers").update({"download_count": count}).eq("id", wallpaper_id).execute()

        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Error tracking download: {e}")
        return jsonify({"error": "Failed to track download"}), 500

# --- Popular ------------------------------------------------------------------
@app.route("/api/popular")
def get_popular_wallpapers():
    device_type = request.args.get("device", "mobile")
    q = supabase.table("wallpapers").select("*")
    if device_type in ["mobile", "pc"]:
        q = q.eq("device_type", device_type)
    res = q.execute()
    wallpapers = res.data or []
    popular_wallpapers = sorted(
        wallpapers, key=lambda x: int(x.get("download_count") or 0), reverse=True
    )[:6]
    return jsonify(popular_wallpapers)

# --- Stats --------------------------------------------------------------------
@app.route("/api/stats")
def get_download_stats():
    device_type = request.args.get("device", "mobile")

    # Wallpapers (filtered)
    wq = supabase.table("wallpapers").select("*")
    if device_type in ["mobile", "pc"]:
        wq = wq.eq("device_type", device_type)
    wres = wq.execute()
    wallpapers = wres.data or []
    wallpaper_ids = {w["id"] for w in wallpapers}

    # Downloads (recent window)
    dres = supabase.table("downloads").select("*").order("timestamp", desc=True).limit(1000).execute()
    downloads = [d for d in (dres.data or []) if d.get("wallpaper_id") in wallpaper_ids]

    total_downloads = len(downloads)
    total_wallpapers = len(wallpapers)

    # last 24h
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_downloads = [
        d for d in downloads
        if d.get("timestamp") and datetime.fromisoformat(str(d["timestamp"]).replace("Z","")) > yesterday
    ]

    # category counts
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

# --- Admin pages --------------------------------------------------------------
@app.route("/admin/analytics")
def admin_analytics():
    secret = request.args.get("secret")
    if secret != SECRET_CODE:
        return "Unauthorized", 403
    return render_template("analytics.html", authorized=True)

@app.route("/admin/upload")
def upload_page():
    """
    Optional: If you already have templates/upload.html it will render.
    Otherwise show a tiny fallback form so /upload redirects won't 404.
    """
    secret = request.args.get("secret")
    if secret != SECRET_CODE:
        return "Unauthorized", 403
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

# --- Delete wallpaper ---------------------------------------------------------
@app.route("/api/delete-wallpaper/<wallpaper_id>", methods=["DELETE"])
def delete_wallpaper(wallpaper_id):
    try:
        # Fetch wallpaper row
        wres = supabase.table("wallpapers").select("*").eq("id", wallpaper_id).limit(1).execute()
        rows = wres.data or []
        if not rows:
            return jsonify({"error": "Wallpaper not found"}), 404

        w = rows[0]
        file_path = w.get("file_path")
        # Delete storage object (best effort)
        if file_path:
            try:
                supabase.storage.from_(BUCKET_NAME).remove([file_path])
            except Exception as stg_err:
                print(f"Storage remove error: {stg_err}")

        # Delete related downloads
        supabase.table("downloads").delete().eq("wallpaper_id", wallpaper_id).execute()
        # Delete wallpaper row
        supabase.table("wallpapers").delete().eq("id", wallpaper_id).execute()

        return jsonify({"success": True, "message": f'Wallpaper "{w.get("title")}" deleted successfully'})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Health -------------------------------------------------------------------
@app.route("/health")
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

# --- Entrypoint ---------------------------------------------------------------
if __name__ == "__main__":
    # Local dev only. On Render use Gunicorn: `gunicorn app:app`
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
