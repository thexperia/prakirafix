import pandas as pd
import streamlit as st

from core import nav, ui, validasi
from core.common import daftar_dataset, load_dataset, now_iso, tgl, uid
from core.storage import get_backend, new_id
from core.template import buat_template


@st.cache_data(show_spinner=False)
def _template():
    return buat_template()


def tampil_pesan(res):
    for e in res["errors"]:
        st.markdown(f'<div class="msg-err"><b>Error · {e["lokasi"]}</b><br>{e["pesan"]}</div>', unsafe_allow_html=True)
    if res["warnings"]:
        with st.expander(f"⚠️ {len(res['warnings'])} peringatan (tidak menghalangi proses)", expanded=not res["ok"] or len(res["warnings"]) <= 3):
            for w in res["warnings"]:
                st.markdown(f'<div class="msg-warn"><b>Peringatan · {w["lokasi"]}</b><br>{w["pesan"]}</div>', unsafe_allow_html=True)


def pratinjau(res, key):
    df, labels, info = res["df"], res["labels"], res["info"]
    last = pd.Period(info["periode_akhir"], "Q")
    df = df.loc[:last]
    c = st.columns(4)
    ui.kpi(c[0], "Periode", f"{info['periode_awal']} s.d. {info['periode_akhir']}")
    ui.kpi(c[1], "Jumlah triwulan", info["n_obs"])
    ui.kpi(c[2], "Kolom", len(info["kolom"]), ", ".join(info["kolom"][:4]) + (" …" if len(info["kolom"]) > 4 else ""))
    ui.kpi(c[3], "Sel kosong", info["sel_kosong"], "diisi otomatis saat proyeksi" if info["sel_kosong"] else "")
    t1, t2, t3 = st.tabs(["Tabel", "Grafik", "Statistik per kolom"])
    with t1:
        show = df.copy()
        show.index = show.index.astype(str)
        show.index.name = "Periode"
        cfg = {c_: st.column_config.NumberColumn(c_, help=labels.get(c_, c_), format="%.2f") for c_ in show.columns}
        st.dataframe(show.reset_index(), column_config=cfg, hide_index=True, use_container_width=True, height=320, key=f"tbl_{key}")
        st.caption("Arahkan kursor ke judul kolom untuk melihat nama lengkap indikator.")
    with t2:
        cc = st.columns([1, 2.4])
        col = cc[0].selectbox("Kolom", list(df.columns), index=list(df.columns).index("GPDRB") if "GPDRB" in df.columns else 0, key=f"sel_{key}")
        cc[1].markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
        cc[1].caption(labels.get(col, col))
        s = df[col].copy()
        s.index = s.index.to_timestamp()
        st.line_chart(s, height=280, color=ui.TEAL)
    with t3:
        d = df.describe().T[["count", "mean", "std", "min", "max"]].round(2)
        d.columns = ["Jumlah data", "Rata-rata", "Simpangan baku", "Min", "Maks"]
        d.insert(0, "Nama", [labels.get(i, i) for i in d.index])
        d.insert(1, "Mulai", [str(df[c_].first_valid_index()) for c_ in df.columns])
        d.insert(2, "Sampai", [str(df[c_].last_valid_index()) for c_ in df.columns])
        st.dataframe(d, use_container_width=True)


