from app import app, db
from models import Official
from werkzeug.security import generate_password_hash

def init_db():
    with app.app_context():
        db.create_all()

        if not Official.query.filter_by(username='admin').first():
            admin = Official(
                name='Admin Official',
                username='admin',
                password=generate_password_hash('admin123')
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created — username: admin, password: admin123")

        print("✅ Database ready!")

if __name__ == '__main__':
    init_db()