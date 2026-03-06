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
        full_name = request.form.get('full_name')
        age = request.form.get('age')
        address = request.form.get('address')
        photo = request.files.get('photo')

        if photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo.save(photo_path)

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
        else:
            flash('Please upload a valid photo (jpg, jpeg, png)')

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
    data = request.get_json()
    image_data = data['image'].split(',')[1]
    image_bytes = base64.b64decode(image_data)
    image = Image.open(BytesIO(image_bytes)).convert('RGB')
    frame = np.array(image)

    # Get face locations and encodings from camera frame
    face_locations = face_recognition.face_locations(frame)
    face_encodings = face_recognition.face_encodings(frame, face_locations)

    if not face_encodings:
        return {'status': 'no_face', 'message': 'No face detected. Please try again.'}

    # Load all registered seniors and their face encodings
    seniors = Senior.query.all()
    for senior in seniors:
        try:
            known_image = face_recognition.load_image_file(senior.photo_path)
            known_encodings = face_recognition.face_encodings(known_image)
            if not known_encodings:
                continue
            known_encoding = known_encodings[0]

            # Compare with camera face
            results = face_recognition.compare_faces([known_encoding], face_encodings[0], tolerance=0.5)
            if results[0]:
                # Match found — record transaction
                transaction = Transaction(
                    senior_id=senior.id,
                    amount=500.00,
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

if __name__ == '__main__':
    app.run(debug=True)