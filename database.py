from app import app, db
from models import Official
from werkzeug.security import generate_password_hash

def init_db():
    with app.app_context():
        db.create_all()

        # Add proxy_enrollment_id to transaction table if it was created before this column existed
        from sqlalchemy import text, inspect as sa_inspect
        insp = sa_inspect(db.engine)
        if 'transaction' in insp.get_table_names():
            existing = [c['name'] for c in insp.get_columns('transaction')]
            if 'proxy_enrollment_id' not in existing:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE "transaction" ADD COLUMN proxy_enrollment_id INTEGER'))
                    conn.commit()

        if not Official.query.filter_by(username='admin').first():
            admin = Official(
                name='Admin Official',
                username='admin',
                password=generate_password_hash('admin123'),
                role='captain',
                captain_pin=generate_password_hash('captain1234')
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created — username: admin, password: admin123")
            print("✅ Captain PIN set to: captain1234")

        print("✅ Database ready!")

if __name__ == '__main__':
    init_db()
