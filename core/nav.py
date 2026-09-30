"""Referensi halaman (diisi app.py) supaya halaman lain bisa berpindah dengan st.switch_page."""
PAGES = {}


def go(name):
    import streamlit as st
    st.switch_page(PAGES[name])
