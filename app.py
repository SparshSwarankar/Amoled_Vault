from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, flash
import json
import os
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
from collections import Counter
from datetime import datetime, timedelta

app = Flask(__name__)

# Production configuration for Render
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Configuration
UPLOAD_FOLDER = 'static/wallpapers'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
SECRET_CODE = os.environ.get('ADMIN_SECRET', '1234')  # Use environment variable
INSTAGRAM_URL = os.environ.get('INSTAGRAM_URL', 'https://www.instagram.com/amoled_vault/')
DOWNLOAD_NAME_SUFFIX = os.environ.get('DOWNLOAD_SUFFIX', 'Amoled Vault')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_database():
    """Load wallpaper metadata from JSON file"""
    try:
        with open('database.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"wallpapers": [], "downloads": []}

def save_database(data):
    """Save wallpaper metadata to JSON file"""
    with open('database.json', 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/')
def index():
    """Homepage with carousel and gallery"""
    db = load_database()
    wallpapers = db.get('wallpapers', [])
    
    # Get device type filter from query params
    device_type = request.args.get('device', 'mobile')
    
    # Filter wallpapers by device type
    if device_type in ['mobile', 'pc']:
        wallpapers = [w for w in wallpapers if w.get('device_type', 'mobile') == device_type]
    
    # Get categories for the filtered wallpapers
    categories = list(set([w['category'] for w in wallpapers]))
    categories.sort()
    
    # Get latest 5 wallpapers for carousel
    latest_wallpapers = sorted(wallpapers, key=lambda x: x.get('upload_date', ''), reverse=True)[:5]
    
    # Get popular wallpapers (top 6 by download count)
    popular_wallpapers = sorted(wallpapers, key=lambda x: x.get('download_count', 0), reverse=True)[:6]
    
    return render_template('index.html', 
                         wallpapers=wallpapers, 
                         categories=categories,
                         latest_wallpapers=latest_wallpapers,
                         popular_wallpapers=popular_wallpapers,
                         instagram_url=INSTAGRAM_URL,
                         current_device=device_type)

@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/api/wallpapers')
def api_wallpapers():
    """API endpoint to get wallpapers (for AJAX filtering)"""
    db = load_database()
    category = request.args.get('category', 'all')
    device_type = request.args.get('device', 'mobile')
    search = request.args.get('search', '').lower()
    
    wallpapers = db.get('wallpapers', [])
    
    # Filter by device type
    if device_type in ['mobile', 'pc']:
        wallpapers = [w for w in wallpapers if w.get('device_type', 'mobile') == device_type]
    
    # Filter by category
    if category != 'all':
        wallpapers = [w for w in wallpapers if w['category'].lower() == category.lower()]
    
    # Filter by search term
    if search:
        wallpapers = [w for w in wallpapers if search in w['title'].lower() or search in w['category'].lower()]
    
    return jsonify(wallpapers)

@app.route('/api/activity')
def api_activity():
    """API endpoint to get recent activity (downloads/uploads) for analytics page"""
    db = load_database()
    wallpapers = db.get('wallpapers', [])
    downloads = db.get('downloads', [])
    activity_type = request.args.get('type', 'all')
    device_type = request.args.get('device', 'mobile')

    # Filter wallpapers by device type
    if device_type in ['mobile', 'pc']:
        filtered_wallpapers = [w for w in wallpapers if w.get('device_type', 'mobile') == device_type]
    else:
        filtered_wallpapers = wallpapers
    wallpaper_ids = {w['id'] for w in filtered_wallpapers}

    # Collect download activity
    activity = []
    if activity_type in ['all', 'downloads']:
        for d in downloads:
            if d['wallpaper_id'] in wallpaper_ids:
                w = next((w for w in filtered_wallpapers if w['id'] == d['wallpaper_id']), None)
                if w:
                    activity.append({
                        'type': 'download',
                        'title': w['title'],
                        'filename': w['filename'],
                        'date': d['timestamp'],
                    })

    # Collect upload activity
    if activity_type in ['all', 'uploads']:
        for w in filtered_wallpapers:
            if 'upload_date' in w:
                activity.append({
                    'type': 'upload',
                    'title': w['title'],
                    'filename': w['filename'],
                    'date': w['upload_date'],
                })

    activity.sort(key=lambda x: x['date'], reverse=True)
    activity = activity[:30]
    return jsonify(activity)

@app.route('/download/<filename>')
def download_wallpaper(filename):
    """Serve wallpaper files for download"""
    try:
        db = load_database()
        wallpapers = db.get('wallpapers', [])
        wallpaper = next((w for w in wallpapers if w['filename'] == filename), None)
        if not wallpaper:
            return "File not found", 404
        category = wallpaper.get('category', 'wallpaper')
        ext = filename.split('.')[-1]
        custom_name = f"{category}-{DOWNLOAD_NAME_SUFFIX}.{ext}"
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True, download_name=custom_name)
    except FileNotFoundError:
        return "File not found", 404

@app.route('/upload')
def upload_page():
    """Secret upload page - requires secret parameter"""
    secret = request.args.get('secret')
    if secret != SECRET_CODE:
        return render_template('upload.html', unauthorized=True)
    
    return render_template('upload.html', authorized=True)

@app.route('/upload', methods=['POST'])
def upload_wallpaper():
    """Handle multiple wallpaper uploads"""
    secret = request.args.get('secret')
    if secret != SECRET_CODE:
        return "Unauthorized", 403
    
    if 'files' not in request.files:
        flash('No files selected')
        return redirect(url_for('upload_page', secret=secret))
    
    files = request.files.getlist('files')
    title_base = request.form.get('title', '').strip()
    category = request.form.get('category', '').strip()
    device_type = request.form.get('device_type', '').strip()
    
    if not files or all(file.filename == '' for file in files):
        flash('No files selected')
        return redirect(url_for('upload_page', secret=secret))
    
    if not title_base or not category or not device_type:
        flash('Title, category, and device type are required')
        return redirect(url_for('upload_page', secret=secret))
    
    if device_type not in ['mobile', 'pc']:
        flash('Invalid device type')
        return redirect(url_for('upload_page', secret=secret))
    
    uploaded_count = 0
    failed_count = 0
    
    db = load_database()
    
    for i, file in enumerate(files):
        if file and allowed_file(file.filename):
            try:
                file_extension = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
                
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                
                if len(files) > 1:
                    file_title = f"{title_base} #{i + 1}"
                else:
                    file_title = title_base
                
                new_wallpaper = {
                    'id': str(uuid.uuid4()),
                    'title': file_title,
                    'category': category,
                    'device_type': device_type,
                    'filename': unique_filename,
                    'upload_date': datetime.now().isoformat(),
                    'download_count': 0
                }
                
                db['wallpapers'].append(new_wallpaper)
                uploaded_count += 1
                
            except Exception as e:
                print(f"Error uploading file {file.filename}: {e}")
                failed_count += 1
        else:
            failed_count += 1
    
    save_database(db)
    
    if uploaded_count > 0 and failed_count == 0:
        flash(f'Successfully uploaded {uploaded_count} wallpaper(s)!')
    elif uploaded_count > 0 and failed_count > 0:
        flash(f'Uploaded {uploaded_count} wallpaper(s), {failed_count} failed. Check file types.')
    else:
        flash('All uploads failed. Please check file types and try again.')
    
    return redirect(url_for('upload_page', secret=secret))

@app.route('/api/track-download', methods=['POST'])
def track_download():
    """Track wallpaper download"""
    data = request.get_json()
    wallpaper_id = data.get('wallpaper_id')
    
    if not wallpaper_id:
        return jsonify({'error': 'Missing wallpaper_id'}), 400
    
    db = load_database()
    
    if 'downloads' not in db:
        db['downloads'] = []
    
    download_record = {
        'wallpaper_id': wallpaper_id,
        'timestamp': datetime.now().isoformat(),
        'ip': request.remote_addr
    }
    
    db['downloads'].append(download_record)
    
    for wallpaper in db['wallpapers']:
        if wallpaper['id'] == wallpaper_id:
            wallpaper['download_count'] = wallpaper.get('download_count', 0) + 1
            break
    
    save_database(db)
    return jsonify({'success': True})

@app.route('/api/popular')
def get_popular_wallpapers():
    """Get popular wallpapers based on download count"""
    db = load_database()
    wallpapers = db.get('wallpapers', [])
    device_type = request.args.get('device', 'mobile')
    
    if device_type in ['mobile', 'pc']:
        wallpapers = [w for w in wallpapers if w.get('device_type', 'mobile') == device_type]
    
    popular_wallpapers = sorted(
        wallpapers, 
        key=lambda x: x.get('download_count', 0), 
        reverse=True
    )[:6]
    
    return jsonify(popular_wallpapers)

@app.route('/api/stats')
def get_download_stats():
    """Get download statistics"""
    db = load_database()
    downloads = db.get('downloads', [])
    wallpapers = db.get('wallpapers', [])
    device_type = request.args.get('device', 'mobile')
    
    if device_type in ['mobile', 'pc']:
        filtered_wallpapers = [w for w in wallpapers if w.get('device_type', 'mobile') == device_type]
    else:
        filtered_wallpapers = wallpapers
    
    filtered_downloads = []
    wallpaper_ids = [w['id'] for w in filtered_wallpapers]
    for download in downloads:
        if download['wallpaper_id'] in wallpaper_ids:
            filtered_downloads.append(download)
    
    total_downloads = len(filtered_downloads)
    total_wallpapers = len(filtered_wallpapers)
    
    yesterday = datetime.now() - timedelta(days=1)
    recent_downloads = [
        d for d in filtered_downloads 
        if datetime.fromisoformat(d['timestamp']) > yesterday
    ]
    
    category_downloads = Counter()
    for download in filtered_downloads:
        for wallpaper in filtered_wallpapers:
            if wallpaper['id'] == download['wallpaper_id']:
                category_downloads[wallpaper['category']] += 1
                break
    
    stats = {
        'total_downloads': total_downloads,
        'total_wallpapers': total_wallpapers,
        'downloads_24h': len(recent_downloads),
        'popular_categories': dict(category_downloads.most_common(5))
    }
    
    return jsonify(stats)

@app.route('/admin/analytics')
def admin_analytics():
    """Admin analytics dashboard"""
    secret = request.args.get('secret')
    if secret != SECRET_CODE:
        return "Unauthorized", 403
    
    return render_template('analytics.html', authorized=True)

@app.route('/api/delete-wallpaper/<wallpaper_id>', methods=['DELETE'])
def delete_wallpaper(wallpaper_id):
    """Delete a wallpaper by ID"""
    try:
        db = load_database()
        
        wallpaper_to_delete = None
        for wallpaper in db['wallpapers']:
            if wallpaper['id'] == wallpaper_id:
                wallpaper_to_delete = wallpaper
                break
        
        if not wallpaper_to_delete:
            return jsonify({'error': 'Wallpaper not found'}), 404
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], wallpaper_to_delete['filename'])
        if os.path.exists(file_path):
            os.remove(file_path)
        
        db['wallpapers'] = [w for w in db['wallpapers'] if w['id'] != wallpaper_id]
        
        if 'downloads' in db:
            db['downloads'] = [d for d in db['downloads'] if d['wallpaper_id'] != wallpaper_id]
        
        save_database(db)
        
        return jsonify({
            'success': True, 
            'message': f'Wallpaper "{wallpaper_to_delete["title"]}" deleted successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    # For local development
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # For production (Render)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
