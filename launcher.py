import sys
import os
import threading
import webbrowser
import time

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def open_browser():
    time.sleep(2)  # Wait for Flask to start
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    # Start browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Initialize database and create default admin if needed
    from app import app, db
    from models import Official
    from werkzeug.security import generate_password_hash

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

    # Start Flask
    app.run(debug=False, host='127.0.0.1', port=5000)