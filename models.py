from fernet_crypto import decrypt
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# --- Barangay Official (the one who logs in) ---
class Official(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), default='official')
    captain_pin = db.Column(db.String(300), nullable=True)
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

def _safe_decrypt(value):
    if value is None:
        return ''
    try:
        return decrypt(value)
    except Exception:
        return value

# --- Senior Citizen ---
class Senior(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    address = db.Column(db.String(300), nullable=False)
    photo_path = db.Column(db.String(300), nullable=False)
    face_encoding = db.Column(db.Text, nullable=True)

    @property
    def display_name(self):
        return _safe_decrypt(self.full_name)

    @property
    def display_address(self):
        return _safe_decrypt(self.address)

# --- Proxy Pre-Enrollment ---
class ProxyEnrollment(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    senior_id    = db.Column(db.Integer, db.ForeignKey('senior.id'), nullable=False)
    full_name    = db.Column(db.String(150), nullable=False)
    relationship = db.Column(db.String(100), nullable=False)
    id_type      = db.Column(db.String(100), nullable=False)
    id_number    = db.Column(db.String(100), nullable=False)
    id_photo     = db.Column(db.String(300), nullable=False)
    face_photo   = db.Column(db.String(300), nullable=True)
    enrolled_by  = db.Column(db.Integer, db.ForeignKey('official.id'), nullable=False)
    enrolled_at  = db.Column(db.DateTime, default=datetime.utcnow)
    is_active    = db.Column(db.Boolean, default=True)

    senior   = db.relationship('Senior',   backref='proxy_enrollments')
    official = db.relationship('Official', backref='enrolled_proxies')

    @property
    def display_name(self):
        return _safe_decrypt(self.full_name)

    @property
    def display_id_number(self):
        return _safe_decrypt(self.id_number)

# --- Transaction (record of money received) ---
class Transaction(db.Model):
    id                  = db.Column(db.Integer, primary_key=True)
    reference_number    = db.Column(db.String(20), unique=True, nullable=False)
    senior_id           = db.Column(db.Integer, db.ForeignKey('senior.id'), nullable=False)
    amount              = db.Column(db.Float, nullable=False)
    date_released       = db.Column(db.DateTime, default=datetime.utcnow)
    released_by         = db.Column(db.String(150), nullable=False)
    status              = db.Column(db.String(50), default='Released')
    signature_path      = db.Column(db.String(300), nullable=True)
    release_photo_path  = db.Column(db.String(300), nullable=True)
    release_type        = db.Column(db.String(50), default='Direct')
    proxy_name          = db.Column(db.String(150), nullable=True)
    proxy_relationship  = db.Column(db.String(150), nullable=True)
    proxy_enrollment_id = db.Column(db.Integer, db.ForeignKey('proxy_enrollment.id'), nullable=True)
    senior              = db.relationship('Senior', backref='transactions')