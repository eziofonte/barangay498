import os
import shutil
import threading
from datetime import datetime

# Save backups to a folder on the Desktop
DOCUMENTS = os.path.join(os.path.expanduser('~'), 'Documents')
BACKUP_FOLDER = os.path.join(DOCUMENTS, 'Barangay498_Backups')
DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')
MAX_BACKUPS = 26
INTERVAL_SECONDS = 14 * 24 * 60 * 60  # 2 weeks

def run_backup():
    try:
        os.makedirs(BACKUP_FOLDER, exist_ok=True)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_filename = f'database_backup_{timestamp}.db'
        backup_path = os.path.join(BACKUP_FOLDER, backup_filename)

        shutil.copy2(DB_PATH, backup_path)
        print(f'✅ Backup saved: {backup_filename}')

        # Delete oldest backups if over limit
        backups = sorted([
            f for f in os.listdir(BACKUP_FOLDER) if f.startswith('database_backup_')
        ])
        while len(backups) > MAX_BACKUPS:
            oldest = backups.pop(0)
            os.remove(os.path.join(BACKUP_FOLDER, oldest))
            print(f'🗑 Deleted old backup: {oldest}')

    except Exception as e:
        print(f'⚠ Backup failed: {e}')

def schedule_backups():
    def loop():
        while True:
            run_backup()
            threading.Event().wait(INTERVAL_SECONDS)
    
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    print('🔁 Automatic backup scheduler started (every 2 weeks)')