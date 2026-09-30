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
MAX_PROYEKSI = pd.Period("2028Q4", "Q")  # tabel tanggal Lebaran di mesin proyeksi s.d. 2029
BULAN = pd.period_range("2019-01", "2023-12", freq="M")
NAMA_BLN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
D = engine.DEFAULTS


def fmt_bln(p):
    return f"{NAMA_BLN[p.month - 1]} {p.year}"


def _bulan(txt, akhir):
    t = str(txt).upper()
    if "Q" in t:
        q = pd.Period(t, "Q")
        return q.asfreq("M", "end" if akhir else "start")
    return pd.Period(t, "M")


def _corr(df, target, cols, krisis):
    rows = []
    ok = [not (krisis[0] <= p <= krisis[1]) for p in df.index]
    for c in cols:
        a = df[c].corr(df[target])
        b = df.loc[ok, c].corr(df.loc[ok, target])
        rows.append({"Pakai": True, "Kode": c, "Korelasi semua": round(a, 2) if pd.notna(a) else None,
                     "Korelasi tanpa pandemi": round(b, 2) if pd.notna(b) else None, "Data sampai": str(df[c].last_valid_index())})
    return pd.DataFrame(rows)


def box(title, tip=None):
    c = st.container(border=True)
    c.subheader(title, help=tip)
    return c


