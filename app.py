"""Proyeksi PDRB: aplikasi web forecasting indikator regional (Streamlit).

Jalankan lokal : streamlit run app.py
Deploy         : Streamlit Community Cloud + Supabase (lihat README.md)
"""
import streamlit as st

st.set_page_config(page_title="Proyeksi PDRB", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

from core import nav, ui  # noqa: E402
from core.auth import cek_password, pastikan_akun_awal  # noqa: E402
from core.storage import get_backend, LocalBackend  # noqa: E402

ui.style()
be = get_backend()
if isinstance(be, LocalBackend) and not st.session_state.get("_seeded"):
    pastikan_akun_awal(be)
    st.session_state["_seeded"] = True


def halaman_login():
    c1, c2, c3 = st.columns([1, 1.1, 1])
    with c2:
        st.markdown("<div style='height:6vh'></div>", unsafe_allow_html=True)
        st.markdown('<div class="eyebrow">Forecasting Indikator Regional</div>', unsafe_allow_html=True)
        st.title("Proyeksi PDRB")
        st.caption("Masuk untuk memakai dataset dan melihat riwayat run milikmu.")
        with st.form("login"):
            u = st.text_input("Username", placeholder="user1")
            p = st.text_input("Password", type="password")
            ok = st.form_submit_button("Masuk", type="primary", use_container_width=True)
        if ok:
            user = be.get_user(u.strip())
            if user and cek_password(p, user["password_hash"]):
                st.session_state["user"] = {"id": user["id"], "username": user["username"]}
                st.session_state["baru_login"] = True
                st.rerun()
            else:
                st.error("Username atau password salah.")
        st.caption(f"Penyimpanan: {'Supabase' if be.name == 'supabase' else 'lokal (mode uji coba)'}")


if "user" not in st.session_state:
    halaman_login()
    st.stop()

from views import beranda, data, jalankan, riwayat, glosarium, akun  # noqa: E402

P = {
    "beranda": st.Page(beranda.show, title="Beranda", icon=":material/home:", url_path="beranda", default=True),
    "data": st.Page(data.show, title="Data", icon=":material/database:", url_path="data"),
    "jalankan": st.Page(jalankan.show, title="Jalankan Proyeksi", icon=":material/play_arrow:", url_path="jalankan"),
    "riwayat": st.Page(riwayat.show, title="Riwayat Run", icon=":material/history:", url_path="riwayat"),
    "glosarium": st.Page(glosarium.show, title="Glosarium", icon=":material/menu_book:", url_path="glosarium"),
    "akun": st.Page(akun.show, title="Akun", icon=":material/person:", url_path="akun"),
}
nav.PAGES = P
pg = st.navigation({"Menu": [P["beranda"], P["data"], P["jalankan"], P["riwayat"]], "Bantuan": [P["glosarium"], P["akun"]]})
if st.session_state.pop("baru_login", False) and pg.url_path != "beranda":
    st.switch_page(P["beranda"])

with st.sidebar:
    st.markdown("### 📈 Proyeksi PDRB")
    st.caption("Forecasting Indikator Regional")
    ds = st.session_state.get("dataset_aktif")
    if ds:
        st.markdown(f"**Dataset aktif**  \n{ds['name']}  \n<small>{ds['info'].get('periode_awal')} s.d. {ds['info'].get('periode_akhir')}</small>",
                    unsafe_allow_html=True)
    st.divider()
    st.markdown(f"👤 **{st.session_state['user']['username']}**")
    if st.button("Keluar", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k != "_backend":
                del st.session_state[k]
        st.rerun()

pg.run()
