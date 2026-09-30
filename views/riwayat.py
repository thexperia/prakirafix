import re

import pandas as pd
import streamlit as st

from core import engine, nav, ui
from core.common import daftar_dataset, daftar_run, file_bytes, tgl, uid
from core.storage import get_backend

GRAFIK = {
    "01_data_historis.png": "Data historis dan hasil pembersihan outlier",
    "02_proyeksi_semua_metode.png": "Proyeksi semua metode",
    "03_fan_chart.png": "Proyeksi dengan selang kepercayaan (dua metode teratas)",
    "04_perbandingan_error.png": "Perbandingan error backtest",
    "05_rmse_per_horizon.png": "RMSE menurut horizon",
    "06_backtest_h1.png": "Backtest 1 triwulan ke depan: aktual vs prediksi",
    "07_pola_musiman_qtq.png": "Pola musiman (mode level)",
}


def _sheet(sheets, name, **kw):
    if name in sheets:
        df = sheets[name]
        if str(df.columns[0]).startswith("Unnamed"):
            df = df.rename(columns={df.columns[0]: "Periode" if name.startswith(("Proyeksi", "Series", "Data", "Variabel")) else ""})
        ui.df_with_help(df, **kw)
    else:
        st.caption("Tidak tersedia untuk run ini.")


def _utama(s):
    return s.get("metode_utama") or engine.pilih_utama(s.get("urutan") or [m["metode"] for m in s.get("metrik", [])] or ["-"])


def _spesifikasi(s, sheets):
    sp = dict(s.get("spesifikasi") or {})
    if not sp and "Penjelasan_Metode" in sheets:
        pm = sheets["Penjelasan_Metode"]
        sp = {r["Metode"]: str(r["Spesifikasi terpilih"]) for _, r in pm.iterrows() if pd.notna(r.get("Spesifikasi terpilih"))}
    return sp


