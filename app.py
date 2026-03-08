import json

import face_recognition
import numpy as np
import base64
import uuid as uuid_module
import os
from io import BytesIO
from PIL import Image
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from models import db, Official, Senior, Transaction
from blink import detect_blink as check_blink

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
                if existing_senior.face_encoding:
                    import json
                    known_encoding = np.array(json.loads(existing_senior.face_encoding))
                else:
                    known_image = face_recognition.load_image_file(existing_senior.photo_path)
                    known_encodings = face_recognition.face_encodings(known_image)
                    if not known_encodings:
                        continue
                    known_encoding = known_encodings[0]

                new_image = face_recognition.load_image_file(photo_path)
                new_encodings = face_recognition.face_encodings(new_image)
                if not new_encodings:
                    continue

                distance = face_recognition.face_distance([known_encoding], new_encodings[0])[0]
                results = face_recognition.compare_faces([known_encoding], new_encodings[0], tolerance=0.4)

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
        compute_and_save_encoding(senior)
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

# --- Generate Reference Number ---
def generate_reference():
    from datetime import datetime
    now = datetime.now()
    unique = uuid_module.uuid4().hex[:6].upper()
    return f"BRY-{now.strftime('%Y%m%d')}-{unique}"

def compute_and_save_encoding(senior):
    try:
        image = face_recognition.load_image_file(senior.photo_path)
        encodings = face_recognition.face_encodings(image)
        if encodings:
            import json
            senior.face_encoding = json.dumps(encodings[0].tolist())
            db.session.commit()
    except Exception:
        pass

# --- Face Recognition API ---
@app.route('/recognize', methods=['POST'])
@login_required
def recognize():
    from datetime import datetime, timedelta

    data = request.get_json()
    image_data = data.get('image')

    if not image_data or not image_data.startswith('data:image'):
        return {'status': 'no_face', 'message': 'Invalid image data'}

    image_bytes = base64.b64decode(image_data.split(',')[1])
    new_image = face_recognition.load_image_file(BytesIO(image_bytes))
    new_encodings = face_recognition.face_encodings(new_image)

    if not new_encodings:
        return {'status': 'no_face', 'message': 'No face detected. Please try again.'}

    seniors = Senior.query.all()
    for senior in seniors:
        try:
            known_image = face_recognition.load_image_file(senior.photo_path)
            known_encodings = face_recognition.face_encodings(known_image)
            if not known_encodings:
                continue

            distance = face_recognition.face_distance([known_encodings[0]], new_encodings[0])[0]
            results = face_recognition.compare_faces([known_encodings[0]], new_encodings[0], tolerance=0.4)

            if results[0] and distance < 0.4:
                # 90-day cooldown check
                cutoff = datetime.now() - timedelta(days=90)
                recent = Transaction.query.filter_by(senior_id=senior.id).filter(
                    Transaction.date_released >= cutoff,
                    Transaction.status == 'Released'
                ).first()

                if recent:
                    next_date = recent.date_released + timedelta(days=90)
                    return {
                        'status': 'already_claimed',
                        'message': f'Already claimed on {recent.date_released.strftime("%B %d, %Y")}. Next eligible: {next_date.strftime("%B %d, %Y")}'
                    }

                # Create pending transaction
                transaction = Transaction(
                    reference_number=generate_reference(),
                    senior_id=senior.id,
                    amount=1500.00,
                    released_by=current_user.name,
                    status='Pending'
                )
                db.session.add(transaction)
                db.session.commit()

                return {
                    'status': 'match',
                    'transaction_id': transaction.id,
                    'reference_number': transaction.reference_number,
                    'name': senior.full_name,
                    'age': senior.age,
                    'address': senior.address,
                    'photo': senior.photo_path
                }
        except Exception:
            continue

    return {'status': 'no_match', 'message': 'No matching senior found.'}

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
        if photo and allowed_file(photo.filename):
            compute_and_save_encoding(senior)
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
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=90)
    transactions = Transaction.query.filter(
        Transaction.date_released >= cutoff,
        Transaction.status == 'Released'
    ).all()
    for t in transactions:
        t.status = 'Reset'
    db.session.commit()
    flash('All claims have been reset. All seniors can now claim again.')
    return redirect(url_for('seniors'))

