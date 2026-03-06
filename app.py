import face_recognition
import numpy as np
import base64
from io import BytesIO
from PIL import Image
import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from models import db, Official, Senior, Transaction

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = 'static/faces'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return Official.query.get(int(user_id))

# --- Home ---
@app.route('/')
@login_required
def index():
    senior_count = Senior.query.count()
    transaction_count = Transaction.query.count()
    return render_template('index.html', senior_count=senior_count, transaction_count=transaction_count)

# --- Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        official = Official.query.filter_by(username=username).first()

        if official and check_password_hash(official.password, password):
            login_user(official)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')

# --- Logout ---
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- Register Senior ---
@app.route('/register-senior', methods=['GET', 'POST'])
@login_required
def register_senior():
    if request.method == 'POST':
        import base64, uuid
        from PIL import Image as PILImage
        from io import BytesIO as BytesIO2

        full_name = request.form.get('full_name')
        age = request.form.get('age')
        address = request.form.get('address')
        photo = request.files.get('photo')
        captured_photo = request.form.get('captured_photo')

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        photo_path = None

        # Camera capture mode
        if captured_photo and captured_photo.startswith('data:image'):
            image_data = captured_photo.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            filename = f"capture_{uuid.uuid4().hex}.jpg"
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(photo_path, 'wb') as f:
                f.write(image_bytes)

        # Upload mode
        elif photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo.save(photo_path)

        else:
            flash('Please provide a photo — either upload one or use the camera.')
            return render_template('register_senior.html')

        # Check if face already exists in the system
        seniors = Senior.query.all()
        for existing_senior in seniors:
            try:
                known_image = face_recognition.load_image_file(existing_senior.photo_path)
                known_encodings = face_recognition.face_encodings(known_image)
                if not known_encodings:
                    continue

                new_image = face_recognition.load_image_file(photo_path)
                new_encodings = face_recognition.face_encodings(new_image)
                if not new_encodings:
                    continue

                distance = face_recognition.face_distance([known_encodings[0]], new_encodings[0])[0]
                results = face_recognition.compare_faces([known_encodings[0]], new_encodings[0], tolerance=0.4)

                if results[0] and distance < 0.4:
                    os.remove(photo_path)
                    flash(f'This person is already registered as {existing_senior.full_name}.')
                    return render_template('register_senior.html')
            except Exception:
                continue

        # All checks passed — save senior
        senior = Senior(
            full_name=full_name,
            age=age,
            address=address,
            photo_path=photo_path
        )
        db.session.add(senior)
        db.session.commit()
        flash('Senior registered successfully!')
        return redirect(url_for('index'))

    return render_template('register_senior.html')

# --- View All Seniors ---
@app.route('/seniors')
@login_required
def seniors():
    all_seniors = Senior.query.all()
    return render_template('seniors.html', seniors=all_seniors)

# --- Scan Page ---
@app.route('/scan')
@login_required
def scan():
    return render_template('scan.html')

# --- Face Recognition API ---
@app.route('/recognize', methods=['POST'])
@login_required
def recognize():
    from datetime import datetime, timedelta
    data = request.get_json()
    image_data = data['image'].split(',')[1]
    image_bytes = base64.b64decode(image_data)
    image = Image.open(BytesIO(image_bytes)).convert('RGB')
    frame = np.array(image)

    face_locations = face_recognition.face_locations(frame)
    face_encodings = face_recognition.face_encodings(frame, face_locations)

    if not face_encodings:
        return {'status': 'no_face', 'message': 'No face detected. Please try again.'}

    seniors = Senior.query.all()
    for senior in seniors:
        try:
            known_image = face_recognition.load_image_file(senior.photo_path)
            known_encodings = face_recognition.face_encodings(known_image)
            if not known_encodings:
                continue
            known_encoding = known_encodings[0]

            distance = face_recognition.face_distance([known_encoding], face_encodings[0])[0]
            results = face_recognition.compare_faces([known_encoding], face_encodings[0], tolerance=0.4)

            if results[0] and distance < 0.4:
                now = datetime.now()
                cutoff = now - timedelta(days=90)
                already_claimed = Transaction.query.filter_by(senior_id=senior.id).filter(
                    Transaction.date_released >= cutoff
                ).first()

                if already_claimed:
                    return {
                        'status': 'already_claimed',
                        'message': f'{senior.full_name} has already claimed on {already_claimed.date_released.strftime("%b %d, %Y")}. Next claim available after {(already_claimed.date_released + timedelta(days=90)).strftime("%b %d, %Y")}.'
                    }

                transaction = Transaction(
                    senior_id=senior.id,
                    amount=1500.00,
                    released_by=current_user.name,
                    status='Released'
                )
                db.session.add(transaction)
                db.session.commit()

                return {
                    'status': 'match',
                    'name': senior.full_name,
                    'age': senior.age,
                    'address': senior.address,
                    'photo': senior.photo_path
                }
        except Exception as e:
            continue

    return {'status': 'no_match', 'message': 'Face not recognized. Senior not found.'}

# --- Transaction History ---
@app.route('/history')
@login_required
def history():
    search = request.args.get('search', '')
    date_filter = request.args.get('date', '')

    query = Transaction.query.join(Senior)

    if search:
        query = query.filter(Senior.full_name.ilike(f'%{search}%'))

    if date_filter:
        from datetime import datetime
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d')
            query = query.filter(
                db.func.date(Transaction.date_released) == filter_date.date()
            )
        except:
            pass

    transactions = query.order_by(Transaction.date_released.desc()).all()
    return render_template('history.html', transactions=transactions, search=search, date_filter=date_filter)

# --- Edit Senior ---
@app.route('/seniors/<int:senior_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_senior(senior_id):
    senior = Senior.query.get_or_404(senior_id)
    if request.method == 'POST':
        senior.full_name = request.form.get('full_name')
        senior.age = request.form.get('age')
        senior.address = request.form.get('address')

        photo = request.files.get('photo')
        if photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo.save(photo_path)
            senior.photo_path = photo_path

        db.session.commit()
        flash('Senior updated successfully!')
        return redirect(url_for('seniors'))

    return render_template('edit_senior.html', senior=senior)

# --- Delete Senior ---
@app.route('/seniors/<int:senior_id>/delete', methods=['POST'])
@login_required
def delete_senior(senior_id):
    senior = Senior.query.get_or_404(senior_id)
    Transaction.query.filter_by(senior_id=senior.id).delete()
    db.session.delete(senior)
    db.session.commit()
    flash('Senior removed from the system.', 'info')
    return redirect(url_for('seniors'))

# --- Reset Senior Claim ---
@app.route('/transactions/<int:transaction_id>/reset', methods=['POST'])
@login_required
def reset_claim(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    db.session.delete(transaction)
    db.session.commit()
    flash('Claim reset successfully. Senior can now claim again.')
    return redirect(url_for('history'))

# --- Reset All Claims ---
@app.route('/transactions/reset-all', methods=['POST'])
@login_required
def reset_all_claims():
    Transaction.query.delete()
    db.session.commit()
    flash('All claims have been reset. All seniors can now claim again.')
    return redirect(url_for('history'))

if __name__ == '__main__':
    app.run(debug=True)