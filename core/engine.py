"""Menjalankan proyeksi_pdrb.py (logika sama persis dengan notebook Colab) dengan pengaturan dari aplikasi.

Bagian PENGATURAN di proyeksi_pdrb.py dipakai sebagai nilai bawaan, lalu ditimpa pilihan pengguna.
Hasilnya berupa file Excel + grafik PNG di folder sementara, plus ringkasan untuk disimpan di database.
"""
import io
import os
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

_SRC = (Path(__file__).parent / "proyeksi_pdrb.py").read_text(encoding="utf-8")
_A = _SRC.index("# ---- 1. File data")
_B = _SRC.index("# #############################################################################\n# ##   AKHIR PENGATURAN")
PENGATURAN_SRC = _SRC[_A:_B]
BODY_SRC = _SRC[_B:]
BODY_SRC = BODY_SRC.replace(
    'def stop(msg):\n    print(f"\\n[PENGATURAN BELUM TEPAT] {msg}\\n")\n    sys.exit(1)',
    'class PengaturanBelumTepat(Exception):\n    pass\n\n\ndef stop(msg):\n    raise PengaturanBelumTepat(msg)')
assert "PengaturanBelumTepat" in BODY_SRC, "pola stop() di proyeksi_pdrb.py berubah"
_BODY_CODE = compile(BODY_SRC, "proyeksi_pdrb.py", "exec")


def default_settings():
    ns = {}
    exec(PENGATURAN_SRC, ns)
    return {k: v for k, v in ns.items() if k.isupper()}


DEFAULTS = default_settings()
METODE_LIST = list(DEFAULTS["METODE"].keys())
# v5: Ridge, Random Forest, dan Gradient Boosting tetap bisa jalan memakai lag target saja
METODE_BUTUH_INDIKATOR = ["ARIMAX", "VAR", "BVAR", "Elastic Net", "Faktor (PCA)"]

# Nama pengaturan lama (run sebelum v5) -> nama baru, supaya "Jalankan ulang" dari riwayat lama tetap jalan
_NAMA_LAMA = {"PAKAI_LEBARAN": "PAKAI_IDUL_FITRI", "PAKAI_IDULADHA": "PAKAI_IDUL_ADHA",
              "IDULADHA_HARI_SEBELUM": "IDUL_ADHA_HARI_SEBELUM", "IDULADHA_HARI_SESUDAH": "IDUL_ADHA_HARI_SESUDAH"}


def sesuaikan_pengaturan(settings):
    """Ubah pengaturan versi lama ke v5. Periode pandemi & rebound lama menjadi PERIODE_KRISIS manual."""
    s = {_NAMA_LAMA.get(k, k): v for k, v in (settings or {}).items()}
    if "PERIODE_PANDEMI" in s and "DETEKSI_KRISIS" not in s:
        rg = [tuple(s["PERIODE_PANDEMI"])]
        if s.get("PAKAI_REBOUND", True) and s.get("PERIODE_REBOUND"):
            rg.append(tuple(s["PERIODE_REBOUND"]))
        s["DETEKSI_KRISIS"], s["PERIODE_KRISIS"] = "manual", rg
    for k in ("PERIODE_PANDEMI", "PERIODE_REBOUND", "PAKAI_REBOUND"):
        s.pop(k, None)
    if "PERIODE_KRISIS" in s:
        s["PERIODE_KRISIS"] = [tuple(x) for x in s["PERIODE_KRISIS"]]
    if "JENDELA_KRISIS" in s:
        s["JENDELA_KRISIS"] = tuple(s["JENDELA_KRISIS"])
    return {k: v for k, v in s.items() if k in DEFAULTS}
METODE_LEVEL = ["SARIMA Musiman", "ETS Musiman"]


class ProgressWriter(io.StringIO):
    """Menangkap print dari skrip; memanggil callback tiap satu titik backtest selesai."""

    def __init__(self, cb=None, total=12):
        super().__init__()
        self.cb, self.done = cb, 0
        self.total = total if isinstance(total, int) and total > 0 else 12

    def write(self, s):
        m = re.search(r"Backtest (\d+) titik asal", s)
        if m:                                   # jumlah backtest sebenarnya (bisa "otomatis" di pengaturan)
            self.total = max(1, int(m.group(1)))
        if self.cb and "selesai: data s.d." in s:
            self.done += 1
            self.cb(min(self.done / self.total, 1.0), f"Backtest {self.done}/{self.total} selesai")
        return super().write(s)


