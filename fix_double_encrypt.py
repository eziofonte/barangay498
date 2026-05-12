from app import app, db
from models import Senior, ProxyEnrollment
from fernet_crypto import decrypt

with app.app_context():
    print("Fixing double-encrypted records...")

    seniors = Senior.query.all()
    for senior in seniors:
        # Decrypt twice to undo the double encryption
        try:
            once = decrypt(senior.full_name)
            twice = decrypt(once)
            senior.full_name = once  # go back to single-encrypted
            
            once_addr = decrypt(senior.address)
            senior.address = once_addr
            print(f"  ✅ Fixed: {twice}")
        except Exception as e:
            print(f"  ⚠ Skipped ID {senior.id}: {e}")

    proxies = ProxyEnrollment.query.all()
    for proxy in proxies:
        try:
            once = decrypt(proxy.full_name)
            proxy.full_name = once
            once_id = decrypt(proxy.id_number)
            proxy.id_number = once_id
            print(f"  ✅ Fixed proxy: {decrypt(once)}")
        except Exception as e:
            print(f"  ⚠ Skipped proxy ID {proxy.id}: {e}")

    db.session.commit()
    print("\n✅ Done! Double encryption removed.")