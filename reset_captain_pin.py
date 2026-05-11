"""
Standalone terminal utility — reset the captain PIN.
Run with: python reset_captain_pin.py
"""

import sys
SUPER_ADMIN_PASSWORD = 'superadmin123'


def main():
    print('=' * 45)
    print('  Captain PIN Recovery — Super Admin Tool')
    print('=' * 45)

    # ── Authenticate ─────────────────────────────
    password = input('Enter super admin password: ')
    if password != SUPER_ADMIN_PASSWORD:
        print('\n[ERROR] Incorrect password. Access denied.')
        sys.exit(1)

    print('\n[OK] Authenticated.\n')

    # ── Get new PIN ───────────────────────────────
    while True:
        new_pin = input('Enter new captain PIN: ')
        if not new_pin:
            print('[ERROR] PIN cannot be empty.')
            continue

        confirm = input('Confirm new captain PIN: ')
        if new_pin != confirm:
            print('[ERROR] PINs do not match. Try again.\n')
            continue

        break

    # ── Update database ───────────────────────────
    try:
        from app import app, db
        from models import Official
        from werkzeug.security import generate_password_hash

        with app.app_context():
            captain = Official.query.filter_by(role='captain').first()

            if captain is None:
                print('\n[ERROR] No account with role="captain" found in the database.')
                sys.exit(1)

            captain.captain_pin = generate_password_hash(new_pin)
            db.session.commit()

            print(f'\n[SUCCESS] Captain PIN updated for account: {captain.username}')

    except Exception as e:
        print(f'\n[ERROR] Database update failed: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