def ringkasan(s, sheets):
    met = sheets.get("Metrik_Error_Backtest")
    urut = list(met["Metode"]) if met is not None else [m["metode"] for m in s.get("metrik", [])]
    utama = _utama(s)
    rm = met.set_index("Metode") if met is not None else pd.DataFrame()
    n = len(urut)

    # ---- pemilih metode yang disorot
    def lbl(m):
        if m in rm.index:
            r = rm.loc[m]
            return f"{m} · peringkat {int(r['Peringkat'])} · RMSE {ui.fmt(r['RMSE'], 3)}" + (" · pembanding" if m in engine.BENCH else "")
        return m
    c1, c2 = st.columns([1.3, 2])
    sorot = c1.selectbox("Sorot metode", urut, index=urut.index(utama) if utama in urut else 0, format_func=lbl,
                         help="Semua metode tetap tampil sebagai garis abu-abu. Metode yang dipilih diberi warna beserta rentang kemungkinannya.")
    c2.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    c2.caption(f"Metode utama run ini: **{utama}**. " + ("Naive dan Rata-rata 8Q adalah pembanding sederhana, dipakai untuk mengukur apakah model lain memberi nilai tambah."))

    # ---- KPI metode yang disorot
    tah = sheets.get("Pertumbuhan_Tahunan")
    th = {}
    if tah is not None and sorot in set(tah["Metode"]):
        rr = tah[tah["Metode"] == sorot].iloc[0]
        th = {str(c): rr[c] for c in tah.columns if c != "Metode"}
    elif sorot == utama:
        th = s.get("tahunan", {})
    k = st.columns(4)
    yrs = [y for y in th if pd.notna(th[y])][-2:]
    for i, y in enumerate(yrs):
        ui.kpi(k[i], f"Tumbuh {y}", ui.fmt(th[y], 2, True), "total 4 triwulan" if s.get("mode") == "level" else "rata-rata yoy 4 triwulan", ui.g("Pertumbuhan tahunan"))
    if sorot in rm.index:
        r = rm.loc[sorot]
        ui.kpi(k[2], "RMSE backtest", ui.fmt(r["RMSE"], 3), f"peringkat {int(r['Peringkat'])} dari {n}", ui.g("RMSE"))
        ui.kpi(k[3], "Akurasi arah", ui.fmt(r.get("Akurasi arah (%)"), 0, True) if pd.notna(r.get("Akurasi arah (%)")) else "-",
               f"{int(r.get('Jumlah titik uji', 0) or 0)} titik uji", ui.g("Akurasi arah"))

    # ---- grafik besar + tabel per triwulan
    l, rcol = st.columns([2.2, 1])
    ser, ci = sheets.get("Series_Aktual_Proyeksi"), sheets.get("Proyeksi_dengan_CI")
    with l:
        st.markdown(f"**Pertumbuhan yoy {s.get('label_target', '')}: aktual dan proyeksi semua metode**")
        ch = ui.chart_semua(ser, ci, sorot) if ser is not None else ui.chart_proyeksi(s)
        if ch is not None:
            st.altair_chart(ch, use_container_width=True)
        st.caption(f"Hitam = aktual · abu-abu = metode lain · berwarna = {sorot}, area muda = rentang kemungkinan (selang kepercayaan). Arahkan kursor ke garis untuk melihat nama metode.")
    with rcol:
        st.markdown(f"**Proyeksi per triwulan · {sorot}**")
        if ci is not None and sorot in set(ci["Metode"]):
            pr = ci[ci["Metode"] == sorot][["Periode", "Proyeksi", "Lower", "Upper"]].copy()
        else:
            py = sheets.get("Proyeksi_yoy")
            pr = pd.DataFrame()
            if py is not None and sorot in py:
                pr = pd.DataFrame({"Periode": py.iloc[:, 0], "Proyeksi": py[sorot]})
        if len(pr):
            pr["Periode"] = pr["Periode"].astype(str)
            cols = [c for c in ["Periode", "Proyeksi", "Lower", "Upper"] if c in pr]
            st.dataframe(pr, hide_index=True, use_container_width=True, column_order=cols,
                         column_config={"Periode": st.column_config.TextColumn("Periode", width="small"),
                                        "Proyeksi": st.column_config.NumberColumn("yoy (%)", format="%.2f", help=ui.g("yoy")),
                                        "Lower": st.column_config.NumberColumn("Bawah", format="%.2f", help=ui.g("Selang kepercayaan")),
                                        "Upper": st.column_config.NumberColumn("Atas", format="%.2f", help=ui.g("Selang kepercayaan"))})
        if sorot == "Ensemble" and s.get("bobot_ensemble"):
            st.markdown("**Bobot Ensemble**", help=ui.g("Bobot Ensemble"))
            st.altair_chart(ui.chart_bobot(s["bobot_ensemble"]), use_container_width=True)
        sp = _spesifikasi(s, sheets).get(sorot)
        if sp and sorot != "Ensemble":
            st.caption(f"Spesifikasi {sorot}: {sp}")

    # ---- rangkuman model
    st.markdown("#### Rangkuman model")
    if met is not None:
        nonb = met[~met["Metode"].isin(engine.BENCH)]
        top = nonb.head(3)
        naive = met[met["Metode"] == "Naive"]
        rm_naive = float(naive["RMSE"].iloc[0]) if len(naive) else None
        lebih_baik = nonb[nonb["RMSE"] < rm_naive] if rm_naive is not None else nonb
        arah = nonb.dropna(subset=["Akurasi arah (%)"]).sort_values("Akurasi arah (%)", ascending=False).head(1) if "Akurasi arah (%)" in nonb else pd.DataFrame()
        ind = s.get("indikator") or []
        sp = _spesifikasi(s, sheets)
        arx = sp.get("ARIMAX", "")
        teks = [f"Tiga model dengan error backtest terkecil: " + ", ".join(f"<b>{r['Metode']}</b> (RMSE {ui.fmt(r['RMSE'], 3)})" for _, r in top.iterrows()) + "."]
        if rm_naive is not None:
            teks.append(f"Pembanding Naive memiliki RMSE {ui.fmt(rm_naive, 3)}; <b>{len(lebih_baik)} dari {len(nonb)}</b> model lain lebih akurat dari pembanding ini"
                        + (f" ({', '.join(lebih_baik['Metode'].head(6))}{'…' if len(lebih_baik) > 6 else ''})." if len(lebih_baik) else "."))
        if len(arah):
            teks.append(f"Arah naik/turun paling sering tepat: <b>{arah.iloc[0]['Metode']}</b> ({ui.fmt(arah.iloc[0]['Akurasi arah (%)'], 0, True)}).")
        teks.append("Indikator pendukung: " + (", ".join(f"<b>{i}</b>" for i in ind) if ind else "tidak ada") + "."
                    + (f" ARIMAX memilih {m_.group(1).strip().rstrip(',')}." if (m_ := re.search(r"indikator:\s*([^()]+)", arx)) else ""))
        rh = sheets.get("RMSE_per_Horizon")
        if rh is not None:
            hc = [c for c in rh.columns if str(c).startswith("h=")]
            rn = rh[~rh["Metode"].isin(engine.BENCH)]
            if hc and len(rn):
                best_h = [f"{c}: {rn.loc[rn[c].idxmin(), 'Metode']}" for c in hc if rn[c].notna().any()]
                teks.append("Terbaik per horizon: " + " · ".join(best_h) + ".")
        st.markdown('<div class="ringkas">' + "<br>".join(teks) + "</div>", unsafe_allow_html=True)
        st.markdown("")
        tb = met[["Peringkat", "Metode", "RMSE", "MAE", "Akurasi arah (%)"]].copy()
        tb["Akurasi arah (%)"] = pd.to_numeric(tb["Akurasi arah (%)"], errors="coerce")
        tb["Spesifikasi"] = tb["Metode"].map(lambda m: "pembanding" if m in engine.BENCH else sp.get(m, ""))
        st.dataframe(tb, hide_index=True, use_container_width=True,
                     column_config={"Peringkat": st.column_config.NumberColumn("#", width="small"),
                                    "RMSE": st.column_config.NumberColumn("RMSE ↓", format="%.3f", help=ui.g("RMSE")),
                                    "MAE": st.column_config.NumberColumn("MAE ↓", format="%.3f", help=ui.g("MAE")),
                                    "Akurasi arah (%)": st.column_config.NumberColumn("Arah ↑ (%)", format="%.0f", help=ui.g("Akurasi arah")),
                                    "Spesifikasi": st.column_config.TextColumn(width="large")})
    py = sheets.get("Proyeksi_yoy")
    if py is not None:
        with st.expander("Proyeksi per triwulan, semua metode"):
            py = py.rename(columns={py.columns[0]: "Periode"})
            py["Periode"] = py["Periode"].astype(str)
            ui.df_with_help(py)


