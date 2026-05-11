from cryptography.fernet import Fernet
import os

KEY_FILE = 'secret.key'

def load_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, 'wb') as f:
            f.write(key)
        print("✅ New encryption key generated and saved to secret.key")
    with open(KEY_FILE, 'rb') as f:
        return f.read()

fernet = Fernet(load_key())

def encrypt(value: str) -> str:
    if not value:
        return value
    return fernet.encrypt(value.encode()).decode()

def decrypt(value: str) -> str:
    if not value:
        return value
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return value