import json
import time as _time
import face_recognition
import numpy as np
import base64
import uuid as uuid_module
import os
from io import BytesIO
from PIL import Image
from flask import session
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from fileinput import filename
from models import db, Official, Senior, Transaction
from blink import detect_blink as check_blink
from datetime import datetime, timedelta


app = Flask(__name__)
app.config['STARTUP_TIME'] = str(_time.time())
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = 'static/faces'
app.config['PERMANENT_SESSION_LIFETIME'] = 900
app.config['SESSION_PERMANENT'] = False

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return Official.query.get(int(user_id))

@app.before_request
def check_session_timeout():
    if request.path.startswith('/static'):
        return
    if current_user.is_authenticated:
        if session.get('startup_time') != app.config.get('STARTUP_TIME'):
            logout_user()
            session.clear()
            return redirect(url_for('login'))
        last_active = session.get('last_active')
        if last_active:
            last_active_dt = datetime.fromisoformat(last_active)
            if datetime.now() - last_active_dt > timedelta(minutes=15):
                logout_user()
                session.clear()
                flash('Your session has expired due to inactivity. Please log in again.')
                return redirect(url_for('login'))
        session['last_active'] = datetime.now().isoformat()
        session.permanent = True

# --- Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    from datetime import datetime, timedelta

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        official = Official.query.filter_by(username=username).first()

        if official:
            # Check if account is locked
            if official.locked_until and datetime.now() < official.locked_until:
                remaining = int((official.locked_until - datetime.now()).total_seconds() / 60) + 1
                flash(f'Account locked. Too many failed attempts. Try again in {remaining} minute(s).')
                return render_template('login.html')

            if check_password_hash(official.password, password):
                # Reset failed attempts on success
                official.failed_attempts = 0
                official.locked_until = None
                db.session.commit()
                login_user(official, remember=False)
                session['startup_time'] = app.config.get('STARTUP_TIME')
                return redirect(url_for('index'))
            else:
                # Increment failed attempts
                official.failed_attempts += 1
                if official.failed_attempts >= 5:
                    official.locked_until = datetime.now() + timedelta(minutes=5)
                    official.failed_attempts = 0
                    db.session.commit()
                    flash('Too many failed attempts. Account locked for 5 minutes.')
                else:
                    db.session.commit()
                    remaining_attempts = 5 - official.failed_attempts
                    flash(f'Invalid password. {remaining_attempts} attempt(s) remaining.')
        else:
            flash('Invalid username or password.')

    return render_template('login.html')

# --- Logout ---
@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    reason = request.args.get('reason')
    if reason == 'timeout':
        flash('You have been logged out due to inactivity.')
    return redirect(url_for('login'))

# --- Register Senior ---
@app.route('/register-senior', methods=['GET', 'POST'])
@login_required
def register_senior():
    if request.method == 'POST':
        import base64, uuid, time, io
        from PIL import Image as PILImage

        full_name = request.form.get('full_name')
        age = request.form.get('age')
        address = request.form.get('address')
        photo = request.files.get('photo')
        captured_photo = request.form.get('captured_photo')

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        photo_path = None
        img_array = None

        # Camera capture mode
        if captured_photo and captured_photo.startswith('data:image'):
            image_data = captured_photo.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            filename = f"capture_{uuid.uuid4().hex}.jpg"
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename).replace('\\', '/')
            with open(photo_path, 'wb') as f:
                f.write(image_bytes)
            # Load from memory directly — avoids file locking
            pil_image = PILImage.open(io.BytesIO(image_bytes)).convert('RGB')
            img_array = np.array(pil_image)

        # Upload mode
        elif photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename).replace('\\', '/')
            photo.save(photo_path)
            time.sleep(0.3)
            pil_image = PILImage.open(photo_path).convert('RGB')
            img_array = np.array(pil_image)

        else:
            flash('Please provide a photo — either upload one or use the camera.')
            return render_template('register_senior.html')

        # Get encoding of new photo
        new_encodings = face_recognition.face_encodings(img_array)
        del img_array

        if not new_encodings:
            flash('No face detected in the photo. Please try again.')
            return render_template('register_senior.html')

        # Check if face already exists using cached encodings
        # Check if face already exists using cached encodings
        all_seniors = Senior.query.all()
        for existing_senior in all_seniors:
            try:
                if not existing_senior.face_encoding:
                    # Fallback: compute from file
                    pil = PILImage.open(existing_senior.photo_path).convert('RGB')
                    arr = np.array(pil)
                    encs = face_recognition.face_encodings(arr)
                    if not encs:
                        continue
                    known_encoding = encs[0]
                else:
                    known_encoding = np.array(json.loads(existing_senior.face_encoding))

                distance = face_recognition.face_distance([known_encoding], new_encodings[0])[0]
                results = face_recognition.compare_faces([known_encoding], new_encodings[0], tolerance=0.4)

                if results[0] and distance < 0.4:
                    flash(f'This person is already registered as {existing_senior.full_name}.')
                    return render_template('register_senior.html')
            except Exception as e:
                print(f"Encoding check error: {e}")
                continue

        # All checks passed — save senior
        senior = Senior(
            full_name=full_name,
            age=age,
            address=address,
            photo_path=photo_path,
            face_encoding=json.dumps(new_encodings[0].tolist())
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
            if not senior.face_encoding:
                continue
            known_encoding = np.array(json.loads(senior.face_encoding))
            distance = face_recognition.face_distance([known_encoding], new_encodings[0])[0]
            results = face_recognition.compare_faces([known_encoding], new_encodings[0], tolerance=0.4)

            if results[0] and distance < 0.4:
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
                    'photo': senior.photo_path.replace('\\', '/')
                }
        except Exception as e:
            print(f"Recognition error: {e}")
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
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename).replace('\\', '/')
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
    total_released = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.status == 'Released'
    ).scalar() or 0

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

