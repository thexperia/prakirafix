"""Penyimpanan data: Supabase (saat deploy) atau lokal/SQLite (untuk uji coba di laptop).

Backend dipilih otomatis: bila st.secrets berisi [supabase] url & key -> Supabase, selain itu lokal.
Semua halaman hanya memanggil fungsi di sini, jadi tidak peduli backend mana yang aktif.
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

BUCKET = "proyeksi-files"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LocalBackend:
    name = "lokal"

    def __init__(self, folder="local_data"):
        self.root = Path(folder)
        (self.root / "files").mkdir(parents=True, exist_ok=True)
        self.db = self.root / "app.db"
        with self._con() as c:
            c.executescript("""
            create table if not exists app_users(id integer primary key, username text unique, password_hash text, display_name text, created_at text);
            create table if not exists datasets(id text primary key, user_id integer, name text, filename text, sheet text,
                storage_path text, info text, labels text, created_at text);
            create table if not exists runs(id text primary key, user_id integer, dataset_id text, name text, note text,
                settings text, summary text, status text, excel_path text, charts_path text, created_at text);
            """)

    def _con(self):
        c = sqlite3.connect(self.db)
        c.row_factory = sqlite3.Row
        return c

    # users
    def get_user(self, username):
        with self._con() as c:
            r = c.execute("select * from app_users where lower(username)=lower(?)", (username,)).fetchone()
        return dict(r) if r else None

    def create_user(self, username, password_hash, display_name=None):
        with self._con() as c:
            c.execute("insert or ignore into app_users(username,password_hash,display_name,created_at) values(?,?,?,?)",
                      (username, password_hash, display_name or username, _now()))

    def set_password(self, user_id, password_hash):
        with self._con() as c:
            c.execute("update app_users set password_hash=? where id=?", (password_hash, user_id))

    # files
    def put_file(self, path, data, content_type="application/octet-stream"):
        p = self.root / "files" / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get_file(self, path):
        return (self.root / "files" / path).read_bytes()

    def delete_file(self, path):
        p = self.root / "files" / path
        if p.exists():
            p.unlink()

    # tables
    def insert(self, table, row):
        row = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in row.items()}
        cols = ",".join(row)
        with self._con() as c:
            c.execute(f"insert into {table}({cols}) values({','.join('?' * len(row))})", list(row.values()))

    def update(self, table, id_, fields):
        fields = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in fields.items()}
        with self._con() as c:
            c.execute(f"update {table} set {','.join(f'{k}=?' for k in fields)} where id=?", [*fields.values(), id_])

    def select(self, table, user_id, id_=None):
        q = f"select * from {table} where user_id=?"
        args = [user_id]
        if id_:
            q += " and id=?"
            args.append(id_)
        q += " order by created_at desc"
        with self._con() as c:
            rows = [dict(r) for r in c.execute(q, args).fetchall()]
        for r in rows:
            for k in ("info", "labels", "settings", "summary"):
                if k in r and isinstance(r[k], str):
                    try:
                        r[k] = json.loads(r[k])
                    except Exception:
                        pass
        return rows

    def delete(self, table, user_id, id_):
        with self._con() as c:
            c.execute(f"delete from {table} where user_id=? and id=?", (user_id, id_))


class SupabaseBackend:
    name = "supabase"

    def __init__(self, url, key):
        from supabase import create_client
        self.sb = create_client(url, key)

    def get_user(self, username):
        r = self.sb.table("app_users").select("*").ilike("username", username).limit(1).execute()
        return r.data[0] if r.data else None

    def create_user(self, username, password_hash, display_name=None):
        self.sb.table("app_users").upsert({"username": username, "password_hash": password_hash, "display_name": display_name or username},
                                          on_conflict="username", ignore_duplicates=True).execute()

    def set_password(self, user_id, password_hash):
        self.sb.table("app_users").update({"password_hash": password_hash}).eq("id", user_id).execute()

    def put_file(self, path, data, content_type="application/octet-stream"):
        self.sb.storage.from_(BUCKET).upload(path, data, {"content-type": content_type, "upsert": "true"})

    def get_file(self, path):
        return self.sb.storage.from_(BUCKET).download(path)

    def delete_file(self, path):
        try:
            self.sb.storage.from_(BUCKET).remove([path])
        except Exception:
            pass

    def insert(self, table, row):
        self.sb.table(table).insert(row).execute()

    def update(self, table, id_, fields):
        self.sb.table(table).update(fields).eq("id", id_).execute()

    def select(self, table, user_id, id_=None):
        q = self.sb.table(table).select("*").eq("user_id", user_id)
        if id_:
            q = q.eq("id", id_)
        return q.order("created_at", desc=True).execute().data or []

    def delete(self, table, user_id, id_):
        self.sb.table(table).delete().eq("user_id", user_id).eq("id", id_).execute()


def get_backend():
    import streamlit as st
    if "_backend" in st.session_state:
        return st.session_state["_backend"]
    be = None
    try:
        cfg = st.secrets.get("supabase", None)
    except Exception:
        cfg = None
    if cfg and cfg.get("url") and cfg.get("key"):
        be = SupabaseBackend(cfg["url"], cfg["key"])
    else:
        be = LocalBackend(os.environ.get("LOCAL_DATA_DIR", "local_data"))
    st.session_state["_backend"] = be
    return be


def new_id():
    return str(uuid.uuid4())
