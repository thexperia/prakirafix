import numpy as np
import pandas as pd
import streamlit as st

from core import engine, nav, ui, validasi
from core.common import daftar_dataset, file_bytes, load_dataset, now_iso, uid
from core.storage import get_backend, new_id

KELOMPOK = [
    ("Benchmark", ["Naive", "Rata-rata 8Q"]),
    ("Pola target sendiri", ["ARIMA", "ETS", "Theta"]),
    ("Pakai indikator", ["ARIMAX", "VAR", "BVAR"]),
    ("Regresi dan ML", ["Ridge", "Elastic Net", "Faktor (PCA)", "Random Forest", "Gradient Boosting"]),
    ("Pola musiman (mode level)", ["SARIMA Musiman", "ETS Musiman"]),
]
PANDEMI = (pd.Period("2020Q1", "Q"), pd.Period("2021Q4", "Q"))
MAX_PROYEKSI = pd.Period("2028Q4", "Q")  # tabel tanggal Lebaran di mesin proyeksi s.d. 2029


def _corr(df, target, cols):
    rows = []
    ok = [not (PANDEMI[0] <= p <= PANDEMI[1]) for p in df.index]
    for c in cols:
        a = df[c].corr(df[target])
        b = df.loc[ok, c].corr(df.loc[ok, target])
        rows.append({"Pakai": True, "Kode": c, "Korelasi semua": round(a, 2) if pd.notna(a) else None,
                     "Korelasi tanpa pandemi": round(b, 2) if pd.notna(b) else None,
                     "Data sampai": str(df[c].last_valid_index())})
    return pd.DataFrame(rows)