def detail(run):
    s = run.get("summary") or {}
    st_ = run.get("settings") or {}
    if st.button("← Semua run"):
        st.session_state.pop("run_terpilih", None)
        st.rerun()
    info_waktu = f"selesai dalam {ui.fmt(s.get('durasi_detik'), 0)} detik" if s.get("durasi_detik") else (s.get("sumber") or "")
    ui.header(f"Detail run · {tgl(run['created_at'])} · {info_waktu}", run.get("name", "Run"),
              run.get("note") or None)
    excel = file_bytes(run["excel_path"])
    charts = ui.read_charts(file_bytes(run["charts_path"]))
    b = st.columns([1, 1, 1, 3])
    b[0].download_button("⬇ Unduh Excel", excel, f"{run.get('name', 'hasil')}.xlsx".replace("/", "-"),
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)
    b[1].download_button("⬇ Grafik (.zip)", file_bytes(run["charts_path"]), "grafik.zip", "application/zip", use_container_width=True)
    if b[2].button("↻ Jalankan ulang", use_container_width=True, help="Buka pengaturan run ini untuk dijalankan lagi, misalnya dengan data terbaru."):
        st.session_state["prefill"] = {"dataset_id": run.get("dataset_id"), "settings": st_, "name": f"{run.get('name')} (ulang)", "note": run.get("note") or ""}
        nav.go("jalankan")
    ui.chips([f"Target: {s.get('target')}", f"Data {s.get('data_awal')} s.d. {s.get('data_akhir')}", f"Proyeksi s.d. {s.get('proyeksi_sampai')}",
              f"Mode {s.get('mode')}", "Indikator: " + (", ".join(s.get("indikator", [])) or "-"),
              f"{len(s.get('metode_aktif', []))} metode" + (" + Ensemble" if s.get("bobot_ensemble") else ""),
              "Add-factor: " + (", ".join(f"{k} {v:+.2f}" for k, v in (st_.get("PENYESUAIAN") or {}).items() if v) or "tidak ada")])

    sheets = ui.read_excel_sheets(excel)
    tabs = st.tabs(["Ringkasan", "Proyeksi per metode", "Metrik error", "Backtest", "Musiman & jarak yoy", "Diagnostik", "Validasi data", "Pengaturan", "Semua grafik"])
    with tabs[0]:
        ringkasan(s, sheets)
    with tabs[1]:
        st.markdown("**Proyeksi yoy semua metode (sudah termasuk add-factor)**")
        _sheet(sheets, "Proyeksi_yoy")
        st.markdown("**Proyeksi dengan selang kepercayaan**")
        _sheet(sheets, "Proyeksi_dengan_CI")
        st.markdown("**Pertumbuhan tahunan**", help=ui.g("Pertumbuhan tahunan"))
        _sheet(sheets, "Pertumbuhan_Tahunan")
        if "02_proyeksi_semua_metode.png" in charts:
            st.image(charts["02_proyeksi_semua_metode.png"], use_container_width=True)
        with st.expander("Proyeksi model murni (tanpa add-factor) dan level"):
            _sheet(sheets, "Proyeksi_yoy_Model_Murni")
            _sheet(sheets, "Proyeksi_Level")
    with tabs[2]:
        st.caption("↓ lower better (RMSE, MAE, sMAPE, MASE, Theil's U) · ↑ higher better (akurasi arah) · bias: makin dekat nol makin baik. Arahkan kursor ke judul kolom untuk penjelasan.")
        _sheet(sheets, "Metrik_Error_Backtest")
        st.markdown("**RMSE per horizon**", help=ui.g("Horizon (h)"))
        _sheet(sheets, "RMSE_per_Horizon")
        c1, c2 = st.columns(2)
        for c, n in zip((c1, c2), ("04_perbandingan_error.png", "05_rmse_per_horizon.png")):
            if n in charts:
                c.image(charts[n], use_container_width=True)
    with tabs[3]:
        st.caption(ui.g("Backtest"))
        if "06_backtest_h1.png" in charts:
            st.image(charts["06_backtest_h1.png"], use_container_width=True)
        with st.expander("Detail semua titik backtest"):
            _sheet(sheets, "Detail_Backtest")
    with tabs[4]:
        for n, t in (("Cek_Q4_vs_Q3", "Cek Q4 dibanding Q3"), ("Pola_yoy_Historis", "Pola yoy historis per triwulan"), ("Cek_Jarak_yoy", "Jarak yoy antartriwulan"),
                     ("Cek_Pola_Musiman", "Cek pola musiman (mode level)"), ("Proyeksi_qtq", "Proyeksi qtq (mode level)")):
            if n in sheets:
                st.markdown(f"**{t}**")
                _sheet(sheets, n)
        if "07_pola_musiman_qtq.png" in charts:
            st.image(charts["07_pola_musiman_qtq.png"], use_container_width=True)
    with tabs[5]:
        _sheet(sheets, "Diagnostik_InSample")
    with tabs[6]:
        _sheet(sheets, "Validasi_Data")
        st.markdown("**Log penanganan outlier**", help=ui.g("Penanganan outlier"))
        _sheet(sheets, "Log_Pembersihan")
        if "01_data_historis.png" in charts:
            st.image(charts["01_data_historis.png"], use_container_width=True)
    with tabs[7]:
        _sheet(sheets, "Pengaturan")
        _sheet(sheets, "Penjelasan_Metode")
    with tabs[8]:
        for n, img in charts.items():
            st.markdown(f"**{GRAFIK.get(n, n)}**")
            st.image(img, use_container_width=True)

    with st.expander("Hapus run ini"):
        if st.button("Hapus permanen", type="secondary"):
            be = get_backend()
            be.delete_file(run["excel_path"])
            be.delete_file(run["charts_path"])
            be.delete("runs", uid(), run["id"])
            st.session_state.pop("run_terpilih", None)
            st.rerun()