def show():
    ui.header("Kelola dataset", "Data", "Unduh template, isi, unggah, lalu cek hasilnya sebelum dipakai.")
    s = st.columns(4)
    for col, (n, t) in zip(s, [("1", "Unduh template"), ("2", "Isi data di Excel"), ("3", "Unggah file"), ("4", "Cek dan simpan")]):
        col.markdown(f'<div class="kpi"><div class="v" style="font-size:20px">{n}. {t}</div></div>', unsafe_allow_html=True)
    st.write("")

    a, b = st.columns([1, 1.4])
    with a:
        with st.container(border=True):
            st.subheader("Template Excel")
            st.markdown("""Pakai template supaya format data selalu sama. Isinya sheet **Data**, **Petunjuk**, dan **Contoh**.
- Baris 1: nama indikator, baris 2: kode (mis. GPDRB)
- Kolom A: tahun, kolom B: triwulan (Q1 s.d. Q4)
- Isi pertumbuhan dalam **% yoy**; kolom level PDRB opsional
- Sel yang belum ada datanya dibiarkan **kosong**, jangan diisi 0""")
            st.download_button("⬇ Unduh template (.xlsx)", _template(), "template_proyeksi_pdrb.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)
    with b:
        with st.container(border=True):
            st.subheader("Unggah data")
            up = st.file_uploader("File Excel sesuai template (.xlsx)", type=["xlsx"], help="Aplikasi membaca sheet 'Data', atau sheet pertama bila tidak ada.")
            if up:
                raw = up.getvalue()
                res = validasi.periksa(raw)
                if res["ok"]:
                    st.success(f"Format sesuai. Sheet dibaca: **{res['sheet']}**.")
                else:
                    st.error("Format belum sesuai. Perbaiki error di bawah, lalu unggah ulang.")
                tampil_pesan(res)
                import hashlib
                h = hashlib.md5(raw).hexdigest()
                if res["ok"] and st.session_state.get("tersimpan_hash") == h:
                    st.info("File ini sudah tersimpan sebagai dataset.")
                elif res["ok"]:
                    nama = st.text_input("Nama dataset", value=up.name.rsplit(".", 1)[0].replace("_", " "))
                    if st.button("💾 Simpan dataset", type="primary"):
                        be = get_backend()
                        did = new_id()
                        path = f"{uid()}/datasets/{did}.xlsx"
                        be.put_file(path, raw, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        row = {"id": did, "user_id": uid(), "name": nama.strip() or up.name, "filename": up.name, "sheet": res["sheet"],
                               "storage_path": path, "info": res["info"], "labels": res["labels"], "created_at": now_iso()}
                        be.insert("datasets", row)
                        st.session_state["dataset_aktif"] = row
                        st.session_state["dataset_baru"] = did
                        st.session_state["tersimpan_hash"] = h
                        st.rerun()

    if st.session_state.pop("dataset_baru", None):
        st.success("Dataset tersimpan dan dijadikan dataset aktif. Lanjut ke **Jalankan Proyeksi** kapan saja.")

    st.subheader("Dataset tersimpan")
    dsets = daftar_dataset()
    if not dsets:
        st.caption("Belum ada dataset tersimpan.")
        return
    aktif = (st.session_state.get("dataset_aktif") or {}).get("id")
    pilih = st.selectbox("Pilih dataset untuk dipratinjau", dsets, format_func=lambda d: f"{d['name']}  ·  diunggah {tgl(d['created_at'])}",
                         index=next((i for i, d in enumerate(dsets) if d["id"] == aktif), 0))
    res = load_dataset(pilih)
    with st.container(border=True):
        st.markdown(f"#### Pratinjau · {pilih['name']}")
        if res["ok"]:
            pratinjau(res, pilih["id"])
        tampil_pesan(res)
        c1, c2, c3, _ = st.columns([1.3, 1.3, 1, 2])
        if c1.button("✔ Jadikan dataset aktif", use_container_width=True):
            st.session_state["dataset_aktif"] = pilih
            st.rerun()
        if c2.button("▶ Pakai untuk proyeksi", type="primary", use_container_width=True):
            st.session_state["dataset_aktif"] = pilih
            nav.go("jalankan")
        if c3.button("🗑 Hapus", use_container_width=True):
            st.session_state["konfirmasi_hapus"] = pilih["id"]
        if st.session_state.get("konfirmasi_hapus") == pilih["id"]:
            st.warning("Hapus dataset ini? Riwayat run yang memakainya tetap ada.")
            y, n, _ = st.columns([1, 1, 4])
            if y.button("Ya, hapus"):
                be = get_backend()
                be.delete_file(pilih["storage_path"])
                be.delete("datasets", uid(), pilih["id"])
                if aktif == pilih["id"]:
                    st.session_state.pop("dataset_aktif", None)
                st.session_state.pop("konfirmasi_hapus", None)
                st.rerun()
            if n.button("Batal"):
                st.session_state.pop("konfirmasi_hapus", None)
                st.rerun()