def show():
    ui.header("Pengaturan run", "Jalankan Proyeksi", "Pilih data, target, indikator, dan metode. Arahkan kursor ke ikon ? untuk penjelasan istilah.")
    dsets = daftar_dataset()
    if not dsets:
        st.info("Belum ada dataset. Unggah dulu di menu **Data**.")
        if st.button("Ke menu Data"):
            nav.go("data")
        return
    pre = st.session_state.get("prefill") or {}
    s = pre.get("settings", {})
    aktif = pre.get("dataset_id") or (st.session_state.get("dataset_aktif") or {}).get("id")
    idx = next((i for i, d in enumerate(dsets) if d["id"] == aktif), 0)
    adv = st.toggle("Mode advanced: tampilkan pengaturan rinci tiap metode", value=bool(s.get("_advanced", False)), help=ui.g("Mode advanced"))

    # ---------------- A. data & target
    with box("Data dan target"):
        ds = st.selectbox("Dataset", dsets, index=idx, format_func=lambda d: d["name"])
        res = load_dataset(ds)
        if not res["ok"]:
            st.error("Dataset ini tidak lolos pengecekan. Perbaiki lalu unggah ulang di menu Data.")
            return
        df, labels = res["df"], res["labels"]
        cols = list(df.columns)
        lvl_cand = validasi.tebak_pasangan_level(cols, df)
        tgt_opts = [x for x in cols if x not in lvl_cand] or cols
        t_def = s.get("TARGET") if s.get("TARGET") in tgt_opts else ("GPDRB" if "GPDRB" in tgt_opts else tgt_opts[0])
        c = st.columns(2)
        target = c[0].selectbox("Target yang diproyeksi", tgt_opts, index=tgt_opts.index(t_def), help=ui.g("Target"))
        c[0].caption(f"{target}: {labels.get(target, target)}")
        lv_opts = ["(tanpa level)"] + [x for x in cols if x != target]
        if s.get("TARGET_LEVEL") in lv_opts:
            lv_def = s["TARGET_LEVEL"]
        elif target == "GPDRB" and "PDRB_ADHK" in cols:
            lv_def = "PDRB_ADHK"
        elif len(lvl_cand) == 1 and lvl_cand[0] != target:
            lv_def = lvl_cand[0]
        else:
            lv_def = "(tanpa level)"
        level = c[1].selectbox("Kolom level (opsional)", lv_opts, index=lv_opts.index(lv_def), help=ui.g("Kolom level"))
        level = None if level.startswith("(") else level
        c[1].caption(f"{level}: {labels.get(level, level)} · mode level (pola musiman ikut dimodelkan)" if level
                     else "Mode yoy. Pilih kolom level untuk mengaktifkan metode musiman.")
        tl = df[target].last_valid_index()
        per = [p for p in df.index if df[target].first_valid_index() <= p <= tl]
        c2 = st.columns(3)
        m0 = pd.Period(s["DATA_MULAI"], "Q") if s.get("DATA_MULAI") else None
        mulai = c2[0].selectbox("Data mulai", per, index=per.index(m0) if m0 in per else 0, format_func=str, help=ui.g("Data mulai / Data sampai"))
        per2 = [p for p in per if p > mulai]
        sampai = c2[1].selectbox("Data sampai", per2, index=len(per2) - 1, format_func=lambda p: f"{p} (terakhir)" if p == tl else str(p),
                                 help=ui.g("Data mulai / Data sampai"))
        fut = list(pd.period_range(sampai + 1, MAX_PROYEKSI, freq="Q"))
        dflt = pd.Period(s["PROYEKSI_SAMPAI"], "Q") if s.get("PROYEKSI_SAMPAI") else pd.Period(f"{sampai.year + 1}Q4", "Q")
        proj = c2[2].selectbox("Proyeksi sampai", fut, index=fut.index(dflt) if dflt in fut else len(fut) - 1, format_func=str, help=ui.g("Proyeksi sampai"))

    # ---------------- B. penanda pandemi (dibutuhkan untuk korelasi tanpa pandemi)
    with box("Penanda pandemi", ui.g("Penanda pandemi")):
        dum = st.toggle("Pakai penanda pandemi", s.get("PAKAI_DUMMY_PANDEMI", True))
        pp, pr_ = s.get("PERIODE_PANDEMI", D["PERIODE_PANDEMI"]), s.get("PERIODE_REBOUND", D["PERIODE_REBOUND"])
        c = st.columns(4)
        pa = c[0].selectbox("Kontraksi mulai", BULAN, index=list(BULAN).index(_bulan(pp[0], False)), format_func=fmt_bln, disabled=not dum)
        pb = c[1].selectbox("Kontraksi selesai", BULAN, index=list(BULAN).index(_bulan(pp[1], True)), format_func=fmt_bln, disabled=not dum)
        reb = c[2].toggle("Tandai masa pemulihan", s.get("PAKAI_REBOUND", True), disabled=not dum, help=ui.g("Masa pemulihan (rebound)"))
        c3 = st.columns(4)
        ra = c3[0].selectbox("Pemulihan mulai", BULAN, index=list(BULAN).index(_bulan(pr_[0], False)), format_func=fmt_bln, disabled=not (dum and reb))
        rb = c3[1].selectbox("Pemulihan selesai", BULAN, index=list(BULAN).index(_bulan(pr_[1], True)), format_func=fmt_bln, disabled=not (dum and reb))
        if pb < pa or (reb and rb < ra):
            st.warning("Bulan selesai tidak boleh lebih awal dari bulan mulai.")
        st.caption("Triwulan yang hanya sebagian masuk periode diberi bobot sesuai porsi bulannya, misalnya Maret saja = 1/3.")
    krisis = (pa.asfreq("Q"), (rb if reb else pb).asfreq("Q"))

    # ---------------- C. indikator
    with box("Indikator pendukung", ui.g("Indikator pendukung")):
        ind_cols = [x for x in cols if x not in (target, level)]
        if not ind_cols:
            st.caption("File ini tidak punya indikator pendukung. Hanya metode univariat yang bisa dipakai.")
            chosen = []
        else:
            tbl = _corr(df.loc[mulai:sampai], target, ind_cols, krisis)
            if s.get("INDIKATOR_DIPAKAI") is not None and pre:
                tbl["Pakai"] = tbl["Kode"].isin(s["INDIKATOR_DIPAKAI"])
            tbl.insert(2, "Nama", [labels.get(k, k) for k in tbl["Kode"]])
            ed = st.data_editor(tbl, hide_index=True, use_container_width=True, disabled=["Kode", "Nama", "Korelasi semua", "Korelasi tanpa pandemi", "Data sampai"],
                                column_config={"Pakai": st.column_config.CheckboxColumn(width="small"),
                                               "Kode": st.column_config.TextColumn(width="medium"),
                                               "Nama": st.column_config.TextColumn(width="large"),
                                               "Korelasi semua": st.column_config.NumberColumn(help=ui.g("Korelasi"), format="%.2f"),
                                               "Korelasi tanpa pandemi": st.column_config.NumberColumn(help=ui.g("Korelasi tanpa pandemi"), format="%.2f")},
                                key=f"ind_{ds['id']}_{target}_{level}")
            chosen = list(ed.loc[ed["Pakai"], "Kode"])
            st.caption("Saran: pilih 3 s.d. 8 indikator. Terlalu banyak indikator dengan data pendek membuat model mudah meleset.")
        var_def = [v for v in s.get("VAR_INDIKATOR", []) if v in chosen] or \
            sorted(chosen, key=lambda k: -abs(df[k].corr(df[target]) if pd.notna(df[k].corr(df[target])) else 0))[:1]
        var_ind = st.multiselect("Indikator untuk VAR dan BVAR", chosen, default=var_def, help=ui.g("Indikator VAR/BVAR")) if chosen else []

    # ---------------- D. outlier
    with box("Penanganan outlier", ui.g("Penanganan outlier")):
        k = st.number_input("Batas deteksi (k)", 2.0, 8.0, float(s.get("BATAS_OUTLIER", D["BATAS_OUTLIER"])), 0.5, help=ui.g("Batas outlier (k)")) if adv \
            else float(s.get("BATAS_OUTLIER", D["BATAS_OUTLIER"]))
        pre_out = s.get("OUTLIER_MANUAL") or {}
        rows = []
        dsub = df.loc[mulai:sampai]
        for cc in chosen:
            x = dsub[cc].dropna()
            out = validasi.deteksi_outlier(x, k)
            med = x.median(); mad = 1.4826 * (x - med).abs().median()
            for p, v in out.items():
                rows.append({"Tangani": str(p) in pre_out.get(cc, []), "Indikator": cc, "Periode": str(p), "Nilai": round(float(v), 2),
                             "Batas bawah": round(med - k * mad, 2), "Batas atas": round(med + k * mad, 2),
                             "Keterangan": "masa pandemi/pemulihan" if dum and krisis[0] <= p <= krisis[1] else ""})
        manual = {}
        if rows:
            st.caption("Nilai berikut kemungkinan outlier. Centang yang ingin ditangani; yang tidak dicentang dibiarkan apa adanya. "
                       "Nilai di masa pandemi umumnya guncangan nyata, sehingga sebaiknya dibiarkan bila penanda pandemi aktif.")
            oed = st.data_editor(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                                 disabled=["Indikator", "Periode", "Nilai", "Batas bawah", "Batas atas", "Keterangan"], key=f"out_{ds['id']}_{k}_{len(chosen)}")
            for _, r in oed[oed["Tangani"]].iterrows():
                manual.setdefault(r["Indikator"], []).append(r["Periode"])
        else:
            st.caption("Tidak ada kemungkinan outlier pada indikator yang dipilih.")
        with st.expander("Tambah periode manual per indikator"):
            for cc in chosen:
                extra = st.multiselect(f"{cc}", [str(p) for p in dsub.index], default=[p for p in pre_out.get(cc, []) if p not in manual.get(cc, [])],
                                       key=f"extra_{cc}", help=labels.get(cc, cc))
                for p in extra:
                    if p not in manual.get(cc, []):
                        manual.setdefault(cc, []).append(p)
        cara = st.radio("Cara menangani", ["pangkas", "hapus"], horizontal=True, index=0 if s.get("OUTLIER_CARA", "pangkas") == "pangkas" else 1,
                        format_func={"pangkas": "Pangkas ke batas wajar", "hapus": "Hapus, lalu isi interpolasi"}.get)
        n_man = sum(len(v) for v in manual.values())
        st.caption(f"{n_man} nilai akan ditangani. Target ({target}) tidak diubah; guncangan pandemi pada target ditangani penanda pandemi.")

    # ---------------- E. metode
    with box("Metode"):
        m_def = s.get("METODE") or D["METODE"]
        metode = {}
        cc_ = st.columns(len(KELOMPOK))
        for col, (grp, ms) in zip(cc_, KELOMPOK):
            col.markdown(f"<div style='font-size:12px;font-weight:800;letter-spacing:1px;color:{ui.CORAL}'>{grp.upper()}</div>", unsafe_allow_html=True)
            for m in ms:
                dis, why = False, ""
                if m in engine.METODE_BUTUH_INDIKATOR and not chosen:
                    dis, why = True, "butuh indikator"
                if m in ("VAR", "BVAR") and chosen and not var_ind:
                    dis, why = True, "pilih indikator VAR"
                if m in engine.METODE_LEVEL and not level:
                    dis, why = True, "butuh kolom level"
                metode[m] = col.checkbox(m, value=bool(m_def.get(m, False)) and not dis, disabled=dis,
                                         help=ui.g(m) + (f" (Nonaktif: {why}.)" if why else ""), key=f"m_{m}")
        e = st.columns([1, 1.6, 1])
        ens = e[0].checkbox("Ensemble", value=s.get("PAKAI_ENSEMBLE", True), help=ui.g("Ensemble"))
        opsi = {"inverse-rmse": "Bobot sesuai akurasi", "top": "Hanya N metode terbaik", "median": "Nilai tengah semua metode"}
        cara_ens = e[1].selectbox("Cara menggabung", list(opsi), index=list(opsi).index(s.get("ENSEMBLE_CARA", "inverse-rmse")), format_func=opsi.get, disabled=not ens)
        topn = e[2].number_input("N terbaik", 2, 10, int(s.get("ENSEMBLE_TOP", 3)), disabled=not (ens and cara_ens == "top"))

    # ---------------- F. advanced per metode
    P = {}
    if adv:
        with box("Pengaturan rinci per metode", ui.g("Mode advanced")):
            st.caption("Biarkan nilai bawaan bila ragu. Nilai bawaan sama dengan notebook Colab.")
            g = lambda n: s.get(n, D[n])
            a = st.columns(3)
            with a[0]:
                st.markdown("**Rata-rata 8Q, ARIMA, ETS**")
                P["RATA2_JUMLAH_TRIWULAN"] = st.number_input("Jumlah triwulan untuk rata-rata", 2, 16, int(g("RATA2_JUMLAH_TRIWULAN")))
                P["ARIMA_MAX_PQ"] = st.number_input("Order ARIMA maksimum", 1, 4, int(g("ARIMA_MAX_PQ")), help=ui.g("Order ARIMA maksimum"))
                P["ETS_TREN"] = st.selectbox("Tren ETS", ["damped", "linear", "tanpa"], index=["damped", "linear", "tanpa"].index(g("ETS_TREN")), help=ui.g("Tren ETS"))
            with a[1]:
                st.markdown("**ARIMAX**")
                P["ARIMAX_JUMLAH_INDIKATOR"] = st.number_input("Jumlah indikator maksimum", 1, 8, int(g("ARIMAX_JUMLAH_INDIKATOR")), help=ui.g("Jumlah indikator ARIMAX"))
                P["ARIMAX_KORELASI_MIN"] = st.number_input("Korelasi minimum", 0.0, 0.9, float(g("ARIMAX_KORELASI_MIN")), 0.05, help=ui.g("Korelasi minimum ARIMAX"))
                P["ARIMAX_PILIH_TANPA_PANDEMI"] = st.checkbox("Pilih indikator dari korelasi tanpa pandemi", bool(g("ARIMAX_PILIH_TANPA_PANDEMI")))
                P["ARIMAX_PROYEKSI_INDIKATOR"] = st.selectbox("Proyeksi indikator", ["ar1", "rata2"], index=["ar1", "rata2"].index(g("ARIMAX_PROYEKSI_INDIKATOR")),
                                                              help=ui.g("Proyeksi indikator ARIMAX"))
                P["ARIMAX_MAX_PQ"] = st.number_input("Order ARIMAX maksimum", 0, 3, int(g("ARIMAX_MAX_PQ")))
            with a[2]:
                st.markdown("**VAR, BVAR, Faktor (PCA)**")
                P["VAR_MAXLAG"] = st.number_input("Lag VAR maksimum", 1, 8, int(g("VAR_MAXLAG")), help=ui.g("Lag VAR maksimum"))
                P["BVAR_LAG"] = st.number_input("Lag BVAR", 1, 6, int(g("BVAR_LAG")), help=ui.g("Lag dan ketatan BVAR"))
                P["BVAR_KETATAN"] = st.number_input("Ketatan BVAR", 0.05, 1.0, float(g("BVAR_KETATAN")), 0.05, help=ui.g("Lag dan ketatan BVAR"))
                P["FAKTOR_JUMLAH"] = st.number_input("Jumlah faktor PCA", 1, 5, int(g("FAKTOR_JUMLAH")), help=ui.g("Jumlah faktor PCA"))
            b = st.columns(3)
            with b[0]:
                st.markdown("**Random Forest**", help=ui.g("Parameter Random Forest"))
                P["RF_POHON"] = st.number_input("Jumlah pohon RF", 50, 1000, int(g("RF_POHON")), 50)
                P["RF_KEDALAMAN"] = st.number_input("Kedalaman maksimum RF", 1, 10, int(g("RF_KEDALAMAN")))
                P["RF_MIN_DAUN"] = st.number_input("Minimal data per daun RF", 1, 10, int(g("RF_MIN_DAUN")))
            with b[1]:
                st.markdown("**Gradient Boosting**", help=ui.g("Parameter Gradient Boosting"))
                P["GB_POHON"] = st.number_input("Jumlah pohon GB", 50, 1000, int(g("GB_POHON")), 50)
                P["GB_LEARNING_RATE"] = st.number_input("Laju belajar GB", 0.01, 0.5, float(g("GB_LEARNING_RATE")), 0.01)
                P["GB_KEDALAMAN"] = st.number_input("Kedalaman pohon GB", 1, 6, int(g("GB_KEDALAMAN")))
            with b[2]:
                st.markdown("**Uji dan model yoy**")
                P["_bt_manual"] = st.number_input("Jumlah backtest", 4, 16, int(s.get("JUMLAH_UJI_BACKTEST", 12)), help=ui.g("Jumlah backtest"))
                P["KALENDER_DI_MODEL_YOY"] = st.checkbox("Kalender di model yoy", bool(g("KALENDER_DI_MODEL_YOY")), help=ui.g("Kalender di model yoy"))
                P["EFEK_TRIWULAN_YOY"] = st.checkbox("Dummy triwulan di model yoy", bool(g("EFEK_TRIWULAN_YOY")), help=ui.g("Dummy triwulan di model yoy"))

    # ---------------- G. kalender, batas, add-factor
    a, b = st.columns(2)
    with a:
        with box("Efek kalender Islam"):
            st.caption("HBKN dan Nataru selalu di Q4, jadi sudah tertangkap pola musiman Q4 pada mode level.")
            r1 = st.columns([1.3, 1, 1])
            ram = r1[0].toggle("Ramadan", s.get("PAKAI_RAMADAN", True), help=ui.g("Ramadan (puasa)"))
            ram_h = r1[1].number_input("Lama puasa (hari)", 25, 30, int(s.get("RAMADAN_HARI", D["RAMADAN_HARI"])), disabled=not ram)
            r2 = st.columns([1.3, 1, 1])
            leb = r2[0].toggle("Lebaran", s.get("PAKAI_LEBARAN", True), help=ui.g("Lebaran (Idul Fitri)"))
            leb_a = r2[1].number_input("Lebaran H-", 0, 30, int(s.get("LEBARAN_HARI_SEBELUM", D["LEBARAN_HARI_SEBELUM"])), disabled=not leb)
            leb_b = r2[2].number_input("Lebaran H+", 0, 30, int(s.get("LEBARAN_HARI_SESUDAH", D["LEBARAN_HARI_SESUDAH"])), disabled=not leb)
            r3 = st.columns([1.3, 1, 1])
            adh = r3[0].toggle("Idul Adha", s.get("PAKAI_IDULADHA", True), help=ui.g("Idul Adha"))
            adh_a = r3[1].number_input("Idul Adha H-", 0, 30, int(s.get("IDULADHA_HARI_SEBELUM", D["IDULADHA_HARI_SEBELUM"])), disabled=not adh)
            adh_b = r3[2].number_input("Idul Adha H+", 0, 30, int(s.get("IDULADHA_HARI_SESUDAH", D["IDULADHA_HARI_SESUDAH"])), disabled=not adh)
        with box("Batas lompatan yoy", ui.g("Batas lompatan yoy")):
            bt_pre = s.get("BATAS_PERUBAHAN_YOY", "otomatis")
            b_on = st.toggle("Aktifkan batas lompatan", bt_pre is not None)
            x = st.columns(2)
            bmode = x[0].radio("Cara menentukan batas", ["Otomatis", "Manual"], index=1 if isinstance(bt_pre, (int, float)) else 0, disabled=not b_on, horizontal=True)
            if bmode == "Otomatis":
                kuantil = x[1].slider("Persentil historis", 70, 99, int(s.get("KUANTIL_BATAS", D["KUANTIL_BATAS"])), disabled=not b_on)
                bval = None
            else:
                bval = x[1].number_input("Batas (poin per triwulan)", 0.1, 5.0, float(bt_pre) if isinstance(bt_pre, (int, float)) else 0.75, 0.05, disabled=not b_on)
                kuantil = D["KUANTIL_BATAS"]
        with box("Uji dan selang"):
            ci = st.select_slider("Selang kepercayaan", [80, 90, 95], value=s.get("SELANG_KEPERCAYAAN", 90), format_func=lambda v: f"{v}%", help=ui.g("Selang kepercayaan"))
            cepat = st.toggle("Mode cepat (6 backtest)", s.get("_cepat", False), help=ui.g("Mode cepat"), disabled=adv)
    with b:
        with box("Add-factor", ui.g("Add-factor")):
            fp = pd.period_range(sampai + 1, proj, freq="Q")
            pre_af = s.get("PENYESUAIAN", {})
            af = pd.DataFrame({"Periode": [str(p) for p in fp], "Add-factor (poin yoy)": [float(pre_af.get(str(p), 0.0)) for p in fp]})
            af_ed = st.data_editor(af, hide_index=True, use_container_width=True, disabled=["Periode"], height=min(36 * (len(af) + 1) + 4, 460),
                                   column_config={"Add-factor (poin yoy)": st.column_config.NumberColumn(format="%+.2f", step=0.05, min_value=-5.0, max_value=5.0)},
                                   key=f"af_{sampai}_{proj}")
            y = df[target].dropna()
            qq = pd.DataFrame({"y": y.values, "yr": y.index.year, "q": y.index.quarter}).pivot(index="yr", columns="q", values="y")
            if {3, 4} <= set(qq.columns):
                qq = qq[~qq.index.isin(range(krisis[0].year, krisis[1].year + 1))].dropna(subset=[3, 4])
                if len(qq):
                    dd = qq[4] - qq[3]
                    st.caption(f"Acuan historis (tahun normal): yoy Q4 dibanding Q3 rata-rata **{dd.mean():+.2f} poin**, Q4 lebih tinggi di {int((dd > 0).sum())} dari {len(dd)} tahun.")

    # ---------------- H. jalankan
    with st.container(border=True):
        n1, n2 = st.columns([1, 1.4])
        nama = n1.text_input("Nama run", value=pre.get("name") or f"{ds['name']} · {target}")
        catatan = n2.text_input("Catatan (opsional)", value=pre.get("note", ""), placeholder="mis. add-factor Q4 +0,10, tanpa indikator wisatawan")
        n_obs = len(df.loc[mulai:sampai])
        bt = int(P.get("_bt_manual", 6 if cepat else 12))
        bt = min(bt, n_obs - 17)
        st.caption(f"Data {mulai} s.d. {sampai} ({n_obs} triwulan) · proyeksi {len(fp)} triwulan · backtest {bt} kali · "
                   f"perkiraan waktu ± {max(1, round(bt / 6))} menit.")
        go = st.button("▶ Jalankan proyeksi", type="primary")

    if not go:
        return
    if bt < 4:
        st.error("Data terlalu pendek untuk diuji. Mundurkan Data mulai atau tambah data.")
        return
    if not any(metode.values()):
        st.error("Pilih minimal satu metode.")
        return
    if pb < pa or (reb and rb < ra):
        st.error("Periode pandemi belum benar: bulan selesai lebih awal dari bulan mulai.")
        return
    settings = {
        "TARGET": target, "TARGET_LEVEL": level, "DATA_MULAI": str(mulai), "DATA_SAMPAI": None if sampai == tl else str(sampai),
        "PROYEKSI_SAMPAI": str(proj), "INDIKATOR_DIPAKAI": chosen, "VAR_INDIKATOR": var_ind or (chosen[:1] if chosen else []),
        "METODE": metode, "PAKAI_ENSEMBLE": ens, "ENSEMBLE_CARA": cara_ens, "ENSEMBLE_TOP": int(topn),
        "PAKAI_DUMMY_PANDEMI": dum, "PERIODE_PANDEMI": (str(pa), str(pb)), "PERIODE_REBOUND": (str(ra), str(rb)), "PAKAI_REBOUND": bool(reb),
        "PAKAI_EFEK_KALENDER": bool(ram or leb or adh), "PAKAI_RAMADAN": ram, "RAMADAN_HARI": int(ram_h), "PAKAI_LEBARAN": leb,
        "LEBARAN_HARI_SEBELUM": int(leb_a), "LEBARAN_HARI_SESUDAH": int(leb_b), "PAKAI_IDULADHA": adh,
        "IDULADHA_HARI_SEBELUM": int(adh_a), "IDULADHA_HARI_SESUDAH": int(adh_b),
        "BERSIHKAN_OUTLIER": False, "OUTLIER_MANUAL": manual, "OUTLIER_CARA": cara, "BATAS_OUTLIER": float(k),
        "JUMLAH_UJI_BACKTEST": int(bt), "SELANG_KEPERCAYAAN": int(ci),
        "BATAS_PERUBAHAN_YOY": None if not b_on else ("otomatis" if bmode == "Otomatis" else float(bval)), "KUANTIL_BATAS": int(kuantil),
        "PENYESUAIAN": {r["Periode"]: float(r["Add-factor (poin yoy)"] or 0) for _, r in af_ed.iterrows()},
    }
    settings.update({kk: vv for kk, vv in P.items() if not kk.startswith("_")})
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
    settings["_advanced"] = adv
    settings["PERIODE_PANDEMI"], settings["PERIODE_REBOUND"] = list(settings["PERIODE_PANDEMI"]), list(settings["PERIODE_REBOUND"])
    be.insert("runs", {"id": rid, "user_id": uid(), "dataset_id": ds["id"], "name": nama.strip() or "Run tanpa nama", "note": catatan.strip(),
                       "settings": settings, "summary": out["summary"], "status": "selesai", "excel_path": xp, "charts_path": cp,
                       "created_at": now_iso()})
    bar.progress(1.0, text="Selesai")
    st.session_state.pop("prefill", None)
    st.session_state["run_terpilih"] = rid
    st.session_state["dataset_aktif"] = ds
    nav.go("riwayat")