def impor_colab():
    with st.expander("⬆ Impor hasil run dari Google Colab (.zip)", expanded=not st.session_state.get("_ada_run", True)):
        st.caption("Unggah zip hasil notebook Colab (berisi hasil_proyeksi.xlsx dan grafik PNG). Bila di dalam zip ada file data "
                   "(mis. Indikator_Makroekonomi_DIY.xlsx), file itu ikut disimpan sebagai dataset. Run langsung masuk riwayat tanpa dijalankan ulang.")
        up = st.file_uploader("Zip hasil Colab", type=["zip"], key="impor_zip", label_visibility="collapsed")
        if not up:
            return
        from core import impor
        import hashlib
        raw = up.getvalue()
        h = hashlib.md5(raw).hexdigest()
        if st.session_state.get("impor_hash") == h:
            st.success("Zip ini sudah diimpor.")
            return
        try:
            isi = impor.baca_zip(raw)
            summary, settings = impor.ringkasan_dari_excel(isi["excel"])
        except ValueError as e:
            st.error(str(e))
            return
        dres = impor.cek_data(isi["data_bytes"])
        st.markdown(f"**Terbaca:** target {summary['target']}, data {summary['data_awal']} s.d. {summary['data_akhir']}, proyeksi s.d. "
                    f"{summary['proyeksi_sampai']}, metode utama {summary['metode_utama']} (RMSE {ui.fmt(summary['rmse_terbaik'], 3)}). "
                    + (f"File data **{isi['data_name']}** ikut disimpan sebagai dataset." if dres else "Tidak ada file data yang valid di zip; run disimpan tanpa dataset."))
        c1, c2 = st.columns([1, 1.4])
        base = isi["data_name"].rsplit(".", 1)[0].replace("_", " ") if isi["data_name"] else summary["target"]
        nama = c1.text_input("Nama run", value=f"{base} · hasil Colab")
        note = c2.text_input("Catatan", value="diimpor dari Google Colab")
        if st.button("Simpan ke riwayat", type="primary"):
            from core.common import now_iso
            from core.storage import new_id
            be = get_backend()
            ds_id = None
            if dres:
                ds_id = new_id()
                dp = f"{uid()}/datasets/{ds_id}.xlsx"
                be.put_file(dp, isi["data_bytes"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                row = {"id": ds_id, "user_id": uid(), "name": isi["data_name"].rsplit(".", 1)[0].replace("_", " "), "filename": isi["data_name"],
                       "sheet": dres["sheet"], "storage_path": dp, "info": dres["info"], "labels": dres["labels"], "created_at": now_iso()}
                be.insert("datasets", row)
                st.session_state["dataset_aktif"] = row
            rid = new_id()
            xp, cp = f"{uid()}/runs/{rid}/hasil_proyeksi.xlsx", f"{uid()}/runs/{rid}/grafik.zip"
            be.put_file(xp, isi["excel"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            be.put_file(cp, isi["charts_zip"], "application/zip")
            be.insert("runs", {"id": rid, "user_id": uid(), "dataset_id": ds_id, "name": nama.strip() or "Hasil Colab", "note": note.strip(),
                               "settings": settings, "summary": summary, "status": "diimpor", "excel_path": xp, "charts_path": cp,
                               "created_at": now_iso()})
            st.session_state["impor_hash"] = h
            st.session_state["run_terpilih"] = rid
            st.rerun()


def show():
    runs = daftar_run()
    st.session_state["_ada_run"] = bool(runs)
    rid = st.session_state.get("run_terpilih")
    if rid:
        run = next((r for r in runs if r["id"] == rid), None)
        if run:
            detail(run)
            return
        st.session_state.pop("run_terpilih", None)
    ui.header("Semua run", "Riwayat Run")
    impor_colab()
    if not runs:
        st.info("Belum ada run. Buat di menu **Jalankan Proyeksi**, atau impor hasil dari Google Colab.")
        return
    dsname = {d["id"]: d["name"] for d in daftar_dataset()}
    q = st.text_input("Cari run", placeholder="cari nama atau catatan run", label_visibility="collapsed")
    for r in runs:
        if q and q.lower() not in f"{r.get('name', '')} {r.get('note', '')}".lower():
            continue
        s = r.get("summary") or {}
        pr = s.get("proyeksi") or []
        ut = _utama(s)
        met = {m["metode"]: m for m in s.get("metrik", [])}
        top = [m for m in (s.get("urutan") or list(met)) if m not in engine.BENCH][:3]
        th = s.get("tahunan") or {}
        yrs = [y for y in th if th[y] is not None][-2:]
        with st.container(border=True):
            a1, a2 = st.columns([5, 1])
            a1.markdown(f"**{r.get('name')}**  \n<small>{tgl(r['created_at'])} · dataset {dsname.get(r.get('dataset_id'), '(dihapus)')}"
                        + (f" · {r['note']}" if r.get("note") else "") + "</small>", unsafe_allow_html=True)
            if a2.button("Buka →", key=f"buka_{r['id']}", use_container_width=True):
                st.session_state["run_terpilih"] = r["id"]
                st.rerun()
            k = st.columns(4)
            ui.kpi(k[0], "Metode utama", ut, f"RMSE {ui.fmt((met.get(ut) or {}).get('rmse', s.get('rmse_terbaik')), 3)}", ui.g("RMSE"))
            if pr:
                ui.kpi(k[1], f"yoy {pr[0].get('periode')}", ui.fmt(pr[0].get("yoy"), 2, True), f"target {s.get('target')}")
            for i, y in enumerate(yrs):
                ui.kpi(k[2 + i], f"Tumbuh {y}", ui.fmt(th[y], 2, True), f"proyeksi s.d. {s.get('proyeksi_sampai')}", ui.g("Pertumbuhan tahunan"))
            ui.chips(["3 model terbaik: " + (", ".join(top) or "-"), "Indikator: " + (", ".join(s.get("indikator") or []) or "-"),
                      f"Mode {s.get('mode')}"])
