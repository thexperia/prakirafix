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
METODE_BUTUH_INDIKATOR = ["ARIMAX", "VAR", "BVAR", "Ridge", "Elastic Net", "Faktor (PCA)", "Random Forest", "Gradient Boosting"]
METODE_LEVEL = ["SARIMA Musiman", "ETS Musiman"]


class ProgressWriter(io.StringIO):
    """Menangkap print dari skrip; memanggil callback tiap satu titik backtest selesai."""

    def __init__(self, cb=None, total=12):
        super().__init__()
        self.cb, self.total, self.done = cb, total, 0

    def write(self, s):
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
    ns.update(settings)
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


def build_summary(ns):
    best = ns["BEST"]
    final = ns["final"]
    fc = ns["fc_periods"]
    order = ns["ORDER"]
    proj = [{"periode": str(p), "yoy": _f(final[best].loc[p, "Proyeksi"]),
             "lower": _f(final[best].loc[p, "Lower"]), "upper": _f(final[best].loc[p, "Upper"])} for p in fc]
    y = ns["y_all"]
    hist = [{"periode": str(p), "yoy": _f(v)} for p, v in y.iloc[-16:].items()]
    met = ns["metrik"]
    top = []
    for _, r in met.head(15).iterrows():
        top.append({"metode": r["Metode"], "rmse": _f(r["RMSE"]), "mae": _f(r["MAE"]),
                    "bias": _f(r["ME (bias)"]), "mase": _f(r["MASE"]), "arah": _f(r["Akurasi arah (%)"])})
    tah = ns["tahunan"]
    tahunan = {str(c): _f(tah.loc[best, c]) for c in tah.columns}
    brow = met[met.Metode == best].iloc[0]
    return {
        "metode_terbaik": best, "rmse_terbaik": _f(brow["RMSE"]), "arah_terbaik": _f(brow["Akurasi arah (%)"]),
        "proyeksi": proj, "historis": hist, "tahunan": tahunan, "metrik": top,
        "mode": "level" if ns["MODE_LEVEL"] else "yoy", "target": ns["TARGET"],
        "label_target": str(ns["LABEL"].get(ns["TARGET"], ns["TARGET"])),
        "data_awal": str(ns["df_raw"].index[0]), "data_akhir": str(ns["df_raw"].index[-1]),
        "proyeksi_sampai": str(fc[-1]), "indikator": list(ns["EXOG_ALL"]),
        "metode_aktif": list(ns["aktif"]), "dilewati": list(ns["dilewati"]),
        "jumlah_titik_uji": int(brow["Jumlah titik uji"]), "urutan": order,
        "bobot_ensemble": {k: _f(v) for k, v in ns["W"].items()} if len(ns["W"]) else {},
    }
