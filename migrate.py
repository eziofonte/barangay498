from app import app, db
from models import ProxyEnrollment

with app.app_context():
    # Create the proxy_enrollment table
    db.create_all()
    
    # Add the column to transaction table if it doesn't exist
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text('ALTER TABLE "transaction" ADD COLUMN proxy_enrollment_id INTEGER REFERENCES proxy_enrollment(id)'))
            conn.commit()
        print("Column added!")
    except Exception as e:
        print(f"Column may already exist, skipping: {e}")
    
    print("Done!")