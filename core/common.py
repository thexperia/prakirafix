"""Fungsi data bersama antarhalaman."""
from datetime import datetime, timezone

import streamlit as st

from core import validasi
from core.storage import get_backend


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def uid():
    return st.session_state["user"]["id"]


def daftar_dataset():
    return get_backend().select("datasets", uid())


def daftar_run():
    return get_backend().select("runs", uid())


@st.cache_data(show_spinner=False, max_entries=20)
def _file(path, _backend_name):
    return get_backend().get_file(path)


def file_bytes(path):
    return _file(path, get_backend().name)


@st.cache_data(show_spinner=False, max_entries=10)
def parse_dataset(path, _backend_name):
    return validasi.periksa(get_backend().get_file(path))


def load_dataset(ds):
    return parse_dataset(ds["storage_path"], get_backend().name)


def tgl(iso):
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone()
        bln = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"][d.month - 1]
        return f"{d.day} {bln} {d.year}, {d:%H:%M}"
    except Exception:
        return str(iso)[:16]
