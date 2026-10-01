import streamlit as st

from core import engine, nav, ui
from core.common import daftar_dataset, daftar_run, tgl


def _utama(s):
    return s.get("metode_utama") or engine.pilih_utama(s.get("urutan") or [m["metode"] for m in s.get("metrik", [])] or ["-"])


def show():
    u = st.session_state["user"]
    user = (u.get("nama") or u["username"]).split()[0]
    runs = daftar_run()
    dsets = daftar_dataset()
    ui.header("Beranda", f"Halo, {user}")

    c = st.columns([1, 1, 1, 1])
    ui.kpi(c[0], "Dataset tersimpan", len(dsets), "bisa dipakai lagi tanpa upload ulang")
    ui.kpi(c[1], "Total run", len(runs), "semua tersimpan di riwayat")
    if runs:
        r0 = runs[0]
        ui.kpi(c[2], "Run terakhir", tgl(r0["created_at"]).split(",")[0], r0.get("name") or "")
        s0 = r0.get("summary") or {}
        ui.kpi(c[3], "Metode utama", _utama(s0), f"RMSE {ui.fmt(s0.get('rmse_terbaik'), 3)} pada run terakhir", ui.g("RMSE"))
    else:
        ui.kpi(c[2], "Run terakhir", "-", "belum ada run")
        ui.kpi(c[3], "Metode utama", "-", "")

    b1, b2, _ = st.columns([1.5, 1.2, 2.3])
    if b1.button("▶ Jalankan proyeksi baru", type="primary", use_container_width=True):
        nav.go("jalankan")
    if b2.button("⬆ Unggah data", use_container_width=True):
        nav.go("data")

    ui.gap("m")
    if not dsets and not runs:
        st.info("Belum ada dataset. Mulai dari menu **Data**: unduh template, isi, lalu unggah. Punya hasil run dari Google Colab? Impor di menu **Riwayat Run**.")
        return

    left, right = st.columns([2.2, 1])
    with left:
        with st.container(border=True):
            if runs:
                r0 = runs[0]
                s = r0.get("summary") or {}
                st.subheader(f"Run terakhir: {r0.get('name')}")
                ch = ui.chart_proyeksi(s, 260)
                if ch is not None:
                    st.altair_chart(ch, use_container_width=True)
                pr = s.get("proyeksi", [])
                th = s.get("tahunan", {})
                yrs = [y for y in th if th[y] is not None][-2:]
                k1, k2 = st.columns(2), st.columns(2)
                slot = [k1[0], k1[1], k2[0], k2[1]]
                if pr:
                    ui.kpi(slot[0], f"yoy {pr[0]['periode']}", ui.fmt(pr[0]["yoy"], 2, True), _utama(s))
                for i, y in enumerate(yrs):
                    ui.kpi(slot[1 + i], f"Tumbuh {y}", ui.fmt(th[y], 2, True), "dari data + proyeksi", ui.g("Pertumbuhan tahunan"))
                ui.kpi(slot[3], "Akurasi arah", ui.fmt(s.get("arah_terbaik"), 0, True), f"backtest {_utama(s)}", ui.g("Akurasi arah"))
                if st.button("Lihat detail lengkap →"):
                    st.session_state["run_terpilih"] = r0["id"]
                    nav.go("riwayat")
            else:
                st.subheader("Belum ada run")
                st.write("Dataset sudah siap. Buka **Jalankan Proyeksi** untuk membuat run pertama, atau impor hasil Colab di **Riwayat Run**.")
    with right:
        with st.container(border=True):
            st.subheader("Dataset tersimpan")
            for d in dsets[:6]:
                inf = d.get("info") or {}
                st.markdown(f"**{d['name']}**  \n<small>{inf.get('periode_awal')} s.d. {inf.get('periode_akhir')} · {inf.get('n_obs')} triwulan · {len(inf.get('kolom', []))} kolom</small>",
                            unsafe_allow_html=True)
            st.caption("Data tersimpan di akunmu dan otomatis tersedia di sesi berikutnya.")

    ui.gap("m")
    st.subheader("Riwayat run")
    if not runs:
        st.caption("Belum ada run.")
        return
    q = st.text_input("Cari run", placeholder="nama atau catatan run", label_visibility="collapsed")
    hdr = st.columns([2.6, 1.6, 1.2, 1.1, 0.9, 1.4, 1.2])
    for h, t in zip(hdr, ["Nama run", "Dataset", "Proyeksi s.d.", "Metode utama", "RMSE ↓", "Tanggal", ""]):
        h.markdown(f"<small><b>{t}</b></small>", unsafe_allow_html=True)
    dsname = {d["id"]: d["name"] for d in dsets}
    for r in runs:
        text = f"{r.get('name', '')} {r.get('note', '')}".lower()
        if q and q.lower() not in text:
            continue
        s = r.get("summary") or {}
        cols = st.columns([2.6, 1.6, 1.2, 1.1, 0.9, 1.4, 1.2])
        cols[0].markdown(f"**{r.get('name')}**" + (f"  \n<small>{r['note']}</small>" if r.get("note") else ""), unsafe_allow_html=True)
        cols[1].write(dsname.get(r.get("dataset_id"), "(dataset dihapus)"))
        cols[2].write(s.get("proyeksi_sampai", "-"))
        cols[3].write(_utama(s) if s else "-")
        cols[4].write(ui.fmt(s.get("rmse_terbaik"), 3))
        cols[5].write(tgl(r["created_at"]))
        if cols[6].button("Buka", key=f"open_{r['id']}", use_container_width=True):
            st.session_state["run_terpilih"] = r["id"]
            nav.go("riwayat")
