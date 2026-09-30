"""Login sederhana di level aplikasi. Password disimpan sebagai hash PBKDF2 (bukan teks asli)."""
import hashlib
import hmac
import os

AKUN_AWAL = [  # (username untuk login, nama tampilan)
    ("rachmad", "Rachmad Irvan Syahputra"),
    ("febiola", "Febiola Napitupulu"),
    ("torkis", "Torkis Justicio Paruhum Natigor Hasibuan"),
    ("shania", "Shania Gumilar"),
    ("sigit", "Sigit Setiawan"),
]
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
    """Membuat 5 akun awal bila belum ada (dipakai mode lokal; di Supabase lewat schema.sql)."""
    for u, nama in AKUN_AWAL:
        if not be.get_user(u):
            be.create_user(u, hash_password(PASSWORD_AWAL), nama)