# --- DSS Page ---
@app.route('/')
@login_required
def index():
    from datetime import datetime, timedelta
    now = datetime.now()
    cutoff = now - timedelta(days=90)

    senior_count = Senior.query.count()
    transaction_count = Transaction.query.count()
    total_released = db.session.query(db.func.sum(Transaction.amount)).scalar() or 0

    claimed_ids = db.session.query(Transaction.senior_id).filter(
        Transaction.date_released >= cutoff
    ).distinct().all()
    claimed_ids = [c[0] for c in claimed_ids]
    claimed_count = len(claimed_ids)
    unclaimed_count = senior_count - claimed_count

    unclaimed_seniors = Senior.query.filter(
        ~Senior.id.in_(claimed_ids)
    ).all() if claimed_ids else Senior.query.all()

    insights = []
    if unclaimed_count > 0:
        insights.append(f'{unclaimed_count} senior(s) have not claimed their allowance in the last 90 days.')
    if unclaimed_count == 0 and senior_count > 0:
        insights.append('All registered seniors have claimed their allowance. Great job!')
    if senior_count == 0:
        insights.append('No seniors are registered yet. Start by registering senior citizens.')
    if claimed_count > 0 and unclaimed_count > 0:
        rate = (claimed_count / senior_count) * 100
        insights.append(f'Current claim rate is {rate:.1f}%. Consider reaching out to unclaimed seniors.')

    return render_template('index.html',
        senior_count=senior_count,
        transaction_count=transaction_count,
        total_released=total_released,
        claimed_count=claimed_count,
        unclaimed_count=unclaimed_count,
        unclaimed_seniors=unclaimed_seniors,
        insights=insights,
        now=now
    )

    # Insights
    insights = []
    if unclaimed_count > 0:
        insights.append(f'{unclaimed_count} senior(s) have not claimed their allowance in the last 90 days.')
    if unclaimed_count == 0 and total_seniors > 0:
        insights.append('All registered seniors have claimed their allowance. Great job!')
    if claimed_count > 0 and unclaimed_count > 0:
        rate = (claimed_count / total_seniors) * 100
        insights.append(f'Current claim rate is {rate:.1f}%. Consider reaching out to unclaimed seniors.')
    if last_transaction:
        days_since = (now - last_transaction.date_released).days
        if days_since > 30:
            insights.append(f'No transactions in the last {days_since} days. Is a new release period coming up?')

    return render_template('dss.html',
        total_released=total_released,
        total_transactions=total_transactions,
        claimed_count=claimed_count,
        unclaimed_count=unclaimed_count,
        unclaimed_seniors=unclaimed_seniors,
        insights=insights,
        now=now
    )

@app.route('/confirm-release', methods=['POST'])
@login_required
def confirm_release():
    import base64, uuid as uuid_lib
    data = request.get_json()
    transaction_id = data.get('transaction_id')
    signature_data = data.get('signature')
    release_photo_data = data.get('release_photo')

    transaction = Transaction.query.get_or_404(transaction_id)

    sig_path = 'static/signatures/' + sig_filename
    photo_path = 'static/release_photos/' + photo_filename

    # Save signature
    if signature_data and signature_data.startswith('data:image'):
        sig_bytes = base64.b64decode(signature_data.split(',')[1])
        senior_name = transaction.senior.full_name.replace(' ', '_')
        ref = transaction.reference_number
        sig_filename = f"{senior_name}_{ref}_signature.png"
        sig_path = 'static/signatures/' + sig_filename
        with open(sig_path, 'wb') as f:
            f.write(sig_bytes)
        transaction.signature_path = sig_path

    # Save release photo
    if release_photo_data and release_photo_data.startswith('data:image'):
        photo_bytes = base64.b64decode(release_photo_data.split(',')[1])
        photo_filename = f"{senior_name}_{ref}_release.jpg"
        photo_path = 'static/release_photos/' + photo_filename
        with open(photo_path, 'wb') as f:
            f.write(photo_bytes)
        transaction.release_photo_path = photo_path

    transaction.status = 'Released'
    db.session.commit()

    return {'status': 'success', 'reference_number': transaction.reference_number}

# --- Reset Individual Senior Claim ---
@app.route('/seniors/<int:senior_id>/reset-claim', methods=['POST'])
@login_required
def reset_senior_claim(senior_id):
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=90)
    Transaction.query.filter_by(senior_id=senior_id).filter(
        Transaction.date_released >= cutoff,
        Transaction.status == 'Released'
    ).delete()
    db.session.commit()
    senior = Senior.query.get_or_404(senior_id)
    flash(f'Claim reset for {senior.full_name}. They can now claim again.')
    return redirect(url_for('seniors'))

# --- Blink Detection ---
# --- Blink Detection ---
@app.route('/detect-blink', methods=['POST'])
@login_required
def detect_blink_route():
    data = request.get_json()
    image_data = data.get('image')
    reset = data.get('reset', False)

    if reset:
        from blink import reset_blink_counter
        reset_blink_counter()
        return {'blink': False, 'face': False}

    if not image_data or not image_data.startswith('data:image'):
        return {'blink': False, 'face': False}

    image_bytes = base64.b64decode(image_data.split(',')[1])
    result = check_blink(image_bytes)
    return result

@app.route('/fix-paths')
@login_required
def fix_paths():
    transactions = Transaction.query.all()
    for t in transactions:
        if t.release_photo_path:
            t.release_photo_path = t.release_photo_path.replace('\\', '/')
        if t.signature_path:
            t.signature_path = t.signature_path.replace('\\', '/')
    db.session.commit()
    return {'status': 'fixed'}

if __name__ == '__main__':
    app.run(debug=True)

