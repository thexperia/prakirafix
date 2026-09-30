"""Login sederhana di level aplikasi. Password disimpan sebagai hash PBKDF2 (bukan teks asli)."""
import hashlib
import hmac
import os

AKUN_AWAL = [f"user{i}" for i in range(1, 6)]
PASSWORD_AWAL = "123456"
ITER = 120_000


def hash_password(pw, salt=None):
    salt = salt or os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), ITER).hex()
    return f"pbkdf2${ITER}${salt}${h}"


def cek_password(pw, stored):
    try:
        _, it, salt, h = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it)).hex()
        return hmac.compare_digest(calc, h)
    except Exception:
        return False


def pastikan_akun_awal(be):
    """Membuat user1 s.d. user5 bila belum ada (dipakai mode lokal; di Supabase lewat schema.sql)."""
    for u in AKUN_AWAL:
        if not be.get_user(u):
            be.create_user(u, hash_password(PASSWORD_AWAL))
