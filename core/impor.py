"""Impor hasil run dari Google Colab (zip berisi hasil_proyeksi.xlsx + grafik PNG, opsional file data).

Ringkasan run dibangun ulang dari sheet Excel, sehingga tampil sama seperti run yang dijalankan di aplikasi.
"""
import io
import re
import zipfile

import numpy as np
import pandas as pd

from core import engine, validasi


def _f(x):
    try:
        x = float(x)
        return None if np.isnan(x) else round(x, 4)
    except Exception:
        return None


def baca_zip(zip_bytes):
    """Mengembalikan dict(excel, charts_zip, data_bytes, data_name) atau raise ValueError."""
    try:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise ValueError("File bukan zip yang valid.")
    names = [n for n in z.namelist() if not n.endswith("/") and "__MACOSX" not in n]
    hasil = [n for n in names if n.lower().endswith("hasil_proyeksi.xlsx")]
    if not hasil:
        xl = [n for n in names if n.lower().endswith(".xlsx")]
        hasil = [n for n in xl if "Metrik_Error_Backtest" in pd.ExcelFile(io.BytesIO(z.read(n))).sheet_names]
    if not hasil:
        raise ValueError("Tidak ditemukan hasil_proyeksi.xlsx di dalam zip.")
    excel = z.read(hasil[0])
    cbuf = io.BytesIO()
    with zipfile.ZipFile(cbuf, "w", zipfile.ZIP_DEFLATED) as cz:
        for n in names:
            if n.lower().endswith(".png"):
                cz.writestr(n.split("/")[-1], z.read(n))
    data = [n for n in names if n.lower().endswith(".xlsx") and n != hasil[0]]
    return {"excel": excel, "charts_zip": cbuf.getvalue(), "data_bytes": z.read(data[0]) if data else None,
            "data_name": data[0].split("/")[-1] if data else None}