def show():
    ui.header("Pengaturan run", "Jalankan Proyeksi", "Pilih data, target, indikator, dan metode. Arahkan kursor ke ⓘ untuk penjelasan istilah.")
    dsets = daftar_dataset()
    if not dsets:
        st.info("Belum ada dataset. Unggah dulu di menu **Data**.")
        if st.button("Ke menu Data"):
            nav.go("data")
        return
    pre = st.session_state.get("prefill") or {}
    aktif = pre.get("dataset_id") or (st.session_state.get("dataset_aktif") or {}).get("id")
    idx = next((i for i, d in enumerate(dsets) if d["id"] == aktif), 0)

    with st.container(border=True):
        st.subheader("Data dan target")
        c = st.columns(3)
        ds = c[0].selectbox("Dataset", dsets, index=idx, format_func=lambda d: d["name"])
        res = load_dataset(ds)
        if not res["ok"]:
            st.error("Dataset ini tidak lolos pengecekan. Perbaiki lalu unggah ulang di menu Data.")
            return
        df, labels = res["df"], res["labels"]
        cols = list(df.columns)
        lvl_cand = validasi.tebak_pasangan_level(cols, df)
        tgt_opts = [x for x in cols if x not in lvl_cand] or cols
        s = pre.get("settings", {})
        t_def = s.get("TARGET") if s.get("TARGET") in tgt_opts else ("GPDRB" if "GPDRB" in tgt_opts else tgt_opts[0])
        target = c[1].selectbox("Target yang diproyeksi", tgt_opts, index=tgt_opts.index(t_def),
                                format_func=lambda x: f"{x} · {labels.get(x, x)}", help=ui.g("Target"))
        lv_opts = ["(tanpa level)"] + [x for x in cols if x != target]
        if s.get("TARGET_LEVEL") in lv_opts:
            lv_def = s["TARGET_LEVEL"]
        elif target == "GPDRB" and "PDRB_ADHK" in cols:
            lv_def = "PDRB_ADHK"
        elif len(lvl_cand) == 1 and lvl_cand[0] != target:
            lv_def = lvl_cand[0]
        else:
            lv_def = "(tanpa level)"
        level = c[2].selectbox("Kolom level (opsional)", lv_opts, index=lv_opts.index(lv_def),
                               format_func=lambda x: x if x.startswith("(") else f"{x} · {labels.get(x, x)}", help=ui.g("Kolom level"))
        level = None if level.startswith("(") else level
        st.caption(f"Mode: **{'level (pola musiman ikut dimodelkan)' if level else 'yoy'}**. " + ("" if level else "Pilih kolom level untuk mengaktifkan metode musiman."))

        tl = df[target].last_valid_index()
        per = [p for p in df.index if df[target].first_valid_index() <= p <= tl]
        c2 = st.columns(3)
        mulai = c2[0].selectbox("Data mulai", per, index=per.index(pd.Period(s["DATA_MULAI"], "Q")) if s.get("DATA_MULAI") and pd.Period(s["DATA_MULAI"], "Q") in per else 0,
                                format_func=str, help=ui.g("Data mulai / Data sampai"))
        per2 = [p for p in per if p > mulai]
        sampai = c2[1].selectbox("Data sampai", per2, index=len(per2) - 1, format_func=lambda p: f"{p}{' (terakhir)' if p == tl else ''}",
                                 help=ui.g("Data mulai / Data sampai"))
        fut = list(pd.period_range(sampai + 1, MAX_PROYEKSI, freq="Q"))
        dflt = pd.Period(f"{sampai.year + 1}Q4", "Q")
        proj = c2[2].selectbox("Proyeksi sampai", fut, index=fut.index(dflt) if dflt in fut else len(fut) - 1, format_func=str, help=ui.g("Proyeksi sampai"))

    with st.container(border=True):
        st.subheader("Indikator pendukung")
        ind_cols = [x for x in cols if x not in (target, level)]
        if not ind_cols:
            st.caption("File ini tidak punya indikator pendukung. Hanya metode univariat yang bisa dipakai.")
            chosen = []
        else:
            tbl = _corr(df.loc[mulai:sampai], target, ind_cols)
            if s.get("INDIKATOR_DIPAKAI"):
                tbl["Pakai"] = tbl["Kode"].isin(s["INDIKATOR_DIPAKAI"])
            tbl.insert(2, "Nama", [labels.get(k, k) for k in tbl["Kode"]])
            ed = st.data_editor(tbl, hide_index=True, use_container_width=True, disabled=["Kode", "Nama", "Korelasi semua", "Korelasi tanpa pandemi", "Data sampai"],
                                column_config={"Pakai": st.column_config.CheckboxColumn(help=ui.g("Indikator pendukung")),
                                               "Korelasi semua": st.column_config.NumberColumn(help=ui.g("Korelasi"), format="%.2f"),
                                               "Korelasi tanpa pandemi": st.column_config.NumberColumn(help=ui.g("Korelasi tanpa pandemi"), format="%.2f")},
                                key=f"ind_{ds['id']}_{target}_{level}")
            chosen = list(ed.loc[ed["Pakai"], "Kode"])
            st.caption("Saran: pilih 3 s.d. 8 indikator. Terlalu banyak indikator dengan data pendek membuat model mudah meleset.")
        var_def = [v for v in s.get("VAR_INDIKATOR", []) if v in chosen] or \
            sorted(chosen, key=lambda k: -abs(df[k].corr(df[target]) if pd.notna(df[k].corr(df[target])) else 0))[:1]
        var_ind = st.multiselect("Indikator untuk VAR dan BVAR", chosen, default=var_def, help=ui.g("Indikator VAR/BVAR")) if chosen else []

    with st.container(border=True):
        st.subheader("Metode")
        m_def = s.get("METODE") or engine.DEFAULTS["METODE"]
        metode = {}
        cc = st.columns(len(KELOMPOK))
        for col, (grp, ms) in zip(cc, KELOMPOK):
            col.markdown(f"<small><b style='color:{ui.CORAL}'>{grp.upper()}</b></small>", unsafe_allow_html=True)
            for m in ms:
                dis, why = False, ""
                if m in engine.METODE_BUTUH_INDIKATOR and not chosen:
                    dis, why = True, " (butuh indikator)"
                if m in ("VAR", "BVAR") and chosen and not var_ind:
                    dis, why = True, " (pilih indikator VAR)"
                if m in engine.METODE_LEVEL and not level:
                    dis, why = True, " (butuh kolom level)"
                metode[m] = col.checkbox(m + why, value=bool(m_def.get(m, False)) and not dis, disabled=dis, help=ui.g(m), key=f"m_{m}")
        e1, e2, e3 = st.columns([1, 1.4, 1])
        ens = e1.checkbox("Ensemble", value=s.get("PAKAI_ENSEMBLE", True), help=ui.g("Ensemble"))
        cara = e2.selectbox("Cara menggabung", ["inverse-rmse", "top", "median"], index=["inverse-rmse", "top", "median"].index(s.get("ENSEMBLE_CARA", "inverse-rmse")),
                            format_func={"inverse-rmse": "Bobot sesuai akurasi (bawaan)", "top": "Hanya N metode terbaik", "median": "Nilai tengah semua metode"}.get, disabled=not ens)
        topn = e3.number_input("N terbaik", 2, 10, int(s.get("ENSEMBLE_TOP", 3)), disabled=not (ens and cara == "top"))

    a, b = st.columns(2)
    with a:
        with st.container(border=True):
            st.subheader("Pengaturan lanjutan")
            dum = st.toggle("Penanda pandemi", s.get("PAKAI_DUMMY_PANDEMI", True), help=ui.g("Penanda pandemi"))
            kal = st.toggle("Efek Ramadan dan Lebaran", s.get("PAKAI_EFEK_KALENDER", True), help=ui.g("Efek Ramadan dan Lebaran"))
            outl = st.toggle("Bersihkan outlier indikator", s.get("BERSIHKAN_OUTLIER", True), help=ui.g("Bersihkan outlier"))
            cepat = st.toggle("Mode cepat (6 backtest)", s.get("_cepat", False), help=ui.g("Mode cepat"))
            x1, x2 = st.columns(2)
            bt_pre = s.get("BATAS_PERUBAHAN_YOY", "otomatis")
            bmode = x1.selectbox("Batas lompatan yoy", ["Otomatis", "Manual", "Tanpa batas"],
                                 index=0 if bt_pre == "otomatis" else (2 if bt_pre is None else 1), help=ui.g("Batas lompatan yoy"))
            bval = x2.number_input("Batas manual (poin)", 0.1, 5.0, float(bt_pre) if isinstance(bt_pre, (int, float)) else 0.75, 0.05, disabled=bmode != "Manual")
            ci = st.select_slider("Selang kepercayaan", [80, 90, 95], value=s.get("SELANG_KEPERCAYAAN", 90), format_func=lambda v: f"{v}%", help=ui.g("Selang kepercayaan"))
    with b:
        with st.container(border=True):
            st.subheader("Add-factor")
            st.caption(ui.g("Add-factor"))
            fp = pd.period_range(sampai + 1, proj, freq="Q")
            pre_af = s.get("PENYESUAIAN", {})
            af = pd.DataFrame({"Periode": [str(p) for p in fp], "Add-factor (poin yoy)": [float(pre_af.get(str(p), 0.0)) for p in fp]})
            af_ed = st.data_editor(af, hide_index=True, use_container_width=True, disabled=["Periode"], height=min(38 * (len(af) + 1), 330),
                                   column_config={"Add-factor (poin yoy)": st.column_config.NumberColumn(format="%+.2f", step=0.05, min_value=-5.0, max_value=5.0)},
                                   key=f"af_{sampai}_{proj}")
            y = df[target].dropna()
            q = pd.DataFrame({"y": y.values, "yr": y.index.year, "q": y.index.quarter}).pivot(index="yr", columns="q", values="y")
            q = q[~q.index.isin([2020, 2021])].dropna(subset=[3, 4]) if {3, 4} <= set(q.columns) else pd.DataFrame()
            if len(q):
                d = (q[4] - q[3])
                st.caption(f"Acuan historis (tahun normal): yoy Q4 dibanding Q3 rata-rata **{d.mean():+.2f} poin**, Q4 lebih tinggi di {int((d > 0).sum())} dari {len(d)} tahun.")

    with st.container(border=True):
        n1, n2 = st.columns([1, 1.4])
        nama = n1.text_input("Nama run", value=pre.get("name") or f"{ds['name']} · {target}")
        catatan = n2.text_input("Catatan (opsional)", value=pre.get("note", ""), placeholder="mis. add-factor Q4 +0,10, tanpa indikator wisatawan")
        n_obs = len(df.loc[mulai:sampai])
        bt = min(6 if cepat else 12, n_obs - 17)
        st.caption(f"Data {mulai} s.d. {sampai} ({n_obs} triwulan) · proyeksi {len(fp)} triwulan · backtest {bt} kali · perkiraan waktu ± {'1' if cepat else '2'} menit.")
        go = st.button("▶ Jalankan proyeksi", type="primary")

    if not go:
        return
    if bt < 4:
        st.error("Data terlalu pendek untuk diuji. Mundurkan Data mulai atau tambah data.")
        return
    if not any(metode.values()):
        st.error("Pilih minimal satu metode.")
        return
    settings = {
        "TARGET": target, "TARGET_LEVEL": level, "DATA_MULAI": str(mulai), "DATA_SAMPAI": str(sampai), "PROYEKSI_SAMPAI": str(proj),
        "INDIKATOR_DIPAKAI": chosen, "VAR_INDIKATOR": var_ind or (chosen[:1] if chosen else []), "METODE": metode,
        "PAKAI_ENSEMBLE": ens, "ENSEMBLE_CARA": cara, "ENSEMBLE_TOP": int(topn), "PAKAI_DUMMY_PANDEMI": dum,
        "PAKAI_EFEK_KALENDER": kal, "BERSIHKAN_OUTLIER": outl, "JUMLAH_UJI_BACKTEST": int(bt), "SELANG_KEPERCAYAAN": int(ci),
        "BATAS_PERUBAHAN_YOY": "otomatis" if bmode == "Otomatis" else (None if bmode == "Tanpa batas" else float(bval)),
        "PENYESUAIAN": {r["Periode"]: float(r["Add-factor (poin yoy)"] or 0) for _, r in af_ed.iterrows()},
    }
    if sampai == tl:
        settings["DATA_SAMPAI"] = None
    bar = st.progress(0.0, text="Menyiapkan data...")
    try:
        with st.spinner("Proyeksi sedang berjalan. Jangan tutup halaman ini."):
            out = engine.run_projection(file_bytes(ds["storage_path"]), ds["sheet"], settings,
                                        progress=lambda f, m: bar.progress(min(0.05 + 0.85 * f, 0.9), text=m))
    except ValueError as e:
        bar.empty()
        st.error(f"Pengaturan belum tepat: {e}")
        return
    except Exception as e:  # noqa
        bar.empty()
        st.error(f"Proyeksi gagal dijalankan. Detail teknis: {e}")
        return
    bar.progress(0.95, text="Menyimpan hasil...")
    be = get_backend()
    rid = new_id()
    xp, cp = f"{uid()}/runs/{rid}/hasil_proyeksi.xlsx", f"{uid()}/runs/{rid}/grafik.zip"
    be.put_file(xp, out["excel"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    be.put_file(cp, out["charts_zip"], "application/zip")
    settings["_cepat"] = cepat
    be.insert("runs", {"id": rid, "user_id": uid(), "dataset_id": ds["id"], "name": nama.strip() or "Run tanpa nama", "note": catatan.strip(),
                       "settings": settings, "summary": out["summary"], "status": "selesai", "excel_path": xp, "charts_path": cp,
                       "created_at": now_iso()})
    bar.progress(1.0, text="Selesai")
    st.session_state.pop("prefill", None)
    st.session_state["run_terpilih"] = rid
    st.session_state["dataset_aktif"] = ds
    nav.go("riwayat")
