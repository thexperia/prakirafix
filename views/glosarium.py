import streamlit as st

from core import ui


def show():
    ui.header("Bantuan", "Glosarium", "Penjelasan singkat istilah yang dipakai di aplikasi. Penjelasan yang sama muncul saat kursor diarahkan ke ikon ⓘ.")
    q = st.text_input("Cari istilah", placeholder="mis. RMSE, BVAR, add-factor")
    for grp, items in ui.GLOSARIUM.items():
        hits = {k: v for k, v in items.items() if not q or q.lower() in (k + " " + v).lower()}
        if not hits:
            continue
        st.subheader(grp)
        for k, v in hits.items():
            with st.container(border=True):
                st.markdown(f"**{k}**  \n{v}")