@app.route('/confirm-release', methods=['POST'])
@login_required
def confirm_release():
    import base64, uuid as uuid_lib
    data = request.get_json()
    transaction_id = data.get('transaction_id')
    signature_data = data.get('signature')
    release_photo_data = data.get('release_photo')

    transaction = Transaction.query.get_or_404(transaction_id)

    os.makedirs('static/signatures', exist_ok=True)
    os.makedirs('static/release_photos', exist_ok=True)

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

# --- Get Seniors List for Proxy ---
@app.route('/seniors-list')
@login_required
def seniors_list():
    seniors = Senior.query.all()
    return {'seniors': [{'id': s.id, 'name': s.full_name, 'age': s.age} for s in seniors]}

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

# --- Proxy Release ---
@app.route('/proxy-release', methods=['POST'])
@login_required
def proxy_release():
    from werkzeug.security import check_password_hash
    data = request.get_json()
    captain_pin = data.get('captain_pin')
    senior_id = data.get('senior_id')
    proxy_name = data.get('proxy_name')
    proxy_relationship = data.get('proxy_relationship')
    signature_data = data.get('signature')
    release_photo_data = data.get('release_photo')

    # Verify captain PIN
    captain = Official.query.filter_by(role='captain').first()
    if not captain or not captain.captain_pin:
        return {'status': 'error', 'message': 'No captain account found.'}
    if not check_password_hash(captain.captain_pin, captain_pin):
        return {'status': 'error', 'message': 'Incorrect captain PIN.'}

    senior = Senior.query.get_or_404(senior_id)

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

    transaction = Transaction(
        reference_number=generate_reference(),
        senior_id=senior.id,
        amount=1500.00,
        released_by=current_user.name,
        status='Released',
        release_type='Proxy',
        proxy_name=proxy_name,
        proxy_relationship=proxy_relationship
    )
    db.session.add(transaction)
    db.session.flush()

    os.makedirs('static/signatures', exist_ok=True)
    os.makedirs('static/release_photos', exist_ok=True)

    senior_name = senior.full_name.replace(' ', '_')
    ref = transaction.reference_number

    if signature_data and signature_data.startswith('data:image'):
        sig_bytes = base64.b64decode(signature_data.split(',')[1])
        sig_filename = f"{senior_name}_{ref}_proxy_signature.png"
        sig_path = 'static/signatures/' + sig_filename
        with open(sig_path, 'wb') as f:
            f.write(sig_bytes)
        transaction.signature_path = sig_path

    if release_photo_data and release_photo_data.startswith('data:image'):
        photo_bytes = base64.b64decode(release_photo_data.split(',')[1])
        photo_filename = f"{senior_name}_{ref}_proxy_release.jpg"
        photo_path = 'static/release_photos/' + photo_filename
        with open(photo_path, 'wb') as f:
            f.write(photo_bytes)
        transaction.release_photo_path = photo_path

    db.session.commit()

    return {
        'status': 'success',
        'reference_number': transaction.reference_number,
        'senior_name': senior.full_name,
        'proxy_name': proxy_name
    }

@app.route('/verify-captain-pin', methods=['POST'])
@login_required
def verify_captain_pin():
    from werkzeug.security import check_password_hash
    data = request.get_json()
    captain_pin = data.get('captain_pin')
    captain = Official.query.filter_by(role='captain').first()
    if not captain or not captain.captain_pin:
        return {'status': 'error', 'message': 'No captain account found.'}
    if not check_password_hash(captain.captain_pin, captain_pin):
        return {'status': 'error', 'message': 'Incorrect captain PIN.'}
    return {'status': 'ok'}

@app.route('/fix-captain')
@login_required
def fix_captain():
    from werkzeug.security import generate_password_hash
    admin = Official.query.filter_by(username='admin').first()
    admin.role = 'captain'
    admin.captain_pin = generate_password_hash('captain1234')
    db.session.commit()
    return {'status': 'done', 'message': 'Admin is now captain with PIN: captain1234'}

if __name__ == '__main__':
    app.run(debug=True)