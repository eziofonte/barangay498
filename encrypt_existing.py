from app import app, db
from models import Senior, ProxyEnrollment
from fernet_crypto import encrypt, decrypt

with app.app_context():
    print("Starting encryption of existing records...")

    # Encrypt existing seniors
    seniors = Senior.query.all()
    for senior in seniors:
        try:
            # Try decrypting first — if it works, already encrypted, skip
            decrypt(senior.full_name)
            # If decrypt didn't raise an error but returned same value, it's plaintext
            # We check by trying to encrypt and comparing
            encrypted = encrypt(decrypt(senior.full_name))
            if encrypted != senior.full_name:
                senior.full_name = encrypt(senior.full_name)
                senior.address = encrypt(senior.address)
                print(f"  ✅ Encrypted: {decrypt(senior.full_name)}")
        except Exception:
            # Already properly encrypted, skip
            print(f"  ⏭ Already encrypted, skipping ID {senior.id}")

    # Encrypt existing proxy enrollments
    proxies = ProxyEnrollment.query.all()
    for proxy in proxies:
        try:
            encrypted = encrypt(decrypt(proxy.full_name))
            if encrypted != proxy.full_name:
                proxy.full_name = encrypt(proxy.full_name)
                proxy.id_number = encrypt(proxy.id_number)
                print(f"  ✅ Encrypted proxy: {decrypt(proxy.full_name)}")
        except Exception:
            print(f"  ⏭ Already encrypted, skipping proxy ID {proxy.id}")

    db.session.commit()
    print("\n✅ Done! All records encrypted.")