def ringkasan_dari_excel(excel):
    x = pd.ExcelFile(io.BytesIO(excel))
    need = ["Pengaturan", "Metrik_Error_Backtest", "Proyeksi_dengan_CI", "Series_Aktual_Proyeksi"]
    miss = [s for s in need if s not in x.sheet_names]
    if miss:
        raise ValueError(f"Sheet {', '.join(miss)} tidak ada. Pastikan file berasal dari notebook proyeksi versi terbaru.")
    peng = pd.read_excel(x, "Pengaturan").set_index("Pengaturan")["Nilai"].astype(str).to_dict()
    met = pd.read_excel(x, "Metrik_Error_Backtest")
    best = peng.get("Metode terbaik (RMSE)") or met.iloc[0]["Metode"]
    ci = pd.read_excel(x, "Proyeksi_dengan_CI")
    ci = ci[ci["Metode"] == best]
    ser = pd.read_excel(x, "Series_Aktual_Proyeksi")
    ser = ser.rename(columns={ser.columns[0]: "Periode"})
    hist = ser[ser["Aktual"].notna() & ser[best].isna()] if best in ser else ser[ser["Aktual"].notna()]
    tah = pd.read_excel(x, "Pertumbuhan_Tahunan").set_index("Metode") if "Pertumbuhan_Tahunan" in x.sheet_names else pd.DataFrame()
    bob = pd.read_excel(x, "Bobot_Ensemble") if "Bobot_Ensemble" in x.sheet_names else pd.DataFrame()
    brow = met[met["Metode"] == best].iloc[0]
    tgt_txt = peng.get("TARGET", "")
    m = re.match(r"^(\S+)\s*\((.*)\)$", tgt_txt)
    target, label = (m.group(1), m.group(2)) if m else (tgt_txt, tgt_txt)
    mode = peng.get("Mode", "")
    lvl = re.search(r"\((.+)\)", mode)
    ind = [s.strip() for s in peng.get("INDIKATOR_DIPAKAI", "").split(",") if s.strip() and s.strip() != "-"]
    aktif = [s.strip() for s in peng.get("METODE aktif", "").split(",") if s.strip()]
    summary = {
        "metode_terbaik": best, "rmse_terbaik": _f(brow["RMSE"]), "arah_terbaik": _f(brow.get("Akurasi arah (%)")),
        "proyeksi": [{"periode": str(r["Periode"]), "yoy": _f(r["Proyeksi"]), "lower": _f(r["Lower"]), "upper": _f(r["Upper"])} for _, r in ci.iterrows()],
        "historis": [{"periode": str(r["Periode"]), "yoy": _f(r["Aktual"])} for _, r in hist.tail(16).iterrows()],
        "tahunan": {str(c): _f(tah.loc[best, c]) for c in tah.columns} if best in tah.index else {},
        "metrik": [{"metode": r["Metode"], "rmse": _f(r["RMSE"]), "mae": _f(r["MAE"]), "bias": _f(r["ME (bias)"]),
                    "mase": _f(r.get("MASE")), "arah": _f(r.get("Akurasi arah (%)"))} for _, r in met.iterrows()],
        "mode": "level" if mode.lower().startswith("level") else "yoy", "target": target, "label_target": label,
        "data_awal": peng.get("DATA_MULAI"), "data_akhir": peng.get("DATA_SAMPAI"), "proyeksi_sampai": peng.get("PROYEKSI_SAMPAI"),
        "indikator": ind, "metode_aktif": aktif, "dilewati": [], "jumlah_titik_uji": int(brow.get("Jumlah titik uji", 0) or 0),
        "urutan": list(met["Metode"]), "bobot_ensemble": {r["Metode"]: _f(r["Bobot"]) for _, r in bob.iterrows()} if len(bob) else {},
        "durasi_detik": None, "sumber": "impor Google Colab",
    }
    # pengaturan untuk tombol "Jalankan ulang"
    af = {}
    for part in peng.get("PENYESUAIAN (pp yoy)", "").split(","):
        if ":" in part:
            k, v = part.split(":")
            try:
                af[k.strip()] = float(v)
            except ValueError:
                pass
    var = [s.strip() for s in peng.get("VAR/BVAR (variabel)", "").split(",") if s.strip() and s.strip() != target]
    batas = peng.get("Batas perubahan yoy antarkuartal", "otomatis")
    settings = {
        "TARGET": target, "TARGET_LEVEL": lvl.group(1) if lvl else None, "DATA_MULAI": peng.get("DATA_MULAI"),
        "PROYEKSI_SAMPAI": peng.get("PROYEKSI_SAMPAI"), "INDIKATOR_DIPAKAI": ind, "VAR_INDIKATOR": var,
        "METODE": {mm: (mm in aktif) for mm in engine.METODE_LIST}, "PAKAI_ENSEMBLE": peng.get("PAKAI_ENSEMBLE") == "True",
        "ENSEMBLE_CARA": peng.get("ENSEMBLE_CARA", "inverse-rmse"), "PAKAI_DUMMY_PANDEMI": peng.get("PAKAI_DUMMY_PANDEMI") == "True",
        "PAKAI_EFEK_KALENDER": peng.get("PAKAI_EFEK_KALENDER") == "True", "BERSIHKAN_OUTLIER": peng.get("BERSIHKAN_OUTLIER") == "True",
        "SELANG_KEPERCAYAAN": int(re.sub(r"\D", "", peng.get("SELANG_KEPERCAYAAN", "90")) or 90),
        "BATAS_PERUBAHAN_YOY": "otomatis" if "otomatis" in batas else (None if "tidak" in batas else batas),
        "PENYESUAIAN": af, "_cepat": peng.get("JUMLAH_UJI_BACKTEST") not in ("12", None),
    }
    if settings["METODE"].get("SARIMA Musiman") is False and "ETS Musiman" not in aktif:
        pass
    return summary, settings


def cek_data(data_bytes):
    if not data_bytes:
        return None
    res = validasi.periksa(data_bytes)
    return res if res["ok"] else None