def run_projection(excel_bytes, sheet_name, settings, progress=None):
    """settings: dict nama pengaturan -> nilai (menimpa bawaan). Mengembalikan dict hasil."""
    t0 = time.time()
    work = Path(tempfile.mkdtemp(prefix="run_"))
    data_path = work / "data.xlsx"
    data_path.write_bytes(excel_bytes)
    out = work / "output"
    ns = dict(DEFAULTS)
    ns.update(sesuaikan_pengaturan(settings))
    ns.update({"FILE_DATA": str(data_path), "SHEET_DATA": sheet_name, "FOLDER_OUTPUT": str(out),
               "NAMA_FILE_EXCEL": "hasil_proyeksi.xlsx", "__name__": "proyeksi_run"})
    log = ProgressWriter(progress, ns.get("JUMLAH_UJI_BACKTEST", 12))
    old = sys.stdout
    sys.stdout = log
    try:
        exec(_BODY_CODE, ns)
    except Exception as e:  # noqa
        sys.stdout = old
        name = type(e).__name__
        msg = str(e)
        if name == "PengaturanBelumTepat":
            raise ValueError(msg) from None
        raise RuntimeError(f"{name}: {msg}") from None
    finally:
        sys.stdout = old
        import matplotlib.pyplot as plt
        plt.close("all")

    excel = (out / "hasil_proyeksi.xlsx").read_bytes()
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.glob("*.png")):
            z.write(p, p.name)
    summary = build_summary(ns)
    summary["durasi_detik"] = round(time.time() - t0, 1)
    summary["log"] = log.getvalue()[-6000:]
    return {"excel": excel, "charts_zip": zbuf.getvalue(), "summary": summary}


def _f(x):
    try:
        x = float(x)
        return None if np.isnan(x) else round(x, 4)
    except Exception:
        return None


BENCH = ("Naive", "Rata-rata 8Q")


def pilih_utama(metode_urut):
    """Metode utama untuk ditampilkan: Ensemble bila ada, selain itu metode non-benchmark terbaik."""
    if "Ensemble" in metode_urut:
        return "Ensemble"
    return next((m for m in metode_urut if m not in BENCH), metode_urut[0])


def build_summary(ns):
    order = ns["ORDER"]
    best = ns["BEST"]
    utama = pilih_utama(order)
    final = ns["final"]
    fc = ns["fc_periods"]
    proj = [{"periode": str(p), "yoy": _f(final[utama].loc[p, "Proyeksi"]),
             "lower": _f(final[utama].loc[p, "Lower"]), "upper": _f(final[utama].loc[p, "Upper"])} for p in fc]
    y = ns["y_all"]
    hist = [{"periode": str(p), "yoy": _f(v)} for p, v in y.iloc[-16:].items()]
    met = ns["metrik"]
    top = [{"metode": r["Metode"], "rmse": _f(r["RMSE"]), "mae": _f(r["MAE"]), "bias": _f(r["ME (bias)"]),
            "mase": _f(r["MASE"]), "arah": _f(r["Akurasi arah (%)"])} for _, r in met.iterrows()]
    tah = ns["tahunan"]
    tahunan = {str(c): _f(tah.loc[utama, c]) for c in tah.columns}
    urow = met[met.Metode == utama].iloc[0]
    spes = {k: str(v) for k, v in ns.get("spesifikasi", {}).items() if v}
    return {
        "metode_terbaik": best, "metode_utama": utama, "peringkat_utama": int(urow["Peringkat"]),
        "rmse_terbaik": _f(urow["RMSE"]), "arah_terbaik": _f(urow["Akurasi arah (%)"]),
        "proyeksi": proj, "historis": hist, "tahunan": tahunan, "metrik": top, "spesifikasi": spes,
        "mode": "level" if ns["MODE_LEVEL"] else "yoy", "target": ns["TARGET"],
        "label_target": str(ns["LABEL"].get(ns["TARGET"], ns["TARGET"])),
        "data_awal": str(ns["df_raw"].index[0]), "data_akhir": str(ns["df_raw"].index[-1]),
        "proyeksi_sampai": str(fc[-1]), "indikator": list(ns["EXOG_ALL"]),
        "metode_aktif": list(ns["aktif"]), "dilewati": list(ns.get("alasan_lewat", {}) or ns["dilewati"]),
        "jumlah_titik_uji": int(urow["Jumlah titik uji"]), "urutan": order,
        "bobot_ensemble": {k: _f(v) for k, v in ns["W"].items()} if len(ns["W"]) else {},
        "alasan_dilewati": {k: str(v) for k, v in ns.get("alasan_lewat", {}).items()},
        "krisis": [str(p) for p in ns.get("KRISIS", [])],
        "krisis_ringkas": ns["ringkas_periode"](ns.get("KRISIS", [])) if ns.get("KRISIS") else "tidak ada",
        "info_krisis": str(ns.get("INFO_KRISIS", "")),
        "sumber_yoy": str(ns.get("SUMBER_YOY", "")),
        "catatan_otomatis": [str(x) for x in ns.get("CATATAN_AUTO", [])],
        "peringatan": [str(x) for x in ns.get("PERINGATAN_DATA", [])],
        "ensemble_disaring": [str(x) for x in ns.get("DISARING", [])],
        "var_variabel": list(ns.get("VAR_VARS", [])),
        "jumlah_backtest": int(ns.get("JUMLAH_UJI_BACKTEST", 0)),
    }
