import streamlit as st

from core import ui
from core.auth import cek_password, hash_password
from core.storage import get_backend


def show():
    ui.header("Akun", st.session_state["user"]["username"])
    be = get_backend()
    st.caption(f"Penyimpanan aktif: {'Supabase' if be.name == 'supabase' else 'lokal (mode uji coba)'}")
    with st.container(border=True):
        st.subheader("Ganti password")
        with st.form("pw"):
            lama = st.text_input("Password lama", type="password")
            baru = st.text_input("Password baru", type="password")
            ulang = st.text_input("Ulangi password baru", type="password")
            ok = st.form_submit_button("Simpan", type="primary")
        if ok:
            u = be.get_user(st.session_state["user"]["username"])
            if not u or not cek_password(lama, u["password_hash"]):
                st.error("Password lama salah.")
            elif len(baru) < 6:
                st.error("Password baru minimal 6 karakter.")
            elif baru != ulang:
                st.error("Password baru dan ulangannya tidak sama.")
            else:
                be.set_password(u["id"], hash_password(baru))
                st.success("Password berhasil diganti.")
