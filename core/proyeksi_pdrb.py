"""
PROYEKSI PDRB DENGAN BANYAK METODE (mode yoy dan mode level) - v5
=================================================================
Cara pakai  :
  1. pip install -r requirements.txt
  2. Ubah bagian "PENGATURAN" di bawah ini sesuai kebutuhan (tidak perlu menyentuh bagian lain)
  3. python proyeksi_pdrb.py
  4. Hasil ada di folder output/ (Excel + grafik PNG)

Format file Excel yang dibaca:
  Baris 1 : nama indikator      (mulai kolom C)
  Baris 2 : kode indikator      (mulai kolom C), misalnya GPDRB, GPDB
  Kolom A : tahun (cukup diisi di baris Q1, sisanya boleh kosong)
  Kolom B : triwulan (Q1, Q2, Q3, Q4)

Dua mode (dipilih otomatis):
  - Mode yoy   : bila file hanya berisi pertumbuhan yoy target.
  - Mode level : bila file juga berisi level PDRB ADHK (kolom TARGET_LEVEL). Yoy target dihitung
                 dari level, pola musiman (Q4 > Q3, efek Lebaran) ikut dimodelkan, dan hasil keluar
                 dalam level, qtq, dan yoy.

Pengaturan bertanda "otomatis" menyesuaikan diri dengan panjang data (jumlah backtest, data mulai,
lag VAR/BVAR, order ARIMA, jumlah indikator, dummy pandemi, dll), sehingga file data dengan rentang
berbeda bisa langsung dipakai tanpa mengubah pengaturan.
"""

# #############################################################################
# ##                                                                         ##
# ##   PENGATURAN  (cukup ubah bagian ini)                                    ##
# ##                                                                         ##
# #############################################################################

# ---- 1. File data -----------------------------------------------------------
FILE_DATA    = "Indikator_Makroekonomi_DIY.xlsx"
SHEET_DATA   = "Indikator DIY (growth)"
TARGET       = "GPDRB"          # kode kolom pertumbuhan yoy yang mau diproyeksi
TARGET_LEVEL = "PDRB_ADHK"      # kode kolom level PDRB ADHK. Bila kolom ini ada di file: MODE LEVEL, yoy target
                                # dihitung dari level (kolom TARGET boleh tidak ada; bila ada, dipakai sebagai pembanding).
                                # Bila kolom ini tidak ada di file (atau diisi None): otomatis MODE YOY.

# ---- 2. Periode (format "TAHUNQx", contoh "2027Q4") ----------------------------
DATA_MULAI      = "otomatis"    # "otomatis" = mulai dari data target pertama yang tersedia.
                                # Isi misalnya "2018Q1" untuk mengabaikan data lama
DATA_SAMPAI     = None          # None = pakai data terakhir yang tersedia.
                                # Isi misalnya "2025Q2" untuk uji coba: proyeksi dibuat seolah-olah
                                # data berhenti di 2025Q2, lalu dibandingkan dengan data aktual sesudahnya
PROYEKSI_SAMPAI = "2027Q4"      # proyeksi dibuat sampai periode ini

# ---- 3. Indikator pendukung ------------------------------------------------------
INDIKATOR_DIPAKAI = "semua"     # "semua" atau daftar kode, contoh: ["GPDB", "KODE_LAIN"]
                                # Indikator yang datanya kosong lebih dari 25% pada periode dipakai otomatis dikeluarkan.

# ---- 4. Metode (True = dipakai, False = tidak) -------------------------------------
METODE = {
    "Naive":             True,   # benchmark: pertumbuhan yoy terakhir diulang
    "Rata-rata 8Q":      True,   # benchmark: rata-rata yoy 8 triwulan terakhir
    "ARIMA":             True,   # statistik univariat pada yoy, order dipilih otomatis
    "ETS":               True,   # exponential smoothing (Holt) pada yoy
    "Theta":             True,   # statistik univariat: garis tren + smoothing, benchmark kuat di kompetisi forecasting
    "ARIMAX":            True,   # ARIMA + indikator pendukung
    "VAR":               True,   # vector autoregression
    "BVAR":              True,   # VAR Bayesian (prior Minnesota): lebih stabil untuk data pendek
    "Ridge":             True,   # regresi linier dengan regularisasi
    "Elastic Net":       True,   # regresi dengan seleksi indikator otomatis (indikator lemah dibuat nol)
    "Faktor (PCA)":      True,   # indikator diringkas jadi beberapa faktor, lalu diregresikan
    "Random Forest":     True,   # machine learning
    "Gradient Boosting": True,   # machine learning
    "SARIMA Musiman":    True,   # MODE LEVEL: SARIMA pada log PDRB ADHK, pola musiman + kalender Lebaran
    "ETS Musiman":       False,  # MODE LEVEL: Holt-Winters pada log PDRB ADHK. Default mati: bila pola musiman
                                 # berubah setelah pandemi, hasil backtest-nya cenderung paling buruk
}
PAKAI_ENSEMBLE = True           # gabungan metode non-benchmark
ENSEMBLE_CARA  = "inverse-rmse" # "inverse-rmse" = semua metode, bobot sesuai akurasi (default)
                                # "top"          = hanya ENSEMBLE_TOP metode terbaik, bobot sesuai akurasi
                                # "median"       = nilai tengah semua metode (tahan terhadap metode yang meleset jauh)
ENSEMBLE_TOP   = 3
ENSEMBLE_SARING     = True      # True = metode yang RMSE backtest-nya lebih dari ENSEMBLE_BATAS_RMSE x RMSE
ENSEMBLE_BATAS_RMSE = 1.5       # tebakan naive (random walk) tidak diikutkan Ensemble (dicatat di Penjelasan_Metode)

# ---- 5. Pengaturan metode (boleh dibiarkan default) ---------------------------------
# Catatan: order ARIMA, lag VAR/BVAR, jumlah indikator ARIMAX, dan jumlah faktor PCA otomatis
# diperkecil bila data latih pendek, supaya model tidak terlalu banyak parameter.
ETS_TREN               = "damped"   # "damped" (tren melemah), "linear" (tren lurus), "tanpa" (datar)
ARIMAX_JUMLAH_INDIKATOR = 3         # ARIMAX memakai maksimal N indikator dengan korelasi tertinggi
ARIMAX_KORELASI_MIN    = 0.20       # indikator dengan |korelasi| di bawah ini tidak dipakai ARIMAX
ARIMAX_PILIH_TANPA_PANDEMI = True   # True = korelasi dihitung tanpa periode pandemi & rebound, supaya indikator
                                    # tidak terpilih hanya karena sama-sama anjlok di 2020 (korelasi semu)
ARIMAX_PROYEKSI_INDIKATOR = "ar1"   # cara indikator diproyeksi ke depan sebelum masuk ARIMAX:
                                    # "ar1"   = AR(1) + dummy pandemi (kembali ke rata-rata normal, bukan rata-rata
                                    #           yang tertarik ke bawah oleh 2020)
                                    # "rata2" = ditahan di rata-rata 4 triwulan terakhir
VAR_INDIKATOR          = "otomatis" # indikator VAR & BVAR (target selalu ikut):
                                    # "otomatis" = dipilih dari korelasi tanpa periode pandemi & rebound
                                    # atau tentukan sendiri, contoh: ["GPDB"] atau ["GPDB", "KODE_LAIN"]
VAR_JUMLAH_OTOMATIS    = 1          # "otomatis": maksimal N indikator (VAR cepat boros parameter; 1 paling aman
                                    # untuk data sekitar 40 triwulan, 2 bila data panjang)
VAR_KORELASI_MIN       = 0.20       # "otomatis": indikator dengan |korelasi| di bawah ini tidak dipilih
BVAR_LAG               = "otomatis" # jumlah lag BVAR: "otomatis" (2, atau 1 bila data pendek) atau angka
BVAR_KETATAN           = 0.2        # makin kecil makin "hemat" (koefisien ditarik ke prior), umumnya 0.1 s.d. 0.5
FAKTOR_JUMLAH          = 2          # jumlah faktor maksimum untuk metode Faktor (PCA)
RATA2_JUMLAH_TRIWULAN  = 8

# ---- 5b. Jarak yoy antarkuartal -------------------------------------------------------
# Pada data historis normal (di luar pandemi), yoy jarang melompat jauh dari triwulan ke triwulan.
# Proyeksi yang melompat melebihi batas dipangkas ke batas itu (berlaku di backtest juga, jadi metrik tetap jujur).
BATAS_PERUBAHAN_YOY = "otomatis"    # "otomatis" = persentil historis perubahan yoy antarkuartal (periode normal)
                                    # angka, misal 0.75 = batas manual dalam poin persen
                                    # None = tanpa batas
KUANTIL_BATAS       = 90            # persentil untuk "otomatis" (90 = hanya 10% perubahan historis yang lebih besar)

# ---- 6. Penanda krisis (pandemi) ---------------------------------------------------------
# Setiap triwulan krisis diberi dummy sendiri (impuls). Model belajar dari periode normal saja, dan anjlok 2020
# tidak tercampur dengan lonjakan basis rendah 2021 (keduanya berlawanan arah).
PAKAI_DUMMY_PANDEMI = True        # otomatis tidak dipakai bila periode data tidak mencakup masa krisis
DETEKSI_KRISIS      = "otomatis"  # "otomatis" = triwulan di JENDELA_KRISIS yang yoy-nya menyimpang jauh dari periode
                                  #              normal ditandai sendiri (anjlok maupun lonjakan)
                                  # "manual"   = pakai daftar PERIODE_KRISIS
JENDELA_KRISIS      = ("2020Q1", "2022Q4")   # "otomatis": rentang pencarian
AMBANG_KRISIS       = 2.0         # "otomatis": menyimpang lebih dari N x simpangan baku periode normal
PERIODE_KRISIS      = [("2020Q1", "2020Q4"), ("2021Q2", "2022Q1")]   # "manual": daftar rentang triwulan krisis
                                  # boleh juga per bulan, mis. ("2020-03", "2020-12"): bulan diubah ke triwulannya

# ---- 7. Efek musiman: kalender Islam (Ramadan, Lebaran, Idul Adha) & HBKN/Nataru ----------
# Ramadan, Lebaran, dan Idul Adha tanggalnya bergeser tiap tahun, sehingga perlu variabel kalender sendiri.
# Nataru & HBKN Natal tanggalnya tetap dan selalu di Q4:
#   - model level (SARIMA/ETS Musiman): efeknya sudah tertangkap komponen musiman Q4;
#   - model yoy: efeknya saling meniadakan (Q4 tahun ini dibanding Q4 tahun lalu).
# Bila ada informasi Nataru tahun tertentu lebih ramai/sepi dari biasanya, gunakan PENYESUAIAN (add-factor) Q4.
PAKAI_EFEK_KALENDER   = True    # hitung porsi hari Ramadan/Lebaran/Idul Adha per triwulan. Dipakai di model level
                                # (SARIMA Musiman). False = semua efek kalender di bawah dimatikan.
PAKAI_RAMADAN         = True    # True/False: efek bulan puasa
PAKAI_IDUL_FITRI      = True    # True/False: efek Lebaran (Idul Fitri), jendela LEBARAN_HARI_SEBELUM/SESUDAH
PAKAI_IDUL_ADHA       = False   # True/False: efek Idul Adha, jendela IDUL_ADHA_HARI_SEBELUM/SESUDAH.
                                # Default mati: pada uji coba memperbesar bias SARIMA Musiman
                                # Contoh hanya Idul Fitri: PAKAI_RAMADAN = False, PAKAI_IDUL_FITRI = True, PAKAI_IDUL_ADHA = False
KALENDER_DI_MODEL_YOY = False   # True = variabel kalender (bentuk selisih yoy) juga masuk ARIMA/ARIMAX/VAR/ML.
                                # Default mati: pada uji coba backtest-nya memburuk. Coba nyalakan & bandingkan.
EFEK_TRIWULAN_YOY     = False   # True = dummy Q1/Q2/Q3 (pembanding Q4) masuk model yoy, untuk menangkap
                                # kecenderungan yoy triwulan tertentu (misal Q4 akibat HBKN/Nataru) lebih tinggi.
RAMADAN_HARI         = 30       # lama puasa (hari) sebelum Idul Fitri
LEBARAN_HARI_SEBELUM = 10       # puncak Lebaran: H-10 (mudik, belanja) ...
LEBARAN_HARI_SESUDAH = 7        # ... s.d. H+7 (libur, arus balik, wisata)
IDUL_ADHA_HARI_SEBELUM = 0      # jendela Idul Adha: H-0 ...
IDUL_ADHA_HARI_SESUDAH = 0      # ... s.d. H+0 (hari raya saja). Contoh H-1 s.d. H+3 untuk libur panjang
# Tanggal 1 Syawal & 10 Zulhijah versi pemerintah. 2026 ke atas: sesuaikan dengan SKB 3 Menteri bila berbeda.
TANGGAL_IDUL_FITRI = {
    2010: "2010-09-10", 2011: "2011-08-31", 2012: "2012-08-19", 2013: "2013-08-08", 2014: "2014-07-28",
    2015: "2015-07-17", 2016: "2016-07-06", 2017: "2017-06-25", 2018: "2018-06-15", 2019: "2019-06-05",
    2020: "2020-05-24", 2021: "2021-05-13", 2022: "2022-05-02", 2023: "2023-04-22", 2024: "2024-04-10",
    2025: "2025-03-31", 2026: "2026-03-20", 2027: "2027-03-10", 2028: "2028-02-27", 2029: "2029-02-15",
}
TANGGAL_IDUL_ADHA = {
    2010: "2010-11-17", 2011: "2011-11-06", 2012: "2012-10-26", 2013: "2013-10-15", 2014: "2014-10-05",
    2015: "2015-09-24", 2016: "2016-09-12", 2017: "2017-09-01", 2018: "2018-08-22", 2019: "2019-08-11",
    2020: "2020-07-31", 2021: "2021-07-20", 2022: "2022-07-10", 2023: "2023-06-29", 2024: "2024-06-17",
    2025: "2025-06-06", 2026: "2026-05-27", 2027: "2027-05-17", 2028: "2028-05-05", 2029: "2029-04-24",
}

# ---- 8. Evaluasi ------------------------------------------------------------------------
JUMLAH_UJI_BACKTEST = "otomatis"  # berapa kali model diuji mundur. "otomatis" = menyesuaikan panjang data
                                  # (maksimal 12). Data pendek tetap dijalankan, dengan peringatan. Atau isi angka
SELANG_KEPERCAYAAN  = 90        # dalam persen: 80, 90, atau 95
POLA_MUSIMAN_MULAI  = "otomatis"  # MODE LEVEL: awal rentang qtq historis pembanding untuk cek pola musiman.
                                  # "otomatis" = setelah masa pandemi & rebound (bila tersisa minimal 2 tahun),
                                  # selain itu 3 tahun terakhir. Atau isi misalnya "2022Q1"

# ---- 9. Penyesuaian judgment / add-factor (poin persen yoy) --------------------------------
# Ditambahkan ke proyeksi yoy SEMUA metode pada periode yang disebut. Level & qtq ikut dihitung ulang.
# Hasil model murni tetap disimpan di Excel sebagai pembanding.
PENYESUAIAN = {
    "2026Q4": +0.00,
    "2027Q4": +0.00,
}

# ---- 10. Pembersihan data ----------------------------------------------------------------
BERSIHKAN_OUTLIER = True        # pangkas nilai ekstrem pada indikator pendukung (target tidak diubah)
BATAS_OUTLIER     = 4.0         # makin kecil makin ketat (umumnya 3 s.d. 5)
OUTLIER_MANUAL    = None        # dict {kode indikator: ["2021Q2", ...]} = hanya periode ini yang ditangani
                                # (menggantikan BERSIHKAN_OUTLIER). Batas wajar dihitung dari periode normal.
OUTLIER_CARA      = "pangkas"   # "pangkas" = dipotong ke batas wajar | "hapus" = dikosongkan lalu diisi interpolasi

# ---- 10b. Parameter per metode (advanced) ----------------------------------------------------
ARIMA_MAX_PQ      = "otomatis"  # order AR & MA maksimum ARIMA: "otomatis" (2, atau 1 bila data < 24 triwulan) atau angka
ARIMAX_MAX_PQ     = 1           # order maksimum ARIMAX
VAR_MAXLAG        = "otomatis"  # lag maksimum VAR: "otomatis" (maks 2, lebih kecil bila data pendek) atau angka
RF_POHON          = 400         # Random Forest: jumlah pohon
RF_KEDALAMAN      = 4           # Random Forest: kedalaman maksimum pohon
RF_MIN_DAUN       = 2           # Random Forest: minimal observasi per daun
GB_POHON          = 250         # Gradient Boosting: jumlah pohon
GB_LEARNING_RATE  = 0.05        # Gradient Boosting: laju belajar
GB_KEDALAMAN      = 2           # Gradient Boosting: kedalaman pohon

# ---- 11. Grafik & output ------------------------------------------------------------------
GRAFIK_MULAI           = "otomatis" # awal sumbu waktu grafik proyeksi: "otomatis" = 5 tahun terakhir, atau "2021Q1"
TAMPILKAN_BENCHMARK    = True       # tampilkan Naive & Rata-rata di grafik proyeksi
FOLDER_OUTPUT          = "output"
NAMA_FILE_EXCEL        = "hasil_proyeksi.xlsx"

# #############################################################################
# ##   AKHIR PENGATURAN. Bagian di bawah tidak perlu diubah.                   ##
# #############################################################################


import os
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.api import VAR
from statsmodels.tsa.stattools import adfuller
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.forecasting.theta import ThetaModel
from sklearn.linear_model import RidgeCV, ElasticNetCV, LinearRegression
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
SEED = 42
BENCHMARK = ["Naive", "Rata-rata 8Q"]
METODE_LEVEL = ["SARIMA Musiman", "ETS Musiman"]


def stop(msg):
    print(f"\n[PENGATURAN BELUM TEPAT] {msg}\n")
    sys.exit(1)


def to_period(txt, nama):
    try:
        return pd.Period(str(txt).upper().replace(" ", ""), freq="Q")
    except Exception:
        stop(f'{nama} = "{txt}" tidak dikenali. Gunakan format seperti "2027Q4".')


# =============================================================================
# 1. LOAD DATA
# =============================================================================
def load_data(path, sheet):
    if not os.path.exists(path):
        stop(f'File "{path}" tidak ditemukan. Taruh file Excel di folder yang sama dengan skrip ini.')
    try:
        raw = pd.read_excel(path, sheet_name=sheet, header=None)
    except ValueError:
        sheets = pd.ExcelFile(path).sheet_names
        stop(f'Sheet "{sheet}" tidak ada. Sheet yang tersedia: {sheets}')
    labels = raw.iloc[0, 2:].tolist()
    codes = [str(c).strip() for c in raw.iloc[1, 2:].tolist()]
    body = raw.iloc[2:].copy()
    body[0] = body[0].ffill().astype(int)
    idx = pd.PeriodIndex([f"{y}{str(q).strip()}" for y, q in zip(body[0], body[1])], freq="Q")
    df = pd.DataFrame(body.iloc[:, 2:].values.astype(float), index=idx, columns=codes)
    df = df.dropna(how="all")
    return df, dict(zip(codes, labels))


df_full, LABEL = load_data(FILE_DATA, SHEET_DATA)
CATATAN_AUTO = []   # daftar penyesuaian otomatis, ditampilkan di ringkasan & sheet Pengaturan

# --- mode level: yoy target dihitung dari level -----------------------------------
MODE_LEVEL = bool(TARGET_LEVEL) and TARGET_LEVEL in df_full.columns
SUMBER_YOY = f"kolom {TARGET}"
if MODE_LEVEL:
    _lv = df_full[TARGET_LEVEL]
    _yoy_lv = (_lv / _lv.shift(4) - 1) * 100
    if TARGET in df_full.columns:
        _beda = (_yoy_lv - df_full[TARGET]).abs().dropna()
        # Cadangan: triwulan awal yang level 4 triwulan sebelumnya tidak ada memakai kolom TARGET
        _awal_lv = _yoy_lv.first_valid_index()
        _cad = df_full[TARGET][(df_full.index < _awal_lv) & df_full[TARGET].notna()] if _awal_lv is not None else df_full[TARGET].iloc[:0]
        SUMBER_YOY = f"dihitung dari {TARGET_LEVEL}" + (
            f" (selisih rata-rata dengan kolom {TARGET}: {_beda.mean():.2f} pp)" if len(_beda) else "") + (
            f"; {len(_cad)} triwulan awal ({_cad.index[0]} s.d. {_cad.index[-1]}) memakai kolom {TARGET} "
            f"karena level 4 triwulan sebelumnya tidak ada" if len(_cad) else "")
        _yoy_lv = _yoy_lv.combine_first(_cad)
    else:
        SUMBER_YOY = f"dihitung dari {TARGET_LEVEL} (kolom {TARGET} tidak ada di file)"
        LABEL[TARGET] = f"Pertumbuhan yoy {LABEL.get(TARGET_LEVEL, TARGET_LEVEL)}"
    df_full[TARGET] = _yoy_lv

# --- cek pengaturan ------------------------------------------------------------
if TARGET not in df_full.columns:
    stop(f'TARGET "{TARGET}" tidak ada. Kode yang tersedia: {list(df_full.columns)}. '
         f'Bila file berisi level PDRB, isi TARGET_LEVEL dengan kode kolom level.')
NON_INDIKATOR = [TARGET] + ([TARGET_LEVEL] if TARGET_LEVEL in df_full.columns else [])
if INDIKATOR_DIPAKAI == "semua":
    EXOG_ALL = [c for c in df_full.columns if c not in NON_INDIKATOR]
else:
    salah = [c for c in INDIKATOR_DIPAKAI if c not in df_full.columns]
    if salah:
        stop(f"Indikator {salah} tidak ada. Kode yang tersedia: {list(df_full.columns)}")
    EXOG_ALL = [c for c in INDIKATOR_DIPAKAI if c not in NON_INDIKATOR]

if df_full[TARGET].notna().sum() == 0:
    stop(f"Kolom {TARGET} tidak berisi angka.")
if DATA_MULAI is None or str(DATA_MULAI).lower() == "otomatis":
    p_mulai = df_full[TARGET].first_valid_index()
else:
    p_mulai = max(to_period(DATA_MULAI, "DATA_MULAI"), df_full[TARGET].first_valid_index())
p_last_avail = df_full[TARGET].last_valid_index()
p_sampai = to_period(DATA_SAMPAI, "DATA_SAMPAI") if DATA_SAMPAI else p_last_avail
p_proj = to_period(PROYEKSI_SAMPAI, "PROYEKSI_SAMPAI")
if p_sampai > p_last_avail:
    stop(f"DATA_SAMPAI ({p_sampai}) melewati data terakhir yang tersedia ({p_last_avail}).")
if p_proj <= p_sampai:
    stop(f"PROYEKSI_SAMPAI ({p_proj}) harus setelah data terakhir ({p_sampai}).")

if SELANG_KEPERCAYAAN not in (80, 90, 95):
    stop("SELANG_KEPERCAYAAN sebaiknya 80, 90, atau 95.")
if ETS_TREN not in ("damped", "linear", "tanpa"):
    stop('ETS_TREN harus "damped", "linear", atau "tanpa".')
if ENSEMBLE_CARA not in ("inverse-rmse", "top", "median"):
    stop('ENSEMBLE_CARA harus "inverse-rmse", "top", atau "median".')
if ARIMAX_PROYEKSI_INDIKATOR not in ("ar1", "rata2"):
    stop('ARIMAX_PROYEKSI_INDIKATOR harus "ar1" atau "rata2".')
if not (BATAS_PERUBAHAN_YOY is None or BATAS_PERUBAHAN_YOY == "otomatis"
        or isinstance(BATAS_PERUBAHAN_YOY, (int, float))):
    stop('BATAS_PERUBAHAN_YOY harus "otomatis", angka (misal 0.75), atau None.')
if not (VAR_INDIKATOR == "otomatis" or isinstance(VAR_INDIKATOR, (list, tuple))):
    stop('VAR_INDIKATOR harus "otomatis" atau daftar kode, contoh: ["GPDB"].')

# --- indikator dengan data terlalu banyak kosong dikeluarkan otomatis -----------------
_per = (df_full.index >= p_mulai) & (df_full.index <= p_sampai)
_kosong = {c: df_full.loc[_per, c].isna().mean() for c in EXOG_ALL}
_keluar = [c for c, f in _kosong.items() if f > 0.25]
if _keluar:
    EXOG_ALL = [c for c in EXOG_ALL if c not in _keluar]
    CATATAN_AUTO.append("indikator dikeluarkan karena data kosong > 25%: "
                        + ", ".join(f"{c} ({_kosong[c]:.0%})" for c in _keluar))

df_raw = df_full.loc[_per, [TARGET] + EXOG_ALL]
fc_periods = pd.period_range(p_sampai + 1, p_proj, freq="Q")
H = len(fc_periods)
CI = SELANG_KEPERCAYAAN / 100
Z = stats.norm.ppf(0.5 + CI / 2)

# --- jumlah backtest menyesuaikan panjang data -------------------------------------------
n_obs = len(df_raw)
PERINGATAN_DATA = []
if n_obs < 3:
    stop(f"Data target hanya {n_obs} triwulan ({p_mulai} s.d. {p_sampai}); tidak ada yang bisa diproyeksi.")
if str(JUMLAH_UJI_BACKTEST).lower() == "otomatis":
    # data latih minimum sebelum uji pertama: 16 bila data cukup panjang, selain itu sekitar 55% data
    min_train = 16 if n_obs >= 29 else max(2, int(np.ceil(n_obs * 0.55)))
    JUMLAH_UJI_BACKTEST = int(max(1, min(12, n_obs - min_train - 1)))
    CATATAN_AUTO.append(f"jumlah backtest {JUMLAH_UJI_BACKTEST} (dari {n_obs} triwulan data, data latih minimum {min_train})")
else:
    JUMLAH_UJI_BACKTEST = int(JUMLAH_UJI_BACKTEST)
    if n_obs - JUMLAH_UJI_BACKTEST - 1 < 4:
        _baru = int(max(1, n_obs - 5))
        PERINGATAN_DATA.append(f"JUMLAH_UJI_BACKTEST {JUMLAH_UJI_BACKTEST} terlalu banyak untuk {n_obs} triwulan data; "
                               f"diturunkan menjadi {_baru}")
        JUMLAH_UJI_BACKTEST = _baru
    min_train = n_obs - JUMLAH_UJI_BACKTEST - 1
if min_train >= 12 and JUMLAH_UJI_BACKTEST < 8:
    PERINGATAN_DATA.append(f"backtest hanya {JUMLAH_UJI_BACKTEST} kali (diatur manual / mode cepat): peringkat dan bobot Ensemble "
                           "kurang kokoh. Untuk hasil final gunakan jumlah backtest otomatis.")
elif min_train < 12 or JUMLAH_UJI_BACKTEST < 8:
    PERINGATAN_DATA.append(
        f"data pendek ({n_obs} triwulan): backtest {JUMLAH_UJI_BACKTEST} kali dengan data latih awal {min_train} triwulan. "
        "Peringkat dan bobot Ensemble kurang kokoh, dan metode yang butuh banyak data bisa gagal (dilewati otomatis). "
        "Rekomendasi: mundurkan DATA_MULAI atau tambah data bila ada, utamakan metode sederhana "
        "(Naive, Rata-rata, ARIMA, ETS, Theta), dan gunakan hasil sebagai indikasi awal.")
for w_ in PERINGATAN_DATA:
    print(f"  PERINGATAN: {w_}")

if str(DETEKSI_KRISIS).lower() not in ("otomatis", "manual"):
    stop('DETEKSI_KRISIS harus "otomatis" atau "manual".')

# --- mode level ------------------------------------------------------------------
LVL = None
if MODE_LEVEL:
    LVL = df_full[TARGET_LEVEL].loc[:p_sampai].dropna()

# --- metode aktif; yang tidak bisa jalan dilewati otomatis beserta alasannya ----------------
BUTUH_INDIKATOR = ["ARIMAX", "VAR", "BVAR", "Elastic Net", "Faktor (PCA)"]
aktif = [m for m, on in METODE.items() if on]
alasan_lewat = {}
for m in aktif:
    if m in METODE_LEVEL and not MODE_LEVEL:
        alasan_lewat[m] = f"butuh kolom level {TARGET_LEVEL or '(TARGET_LEVEL)'} di file data"
    elif m in METODE_LEVEL and len(LVL.loc[p_mulai - 4:]) < 20:
        alasan_lewat[m] = f"data level kurang dari 5 tahun ({len(LVL.loc[p_mulai - 4:])} triwulan)"
    elif m in BUTUH_INDIKATOR and not EXOG_ALL:
        alasan_lewat[m] = "butuh minimal 1 indikator pendukung"
dilewati = list(alasan_lewat)
aktif = [m for m in aktif if m not in dilewati]
if not aktif:
    stop("Tidak ada metode yang bisa dijalankan. Aktifkan minimal satu metode di bagian METODE.")
os.makedirs(FOLDER_OUTPUT, exist_ok=True)

print("=" * 72)
print(f" Target        : {TARGET} ({LABEL[TARGET]})")
print(f" Mode          : {'LEVEL (pola musiman dari ' + TARGET_LEVEL + ')' if MODE_LEVEL else 'YOY (tidak ada kolom level)'}")
print(f" Sumber yoy    : {SUMBER_YOY}")
print(f" Data dipakai  : {df_raw.index[0]} s.d. {df_raw.index[-1]} ({len(df_raw)} obs)")
print(f" Proyeksi      : {fc_periods[0]} s.d. {fc_periods[-1]} ({H} triwulan)")
print(f" Indikator     : {', '.join(EXOG_ALL) if EXOG_ALL else '-'}")
print(f" Metode        : {', '.join(aktif)}{' + Ensemble' if PAKAI_ENSEMBLE else ''}")
for m_, a_ in alasan_lewat.items():
    print(f" Dilewati      : {m_} ({a_})")
print(f" Dummy pandemi : {'Ya' if PAKAI_DUMMY_PANDEMI else 'Tidak'} | Backtest: {JUMLAH_UJI_BACKTEST} uji | CI {SELANG_KEPERCAYAAN}%")
_kal_aktif = [n_ for n_, on_ in (("Ramadan", PAKAI_RAMADAN), ("Idul Fitri", PAKAI_IDUL_FITRI), ("Idul Adha", PAKAI_IDUL_ADHA)) if on_]
print(f" Efek musiman  : kalender {'(' + ', '.join(_kal_aktif) + ') di model level' if PAKAI_EFEK_KALENDER and _kal_aktif else 'tidak'}"
      f"{' + model yoy' if PAKAI_EFEK_KALENDER and KALENDER_DI_MODEL_YOY else ''}"
      f" | dummy triwulan yoy: {'Ya' if EFEK_TRIWULAN_YOY else 'Tidak'}")
for c_ in CATATAN_AUTO:
    print(f" Otomatis      : {c_}")
print("=" * 72)

# =============================================================================
# 2. VALIDASI DATA
# =============================================================================
def robust_z(s):
    med = s.median()
    mad = 1.4826 * (s - med).abs().median()
    return (s - med) / (mad if mad > 0 else s.std())

col_out = f"Jumlah outlier (|z robust| > {BATAS_OUTLIER})"
val_rows = []
for c in df_raw.columns:
    s = df_raw[c]
    rz = robust_z(s.dropna())
    out = rz[rz.abs() > BATAS_OUTLIER]
    try:
        adf_p = adfuller(s.dropna(), autolag="AIC")[1]
    except Exception:
        adf_p = np.nan
    val_rows.append({
        "Kode": c, "Indikator": LABEL[c], "Obs": int(s.notna().sum()), "Kosong": int(s.isna().sum()),
        "Min": s.min(), "Median": s.median(), "Maks": s.max(), "Std": s.std(),
        col_out: len(out), "Periode outlier": ", ".join(str(p) for p in out.index),
        "ADF p-value": adf_p, "Stasioner (5%)": "Ya" if adf_p < 0.05 else "Tidak",
        f"Korelasi dg {TARGET} (t)": s.corr(df_raw[TARGET]) if c != TARGET else 1.0,
        f"Korelasi dg {TARGET} (t-1)": s.shift(1).corr(df_raw[TARGET]) if c != TARGET else np.nan,
    })
validasi = pd.DataFrame(val_rows)
print("\nVALIDASI DATA")
print(validasi[["Kode", "Obs", "Kosong", col_out, "ADF p-value", f"Korelasi dg {TARGET} (t)"]]
      .round(3).to_string(index=False))
if df_raw[TARGET].isna().any():
    print(f"  Catatan: {int(df_raw[TARGET].isna().sum())} nilai target kosong diisi interpolasi linear.")

df = df_raw.copy()
df[TARGET] = df[TARGET].interpolate(limit_direction="both")


# ---- Penanda krisis --------------------------------------------------------------------
def _rentang(a, b, nama):
    return list(pd.period_range(to_period(a, nama), to_period(b, nama), freq="Q"))


def ringkas_periode(ps):
    """[2020Q1, 2020Q2, 2021Q2] -> '2020Q1 s.d. 2020Q2, 2021Q2'"""
    ps = sorted(ps)
    if not ps:
        return "-"
    out, a, b = [], ps[0], ps[0]
    for p in ps[1:]:
        if p == b + 1:
            b = p
        else:
            out.append(str(a) if a == b else f"{a} s.d. {b}"); a = b = p
    out.append(str(a) if a == b else f"{a} s.d. {b}")
    return ", ".join(out)


_manual = [p for a, b in PERIODE_KRISIS for p in _rentang(a, b, "PERIODE_KRISIS")]
if str(DETEKSI_KRISIS).lower() == "manual":
    KRISIS, INFO_KRISIS = sorted(set(_manual)), "manual (PERIODE_KRISIS)"
else:
    _w = set(_rentang(JENDELA_KRISIS[0], JENDELA_KRISIS[1], "JENDELA_KRISIS"))
    _yk = df[TARGET]
    _norm = _yk[[p not in _w for p in _yk.index]].dropna()
    if len(_norm) >= 8:
        _med, _sd = _norm.median(), max(_norm.std(), 0.1)
        _cand = _yk[[p in _w for p in _yk.index]]
        KRISIS = sorted(_cand[(_cand - _med).abs() > AMBANG_KRISIS * _sd].index)
        INFO_KRISIS = (f"otomatis: yoy di {JENDELA_KRISIS[0]} s.d. {JENDELA_KRISIS[1]} yang menyimpang > "
                       f"{AMBANG_KRISIS:g} x {_sd:.2f} pp dari median normal {_med:.2f}%")
    else:
        KRISIS = sorted(set(_manual))
        INFO_KRISIS = "PERIODE_KRISIS (data periode normal kurang dari 8 triwulan, deteksi otomatis tidak bisa)"
KRISIS = [p for p in KRISIS if df.index[0] <= p <= df.index[-1]]
SPAN_KRISIS = list(pd.period_range(KRISIS[0], KRISIS[-1], freq="Q")) if KRISIS else []
if PAKAI_DUMMY_PANDEMI and not KRISIS:
    PAKAI_DUMMY_PANDEMI = False
    CATATAN_AUTO.append("dummy krisis tidak dipakai (tidak ada triwulan krisis di periode data)")
if KRISIS:
    CATATAN_AUTO.append(f"triwulan krisis: {ringkas_periode(KRISIS)} ({INFO_KRISIS})")
print(f"\nPENANDA KRISIS : {ringkas_periode(KRISIS)}" + ("" if PAKAI_DUMMY_PANDEMI else " (dummy tidak dipakai)"))
print(f"  {INFO_KRISIS}")


def normal(p):
    """True bila periode p di luar rentang krisis (dari triwulan krisis pertama s.d. terakhir)."""
    return p not in SPAN_KRISIS


def isi_krisis(y):
    """Triwulan krisis diganti interpolasi linear. Dipakai metode tanpa regresor (ETS, Theta)."""
    if not PAKAI_DUMMY_PANDEMI or not KRISIS:
        return y
    m = y.index.isin(KRISIS)
    if not m.any() or m.all():
        return y
    s = y.copy()
    s[m] = np.nan
    return s.interpolate(limit_direction="both")


# ---- Pembersihan outlier indikator: batas dari periode normal, triwulan krisis tidak dipangkas ----
winsor_log = []
_ok_norm = np.array([normal(p) for p in df.index])
for c in EXOG_ALL:
    s = df[c]
    nm = s[_ok_norm].dropna()
    if len(nm) < 8:
        nm = s.dropna()
    med = nm.median()
    skala = max(1.4826 * (nm - med).abs().median(), nm.std())   # skala minimum = simpangan baku normal
    lo, hi = med - BATAS_OUTLIER * skala, med + BATAS_OUTLIER * skala
    if OUTLIER_MANUAL is not None:                               # pilihan manual dari aplikasi web
        for x in [to_period(v, "OUTLIER_MANUAL") for v in (OUTLIER_MANUAL.get(c) or [])]:
            if x not in s.index or pd.isna(s[x]):
                continue
            lama = float(s[x])
            baru = np.nan if OUTLIER_CARA == "hapus" else float(np.clip(lama, lo, hi))
            df.loc[x, c] = baru
            winsor_log.append({"Kode": c, "Periode": str(x), "Nilai asli": lama,
                               "Nilai baru": "diisi interpolasi" if OUTLIER_CARA == "hapus" else baru,
                               "Cara": OUTLIER_CARA, "Batas bawah": lo, "Batas atas": hi})
    elif BERSIHKAN_OUTLIER:
        luar = ((s < lo) | (s > hi)) & _ok_norm
        if luar.any():
            winsor_log.append({"Kode": c, "Batas bawah": lo, "Batas atas": hi, "Nilai dipangkas": int(luar.sum()),
                               "Periode": ", ".join(str(p) for p in s.index[luar])})
            df.loc[luar, c] = s[luar].clip(lo, hi)
df[EXOG_ALL] = df[EXOG_ALL].interpolate(limit_direction="both")

# ---- Variabel kalender -----------------------------------------------------------
# Level (untuk model berbasis level): porsi hari Ramadan / puncak Lebaran / Idul Adha yang jatuh di tiap triwulan.
# Yoy (untuk model berbasis yoy): selisih porsi tersebut dengan triwulan yang sama tahun lalu.
# Nataru dan HBKN Natal selalu jatuh di Q4 setiap tahun: di model level ditangkap komponen musiman Q4,
# di model yoy saling meniadakan (Q4 dibanding Q4), sehingga tidak perlu variabel terpisah.
ALL_IDX = df.index.append(fc_periods)
IDX_KAL = pd.period_range(min(ALL_IDX[0], (LVL.index[0] if MODE_LEVEL else ALL_IDX[0])) - 4, ALL_IDX[-1], freq="Q")


def buat_kalender(idx):
    tahun = range(idx[0].year - 1, idx[-1].year + 2)
    fitri = PAKAI_RAMADAN or PAKAI_IDUL_FITRI
    kurang = [t for t in tahun if (fitri and t not in TANGGAL_IDUL_FITRI) or (PAKAI_IDUL_ADHA and t not in TANGGAL_IDUL_ADHA)]
    if kurang:
        stop(f"Tanggal Idul Fitri/Idul Adha tahun {kurang} belum ada di TANGGAL_IDUL_FITRI / TANGGAL_IDUL_ADHA.")
    hari = pd.date_range(f"{tahun[0]}-01-01", f"{tahun[-1]}-12-31")
    ram = pd.Series(0.0, index=hari); leb = ram.copy(); adha = ram.copy()
    for t in tahun:
        if fitri:
            d = pd.Timestamp(TANGGAL_IDUL_FITRI[t])
            ram[d - pd.Timedelta(days=RAMADAN_HARI): d - pd.Timedelta(days=1)] = 1
            leb[d - pd.Timedelta(days=LEBARAN_HARI_SEBELUM): d + pd.Timedelta(days=LEBARAN_HARI_SESUDAH)] = 1
        if PAKAI_IDUL_ADHA:
            da = pd.Timestamp(TANGGAL_IDUL_ADHA[t])
            adha[da - pd.Timedelta(days=IDUL_ADHA_HARI_SEBELUM): da + pd.Timedelta(days=IDUL_ADHA_HARI_SESUDAH)] = 1
    q = hari.to_period("Q")
    kal = pd.DataFrame(index=ram.groupby(q).sum().index)
    if PAKAI_RAMADAN:
        kal["K_RAMADAN"] = ram.groupby(q).sum() / max(RAMADAN_HARI, 1)
    if PAKAI_IDUL_FITRI:
        kal["K_LEBARAN"] = leb.groupby(q).sum() / (LEBARAN_HARI_SEBELUM + LEBARAN_HARI_SESUDAH + 1)
    if PAKAI_IDUL_ADHA:
        kal["K_IDULADHA"] = adha.groupby(q).sum() / (IDUL_ADHA_HARI_SEBELUM + IDUL_ADHA_HARI_SESUDAH + 1)
    return kal.reindex(pd.period_range(idx[0] - 4, idx[-1], freq="Q"))


if PAKAI_EFEK_KALENDER and not (PAKAI_RAMADAN or PAKAI_IDUL_FITRI or PAKAI_IDUL_ADHA):
    PAKAI_EFEK_KALENDER = False
    print("  Catatan: Ramadan, Idul Fitri, dan Idul Adha semuanya False, efek kalender tidak dipakai.")


KAL_LVL = buat_kalender(IDX_KAL) if PAKAI_EFEK_KALENDER else pd.DataFrame(index=IDX_KAL)
KAL_YOY = (KAL_LVL - KAL_LVL.shift(4)).add_suffix("_yoy")

# Dummy (untuk model berbasis yoy): pandemi + kalender dalam bentuk yoy
DUM = pd.DataFrame(index=ALL_IDX)
if PAKAI_DUMMY_PANDEMI:
    for pk in KRISIS:                      # satu dummy impuls per triwulan krisis
        DUM[f"D_K{pk}"] = [1.0 if p == pk else 0.0 for p in ALL_IDX]
if PAKAI_EFEK_KALENDER and KALENDER_DI_MODEL_YOY:
    DUM = DUM.join(KAL_YOY.reindex(ALL_IDX))
if EFEK_TRIWULAN_YOY:
    for q_ in (1, 2, 3):
        DUM[f"D_Q{q_}"] = [1.0 if p.quarter == q_ else 0.0 for p in ALL_IDX]

# Dummy (untuk model berbasis level): impuls di setiap triwulan dalam rentang krisis, karena level PDRB
# tertekan sepanjang rentang itu (termasuk triwulan yang yoy-nya tampak normal akibat basis rendah)
DUM_L = pd.DataFrame(index=IDX_KAL)
if MODE_LEVEL and PAKAI_DUMMY_PANDEMI:
    for pk in SPAN_KRISIS:
        DUM_L[f"D_K{pk}"] = [1.0 if p == pk else 0.0 for p in IDX_KAL]
if MODE_LEVEL and PAKAI_EFEK_KALENDER:
    DUM_L = DUM_L.join(KAL_LVL.reindex(IDX_KAL))


# ---- Jarak yoy antarkuartal: pola historis periode normal -------------------------------
# Awal rentang pembanding pola musiman (mode level)
if str(POLA_MUSIMAN_MULAI).lower() == "otomatis":
    _c = (SPAN_KRISIS[-1] + 1) if SPAN_KRISIS else df_raw.index[0]
    if MODE_LEVEL and LVL.index[0] < _c and p_sampai.ordinal - _c.ordinal + 1 >= 8:
        POLA_MUSIMAN_MULAI = str(_c)
    else:
        POLA_MUSIMAN_MULAI = str(max(df_raw.index[0], p_sampai - 11))


def _korelasi_normal(y, X):
    """|Korelasi| indikator dengan target, dihitung di luar masa pandemi & rebound (menghindari korelasi semu)."""
    ok = [normal(p) for p in y.index]
    if sum(ok) < 8:
        ok = [True] * len(y)
    return X[ok].corrwith(y[ok]).abs().dropna().sort_values(ascending=False)


VAR_HILANG = []


def pilih_var(y, X):
    """Variabel VAR/BVAR: target + indikator otomatis (korelasi) atau daftar VAR_INDIKATOR."""
    if VAR_INDIKATOR == "otomatis":
        kor = _korelasi_normal(y, X)
        sel = list(kor[kor >= VAR_KORELASI_MIN].index[:VAR_JUMLAH_OTOMATIS]) or list(kor.index[:1])
    else:
        sel = [v for v in VAR_INDIKATOR if v in X.columns]
        if not sel:   # semua yang ditulis tidak tersedia: kembali ke pilihan otomatis
            kor = _korelasi_normal(y, X)
            sel = list(kor.index[:1])
    return [TARGET] + sel


if EXOG_ALL:
    VAR_VARS = pilih_var(df[TARGET], df[EXOG_ALL])
    if VAR_INDIKATOR != "otomatis":
        VAR_HILANG = [v for v in VAR_INDIKATOR if v not in EXOG_ALL]
        if VAR_HILANG:
            CATATAN_AUTO.append(f"VAR_INDIKATOR {', '.join(VAR_HILANG)} tidak tersedia, tidak ikut VAR/BVAR"
                                + ("" if len(VAR_VARS) > 1 and any(v in EXOG_ALL for v in VAR_INDIKATOR)
                                   else f"; diganti pilihan otomatis {', '.join(VAR_VARS[1:])}"))
            print(f"  CATATAN: {CATATAN_AUTO[-1]}")
    print(f"  Variabel VAR/BVAR ({'otomatis' if VAR_INDIKATOR == 'otomatis' else 'ditentukan'}): {', '.join(VAR_VARS)}")
else:
    VAR_VARS = [TARGET]


DY = df[TARGET].diff()
DY_NORMAL = DY[[normal(p) and normal(p - 1) for p in DY.index]].dropna()
if BATAS_PERUBAHAN_YOY == "otomatis":
    BATAS_YOY = float(DY_NORMAL.abs().quantile(KUANTIL_BATAS / 100)) if len(DY_NORMAL) >= 8 else None
elif BATAS_PERUBAHAN_YOY is None:
    BATAS_YOY = None
else:
    BATAS_YOY = float(BATAS_PERUBAHAN_YOY)

# Tabel pola yoy per triwulan (untuk cek Q4 vs Q3 secara yoy)
_t = df[TARGET]
pola_yoy_hist = pd.DataFrame({"Tahun": _t.index.year, "Q": [f"Q{p.quarter}" for p in _t.index], "v": _t.values}) \
    .pivot(index="Tahun", columns="Q", values="v")
pola_yoy_hist = pola_yoy_hist.reindex(columns=["Q1", "Q2", "Q3", "Q4"])
for a_, b_ in [("Q2", "Q1"), ("Q3", "Q2"), ("Q4", "Q3")]:
    pola_yoy_hist[f"{a_} - {b_} (pp)"] = pola_yoy_hist[a_] - pola_yoy_hist[b_]
pola_yoy_hist["Tahun normal"] = ["Ya" if all(normal(pd.Period(f"{yr}Q{q}", "Q")) for q in range(1, 5)) else "Tidak"
                                 for yr in pola_yoy_hist.index]
_n = pola_yoy_hist[(pola_yoy_hist["Tahun normal"] == "Ya")].dropna(subset=["Q3", "Q4"])
Q4Q3_RATA2 = _n["Q4 - Q3 (pp)"].mean() if len(_n) else np.nan
Q4Q3_PORSI = (_n["Q4 - Q3 (pp)"] > 0).mean() * 100 if len(_n) else np.nan

print("\nJARAK YOY ANTARKUARTAL (periode normal, tanpa pandemi & rebound)")
print(f"  Median |perubahan yoy| : {DY_NORMAL.abs().median():.2f} pp | persentil {KUANTIL_BATAS}: "
      f"{DY_NORMAL.abs().quantile(KUANTIL_BATAS / 100):.2f} pp | maks: {DY_NORMAL.abs().max():.2f} pp")
print(f"  Batas perubahan dipakai: {'tidak ada' if BATAS_YOY is None else f'{BATAS_YOY:.2f} pp per triwulan'}")
print(f"  Yoy Q4 dibanding Q3    : rata-rata {Q4Q3_RATA2:+.2f} pp, Q4 > Q3 pada {Q4Q3_PORSI:.0f}% tahun normal "
      f"({len(_n)} tahun). Angka ini bisa jadi acuan PENYESUAIAN Q4.")


def rapikan(y_last, r, nama):
    """Pangkas lompatan yoy antarkuartal yang melebihi BATAS_YOY (selang ikut digeser)."""
    if BATAS_YOY is None or nama in BENCHMARK:
        return r
    mean = np.asarray(r["mean"], dtype=float)
    baru, prev = [], float(y_last)
    for v in mean:
        prev = float(np.clip(v, prev - BATAS_YOY, prev + BATAS_YOY))
        baru.append(prev)
    geser = np.array(baru) - mean
    r = dict(r)
    r["mean"] = np.array(baru)
    r["dipangkas"] = int((np.abs(geser) > 1e-9).sum())
    if r.get("lo") is not None:
        r["lo"] = np.asarray(r["lo"], float) + geser
        r["hi"] = np.asarray(r["hi"], float) + geser
    return r


def dummies(train_idx, h, tabel=None):
    """Regresor deterministik untuk data latih & periode proyeksi. Kolom yang isinya nol semua dibuang."""
    tabel = DUM if tabel is None else tabel
    cols = [c for c in tabel.columns if tabel.loc[train_idx, c].abs().sum() > 0]
    if not cols:
        return None, None
    fut = pd.period_range(train_idx[-1] + 1, periods=h, freq="Q")
    return tabel.loc[train_idx, cols].values, tabel.loc[fut, cols].values


def stack(*arrs):
    arrs = [a for a in arrs if a is not None and a.size]
    return np.column_stack(arrs) if arrs else None


def level_dari_yoy(L_hist, periods, yoy):
    """Level proyeksi dari yoy: L_t = L_(t-4) x (1 + yoy/100), memakai level aktual/hasil proyeksi sebelumnya."""
    s = L_hist.copy()
    for p, g in zip(periods, yoy):
        s.loc[p] = s.loc[p - 4] * (1 + g / 100)
    return s.loc[periods].values


def yoy_dari_level(L_hist, periods, lvl):
    s = pd.concat([L_hist, pd.Series(lvl, index=periods)])
    return np.array([(s.loc[p] / s.loc[p - 4] - 1) * 100 for p in periods])

# =============================================================================
# 3. METODE PROYEKSI
#    fungsi(y_train, X_train, h) -> dict(mean, lo, hi, res, info)   (mean/lo/hi dalam % yoy)
#    lo/hi None = selang dihitung dari error backtest
# =============================================================================
def m_naive(y, X, h):
    d = y.diff()
    dn = d[[normal(p) and normal(p - 1) for p in d.index]].dropna()
    sd = (dn if len(dn) >= 6 else d.dropna()).std()      # simpangan dari periode normal (bukan pandemi)
    mean = np.repeat(y.iloc[-1], h)
    se = sd * np.sqrt(np.arange(1, h + 1))
    return dict(mean=mean, lo=mean - Z * se, hi=mean + Z * se)


def m_mean(y, X, h):
    return dict(mean=np.repeat(y.iloc[-RATA2_JUMLAH_TRIWULAN:].mean(), h), lo=None, hi=None)


def _best_arima(y, exog=None, max_pq=2):
    best = None
    for p in range(max_pq + 1):
        for q in range(max_pq + 1):
            try:
                r = SARIMAX(y.values, exog=exog, order=(p, 0, q), trend="c").fit(disp=False)
                if best is None or r.aic < best[0].aic:
                    best = (r, (p, 0, q))
            except Exception:
                pass
    return best


def _auto(v):
    return str(v).lower() == "otomatis"


def m_arima(y, X, h):
    d_tr, d_fc = dummies(y.index, h)
    res, order = _best_arima(y, exog=d_tr, max_pq=(2 if len(y) >= 24 else 1) if _auto(ARIMA_MAX_PQ) else int(ARIMA_MAX_PQ))
    fc = res.get_forecast(h, exog=d_fc)
    ci = fc.conf_int(alpha=1 - CI)
    return dict(mean=fc.predicted_mean, lo=ci[:, 0], hi=ci[:, 1], res=res,
                info=f"ARIMA{order}{' + regresor deterministik' if d_tr is not None else ''}")


def m_ets(y, X, h):
    trend = None if ETS_TREN == "tanpa" else "add"
    yf = isi_krisis(y)                                    # triwulan krisis diisi interpolasi sebelum fitting
    res = ExponentialSmoothing(yf.values, trend=trend, damped_trend=(ETS_TREN == "damped")).fit(optimized=True)
    mean = res.forecast(h)
    sd = np.std(res.resid, ddof=1)
    se = sd * np.sqrt(np.arange(1, h + 1))
    return dict(mean=mean, lo=mean - Z * se, hi=mean + Z * se, res=res, info=f"ETS tren {ETS_TREN}")


def m_theta(y, X, h):
    res = ThetaModel(isi_krisis(y).values, period=4, deseasonalize=False).fit()
    mean = np.asarray(res.forecast(h))
    pi = np.asarray(res.prediction_intervals(h, alpha=1 - CI))
    return dict(mean=mean, lo=pi[:, 0], hi=pi[:, 1], info="Theta (theta = 2, tanpa deseasonalisasi)")


def _forecast_exog(Xc, h):
    """Proyeksi indikator untuk ARIMAX. AR(1) diberi dummy pandemi supaya indikator kembali ke rata-rata
    periode normal (bukan rata-rata yang tertarik oleh anjloknya 2020)."""
    if ARIMAX_PROYEKSI_INDIKATOR == "rata2":
        return pd.DataFrame({c: np.repeat(Xc[c].iloc[-4:].mean(), h) for c in Xc.columns})
    dcols = [c for c in DUM.columns if c.startswith("D_K") and DUM.loc[Xc.index, c].sum() > 0]
    ex = DUM.loc[Xc.index, dcols].values if dcols else None
    ex_f = np.zeros((h, len(dcols))) if dcols else None
    out = {}
    for c in Xc.columns:
        try:
            out[c] = SARIMAX(Xc[c].values, exog=ex, order=(1, 0, 0), trend="c").fit(disp=False).forecast(h, exog=ex_f)
        except Exception:
            out[c] = np.repeat(Xc[c].iloc[-4:].mean(), h)
    return pd.DataFrame(out)


def _pilih_indikator(y, X):
    """Indikator ARIMAX: korelasi tertinggi (default tanpa periode pandemi & rebound), di atas ambang minimum."""
    kor = _korelasi_normal(y, X) if ARIMAX_PILIH_TANPA_PANDEMI else X.corrwith(y).abs().dropna().sort_values(ascending=False)
    k = min(ARIMAX_JUMLAH_INDIKATOR, max(1, len(y) // 10))   # data pendek: indikator lebih sedikit
    sel = list(kor[kor >= ARIMAX_KORELASI_MIN].index[:k])
    return sel or list(kor.index[:1])


def m_arimax(y, X, h):
    sel = _pilih_indikator(y, X)
    d_tr, d_fc = dummies(y.index, h)
    ex_tr = stack(X[sel].values, d_tr)
    ex_fc = stack(_forecast_exog(X[sel], h).values, d_fc)
    res, order = _best_arima(y, exog=ex_tr, max_pq=int(ARIMAX_MAX_PQ))
    fc = res.get_forecast(h, exog=ex_fc)
    ci = fc.conf_int(alpha=1 - CI)
    return dict(mean=fc.predicted_mean, lo=ci[:, 0], hi=ci[:, 1], res=res,
                info=f"ARIMAX{order}, indikator: {', '.join(sel)} (proyeksi indikator: {ARIMAX_PROYEKSI_INDIKATOR})")


def m_var(y, X, h):
    vv = pilih_var(y, X)
    data = pd.concat([y, X], axis=1)[vv]
    d_tr, d_fc = dummies(y.index, h)
    model = VAR(data.values, exog=d_tr)
    maxlag = int(min(2, max(1, (len(y) - 8) // (2 * len(vv)))))   # lag maksimum 2, lebih kecil bila data pendek
    if not _auto(VAR_MAXLAG):
        maxlag = max(1, min(int(VAR_MAXLAG), (len(y) - 4) // (len(vv) + 1)))
    try:
        p = max(1, int(model.select_order(maxlags=maxlag).aic))
    except Exception:
        p = 1
    res = model.fit(p)
    mean, lo, hi = res.forecast_interval(data.values[-p:], steps=h, alpha=1 - CI, exog_future=d_fc)
    return dict(mean=mean[:, 0], lo=lo[:, 0], hi=hi[:, 0], res=res, info=f"VAR({p}) {' + '.join(vv)}")


def m_bvar(y, X, h):
    """VAR Bayesian dengan prior Minnesota. Tiap koefisien 'ditarik' ke prior: lag-1 variabel sendiri = 0.8
    (yoy persisten), koefisien lain = 0. Konstanta & dummy pandemi tanpa prior (bebas)."""
    vv = pilih_var(y, X)
    data = pd.concat([y, X], axis=1)[vv].values
    T, nv = data.shape
    p = (2 if T >= 24 else 1) if str(BVAR_LAG).lower() == "otomatis" else int(BVAR_LAG)
    d_tr, d_fc = dummies(y.index, h)
    nd = 0 if d_tr is None else d_tr.shape[1]

    def regresor(hist, t, d_row):
        lags = np.concatenate([hist[t - l] for l in range(1, p + 1)])
        return np.r_[1.0, lags, d_row if nd else []]

    Z = np.array([regresor(data, t, d_tr[t] if nd else None) for t in range(p, T)])
    Y = data[p:]
    # skala tiap variabel: simpangan residual AR(p) univariat
    sig = []
    for j in range(nv):
        Zj = np.column_stack([np.ones(T - p)] + [data[p - l:T - l, j] for l in range(1, p + 1)])
        e = data[p:, j] - Zj @ np.linalg.lstsq(Zj, data[p:, j], rcond=None)[0]
        sig.append(max(np.std(e, ddof=1), 1e-6))
    sig = np.array(sig)
    B = np.zeros((Z.shape[1], nv))
    for i in range(nv):
        b0 = np.zeros(Z.shape[1]); v0 = np.full(Z.shape[1], 1e6)   # konstanta & dummy: prior sangat longgar
        for l in range(1, p + 1):
            for j in range(nv):
                k = 1 + (l - 1) * nv + j
                v0[k] = (BVAR_KETATAN / l) ** 2 if i == j else (BVAR_KETATAN * 0.5 * sig[i] / (l * sig[j])) ** 2
                if i == j and l == 1:
                    b0[k] = 0.8
        prec = Z.T @ Z / sig[i] ** 2 + np.diag(1 / v0)
        B[:, i] = np.linalg.solve(prec, Z.T @ Y[:, i] / sig[i] ** 2 + b0 / v0)
    hist = list(data)
    for k in range(h):
        z = regresor(np.array(hist), len(hist), d_fc[k] if nd else None)
        hist.append(z @ B)
    mean = np.array(hist[T:])[:, 0]
    return dict(mean=mean, lo=None, hi=None, info=f"BVAR({p}) Minnesota, ketatan {BVAR_KETATAN}: {' + '.join(vv)}")


def _direct_ml(y, X, h, make_model):
    """Satu model per horizon; fitur diambil h triwulan sebelumnya, jadi indikator tidak perlu diproyeksi.
    Variabel kalender dipakai pada periode sasaran (sudah diketahui di muka). Baris yang menyentuh rentang krisis
    tidak dipakai melatih (bila sisa data cukup)."""
    feats = pd.concat([y.rename("y_lag"), y.shift(1).rename("y_lag2"), X], axis=1)
    dcols = [c for c in DUM.columns if DUM.loc[y.index, c].abs().sum() > 0]
    preds = []
    for k in range(1, h + 1):
        Xk = pd.concat([feats.shift(k), DUM.loc[y.index, dcols]], axis=1)
        dat = pd.concat([Xk, y.rename("target")], axis=1).dropna()
        dk = list(dcols)
        if PAKAI_DUMMY_PANDEMI and KRISIS:
            # latih hanya pada baris yang target DAN fitur lag-nya di luar rentang krisis; dummy krisis jadi tidak perlu
            ok = [normal(p) and normal(p - k) and normal(p - k - 1) for p in dat.index]
            if sum(ok) >= 8:
                dk = [c for c in dcols if not c.startswith("D_K")]
                dat = dat.loc[ok, [c for c in dat.columns if c not in dcols or c in dk]]
        m = make_model(len(dat))
        m.fit(dat.drop(columns="target").values, dat["target"].values)
        x_new = pd.concat([feats.iloc[[-1]].reset_index(drop=True),
                           DUM.loc[[y.index[-1] + k], dk].reset_index(drop=True)], axis=1)
        preds.append(m.predict(x_new.values)[0])
    return dict(mean=np.array(preds), lo=None, hi=None)


def m_ridge(y, X, h):
    return _direct_ml(y, X, h, lambda n: make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 30))))


def m_enet(y, X, h):
    return _direct_ml(y, X, h, lambda n: make_pipeline(   # jumlah lipatan CV menyesuaikan jumlah data
        StandardScaler(), ElasticNetCV(l1_ratio=[.2, .5, .8, 1.0], cv=int(max(2, min(4, n // 5))),
                                       max_iter=20000, random_state=SEED)))


def m_faktor(y, X, h):
    """Indikator diringkas menjadi FAKTOR_JUMLAH faktor (PCA), lalu dipakai sebagai fitur regresi direct."""
    k = min(FAKTOR_JUMLAH, X.shape[1], max(1, len(y) // 12))   # data pendek: faktor lebih sedikit
    pca = make_pipeline(StandardScaler(), PCA(n_components=k))
    F = pd.DataFrame(pca.fit_transform(X.values), index=X.index, columns=[f"F{i + 1}" for i in range(k)])
    r = _direct_ml(y, F, h, lambda n: LinearRegression())
    var = pca.named_steps["pca"].explained_variance_ratio_.sum()
    r["info"] = f"{k} faktor PCA (menjelaskan {var:.0%} variasi indikator) + lag target"
    return r


def m_rf(y, X, h):
    return _direct_ml(y, X, h, lambda n: RandomForestRegressor(n_estimators=int(RF_POHON), max_depth=int(RF_KEDALAMAN),
                                                             min_samples_leaf=int(RF_MIN_DAUN), random_state=SEED))


def m_gbr(y, X, h):
    return _direct_ml(y, X, h, lambda n: GradientBoostingRegressor(n_estimators=int(GB_POHON), learning_rate=float(GB_LEARNING_RATE),
                                                                 max_depth=int(GB_KEDALAMAN),
                                                                 subsample=0.8, random_state=SEED))


def _level_train(y):
    L = LVL.loc[:y.index[-1]]
    return L[L.index >= p_mulai - 4]


def m_sarima_musiman(y, X, h):
    """SARIMA pada log level: (p,1,q)(P,1,Q)4. Pola musiman (termasuk Q4/Nataru) + regresor kalender & pandemi."""
    L = _level_train(y)
    lg = np.log(L)
    d_tr, d_fc = dummies(L.index, h, tabel=DUM_L)
    best = None
    for order in [(0, 1, 1), (1, 1, 0), (1, 1, 1), (0, 1, 0)]:
        for sorder in [(0, 1, 1, 4), (1, 1, 0, 4), (0, 1, 0, 4)]:
            try:
                r = SARIMAX(lg.values, exog=d_tr, order=order, seasonal_order=sorder).fit(disp=False)
                if best is None or r.aic < best[0].aic:
                    best = (r, order, sorder)
            except Exception:
                pass
    res, order, sorder = best
    fc = res.get_forecast(h, exog=d_fc)
    ci = fc.conf_int(alpha=1 - CI)
    fut = pd.period_range(L.index[-1] + 1, periods=h, freq="Q")
    lvl, lvl_lo, lvl_hi = np.exp(fc.predicted_mean), np.exp(ci[:, 0]), np.exp(ci[:, 1])
    mean = yoy_dari_level(L, fut, lvl)
    base = pd.concat([L, pd.Series(lvl, index=fut)])
    lo = np.array([(v / base.loc[p - 4] - 1) * 100 for p, v in zip(fut, lvl_lo)])
    hi = np.array([(v / base.loc[p - 4] - 1) * 100 for p, v in zip(fut, lvl_hi)])
    return dict(mean=mean, lo=lo, hi=hi, res=res, level=True,
                info=f"SARIMA{order}x{sorder[:3]}4 pada log {TARGET_LEVEL}"
                     f"{' + kalender' if PAKAI_EFEK_KALENDER else ''}{' + dummy krisis' if PAKAI_DUMMY_PANDEMI else ''}")


def m_ets_musiman(y, X, h):
    """Holt-Winters pada log level (tren damped + musiman aditif). Periode pandemi diganti jalur tanpa-pandemi
    supaya pola musiman tidak rusak; level pascapandemi tetap memakai data aktual."""
    L = _level_train(y)
    lg = np.log(L).copy()
    if PAKAI_DUMMY_PANDEMI and SPAN_KRISIS:
        a1, b2 = SPAN_KRISIS[0], SPAN_KRISIS[-1]
        pre = lg.loc[:a1 - 1]
        if len(pre) >= 8:
            g = (pre - pre.shift(4)).dropna().iloc[-4:].mean()
            for p in pd.period_range(a1, min(b2, lg.index[-1]), freq="Q"):
                lg.loc[p] = lg.loc[p - 4] + g
    res = ExponentialSmoothing(lg.values, trend="add", damped_trend=True, seasonal="add",
                               seasonal_periods=4).fit(optimized=True)
    fut = pd.period_range(L.index[-1] + 1, periods=h, freq="Q")
    lvl = np.exp(res.forecast(h))
    sd = np.std(np.asarray(res.resid)[4:], ddof=1)
    se = sd * np.sqrt(np.arange(1, h + 1))
    mean = yoy_dari_level(L, fut, lvl)
    base = pd.concat([L, pd.Series(lvl, index=fut)])
    lo = np.array([(v * np.exp(-Z * s) / base.loc[p - 4] - 1) * 100 for p, v, s in zip(fut, lvl, se)])
    hi = np.array([(v * np.exp(Z * s) / base.loc[p - 4] - 1) * 100 for p, v, s in zip(fut, lvl, se)])
    return dict(mean=mean, lo=lo, hi=hi, res=res, level=True, info=f"Holt-Winters (tren damped + musiman) pada log {TARGET_LEVEL}")


ALL_METHODS = {"Naive": m_naive, "Rata-rata 8Q": m_mean, "ARIMA": m_arima, "ETS": m_ets, "Theta": m_theta,
               "ARIMAX": m_arimax, "VAR": m_var, "BVAR": m_bvar, "Ridge": m_ridge, "Elastic Net": m_enet,
               "Faktor (PCA)": m_faktor, "Random Forest": m_rf, "Gradient Boosting": m_gbr,
               "SARIMA Musiman": m_sarima_musiman, "ETS Musiman": m_ets_musiman}
METHODS = {m: ALL_METHODS[m] for m in aktif}
comp = [m for m in METHODS if m not in BENCHMARK]
USE_ENS = PAKAI_ENSEMBLE and len(comp) >= 2

# =============================================================================
# 4. BACKTEST ROLLING-ORIGIN
# =============================================================================
y_all = df[TARGET]
X_all = df[EXOG_ALL]
n = len(y_all)
origins = range(n - JUMLAH_UJI_BACKTEST - 1, n - 1)
print(f"\nBacktest {JUMLAH_UJI_BACKTEST} titik asal ({y_all.index[origins[0]]} s.d. {y_all.index[origins[-1]]})...")

bt_rows = []
for o in origins:
    y_tr, X_tr = y_all.iloc[: o + 1], X_all.iloc[: o + 1]
    h_eval = min(H, n - 1 - o)
    for name, fn in METHODS.items():
        try:
            r0 = fn(y_tr, X_tr, H)
            r = rapikan(y_tr.iloc[-1], r0, name)
        except Exception as e:
            print(f"  {name} gagal di {y_tr.index[-1]}: {e}")
            continue
        for k in range(1, h_eval + 1):
            bt_rows.append({
                "Metode": name, "Origin": str(y_tr.index[-1]), "Periode": str(y_all.index[o + k]), "h": k,
                "Aktual": y_all.iloc[o + k], "Prediksi": float(np.asarray(r["mean"])[k - 1]),
                "Prediksi mentah": float(np.asarray(r0["mean"])[k - 1]),
                "Lower": None if r["lo"] is None else float(np.asarray(r["lo"])[k - 1]),
                "Upper": None if r["hi"] is None else float(np.asarray(r["hi"])[k - 1]),
                "Aktual origin": y_tr.iloc[-1],
            })
    print(f"  selesai: data s.d. {y_tr.index[-1]}")

bt = pd.DataFrame(bt_rows)
if bt.empty:
    stop("Semua metode gagal di backtest. Biasanya karena data terlalu pendek: mundurkan DATA_MULAI, tambah data, "
         "atau aktifkan hanya metode sederhana (Naive, Rata-rata 8Q, ARIMA, ETS, Theta).")
bt["Error"] = bt["Aktual"] - bt["Prediksi"]
bt["Error naive"] = bt["Aktual"] - bt["Aktual origin"]       # pembanding random walk
rmse_fn = lambda e: np.sqrt(np.mean(np.asarray(e, dtype=float) ** 2))
comp = [m for m in comp if m in set(bt.Metode)]               # metode yang gagal di semua titik uji dikeluarkan
USE_ENS = PAKAI_ENSEMBLE and len(comp) >= 2


def hitung_bobot(sub):
    """Bobot Ensemble dari baris backtest `sub`. Metode dengan RMSE > ENSEMBLE_BATAS_RMSE x RMSE random walk
    disaring (bila masih tersisa minimal 2 metode). Return (bobot, daftar metode yang disaring)."""
    rm = sub.groupby("Metode")["Error"].apply(rmse_fn)
    rw = rmse_fn(sub.drop_duplicates(["Origin", "Periode", "h"])["Error naive"])
    nt = sub.groupby("Metode").size()
    kurang = sorted(nt[nt < 0.5 * nt.max()].index)      # titik uji terlalu sedikit (sering gagal): tidak sebanding
    if len(rm) - len(kurang) >= 2:
        rm = rm.drop(kurang)
    else:
        kurang = []
    keluar = []
    if ENSEMBLE_SARING and np.isfinite(rw) and rw > 0:
        keluar = sorted(rm[rm > ENSEMBLE_BATAS_RMSE * rw].index)
        if len(rm) - len(keluar) >= 2:
            rm = rm.drop(keluar)
        else:
            keluar = []
    keluar = sorted(set(keluar) | set(kurang))
    rm = rm.sort_values()
    if ENSEMBLE_CARA == "top":
        rm = rm.iloc[:max(2, ENSEMBLE_TOP)]
    if ENSEMBLE_CARA == "median":
        return pd.Series(1 / len(rm), index=rm.index), keluar
    return (1 / rm) / (1 / rm).sum(), keluar


def gabung(P, w):
    """Gabungkan prediksi (kolom = metode). Metode yang kosong/gagal tidak dihitung sebagai nol:
    bobot dinormalkan ulang atas metode yang tersedia."""
    cols = [m for m in w.index if m in P.columns]
    P, w = P[cols], w[cols]
    if ENSEMBLE_CARA == "median":
        return P.median(axis=1)
    return P.mul(w, axis=1).sum(axis=1, min_count=1) / P.notna().mul(w, axis=1).sum(axis=1)


W, DISARING = pd.Series(dtype=float), []
if USE_ENS:
    b_comp = bt[bt.Metode.isin(comp)].copy()
    b_comp["_per"] = pd.PeriodIndex(b_comp["Periode"], freq="Q")
    W, DISARING = hitung_bobot(b_comp)                           # bobot final: seluruh backtest
    piv = b_comp.pivot_table(index=["Origin", "Periode", "h"], columns="Metode", values="Prediksi")
    piv_raw = b_comp.pivot_table(index=["Origin", "Periode", "h"], columns="Metode", values="Prediksi mentah")
    ens_parts = []
    for o in sorted(set(b_comp["Origin"])):
        # bobot di titik uji ini hanya dari error yang SUDAH terealisasi sebelum titik itu (tanpa bocoran)
        hist = b_comp[b_comp["_per"] <= pd.Period(o, "Q")]
        cukup = len(hist) and hist.groupby("Metode").size().min() >= 4 and hist["Metode"].nunique() >= 2
        w_o = hitung_bobot(hist)[0] if cukup else pd.Series(1 / len(comp), index=comp)
        Po, Ro = piv.xs(o, level="Origin", drop_level=False), piv_raw.xs(o, level="Origin", drop_level=False)
        ens_parts.append(pd.DataFrame({"Prediksi": gabung(Po, w_o), "Prediksi mentah": gabung(Ro, w_o)}))
    ens = pd.concat(ens_parts).reset_index()
    ref = bt.drop_duplicates(["Origin", "Periode", "h"])[["Origin", "Periode", "h", "Aktual", "Aktual origin", "Error naive"]]
    ens = ens.merge(ref, on=["Origin", "Periode", "h"])
    ens["Metode"] = "Ensemble"; ens["Lower"] = None; ens["Upper"] = None
    ens["Error"] = ens["Aktual"] - ens["Prediksi"]
    bt = pd.concat([bt, ens[bt.columns]], ignore_index=True)
    if DISARING:
        print(f"  Tidak ikut Ensemble (RMSE > {ENSEMBLE_BATAS_RMSE:g} x random walk / titik uji terlalu sedikit): "
              f"{', '.join(DISARING)}")

# Mode level: qtq prediksi di backtest (dari yoy prediksi + level aktual s.d. origin)
if MODE_LEVEL:
    bt["qtq Aktual"] = np.nan; bt["qtq Prediksi"] = np.nan
    for (m, o), g in bt.groupby(["Metode", "Origin"]):
        g = g.sort_values("h")
        per = pd.PeriodIndex(g["Periode"], freq="Q")
        L_hist = LVL.loc[:pd.Period(o, "Q")]
        lvl = pd.Series(level_dari_yoy(L_hist, per, g["Prediksi"].values), index=per)
        full = pd.concat([L_hist, lvl])
        bt.loc[g.index, "qtq Prediksi"] = [(full.loc[p] / full.loc[p - 1] - 1) * 100 for p in per]
        bt.loc[g.index, "qtq Aktual"] = [(LVL.loc[p] / LVL.loc[p - 1] - 1) * 100 for p in per]

# =============================================================================
# 5. METRIK ERROR
# =============================================================================
_dtr = y_all.iloc[: n - JUMLAH_UJI_BACKTEST].diff()
_okm = [normal(p) and normal(p - 1) for p in _dtr.index]
mase_scale = _dtr[_okm].abs().mean() if sum(_okm) >= 6 else _dtr.abs().mean()   # skala MASE dari periode normal
# pembanding untuk Theil's U & DM: random walk (kolom "Error naive", tidak tergantung metode Naive aktif)


def dm_test(e1, e2, h=1):
    d = np.asarray(e1) ** 2 - np.asarray(e2) ** 2
    T = len(d)
    if T < 3 or np.var(d) == 0:
        return np.nan, np.nan
    gamma = [np.cov(d[k:], d[:T - k])[0, 1] if k else np.var(d) for k in range(h)]
    dm = d.mean() / np.sqrt((gamma[0] + 2 * sum(gamma[1:])) / T)
    dm *= np.sqrt((T + 1 - 2 * h + h * (h - 1) / T) / T)
    return dm, 2 * (1 - stats.t.cdf(abs(dm), df=T - 1))


met_rows = []
for m, g in bt.groupby("Metode"):
    e, a, p = g["Error"].values, g["Aktual"].values, g["Prediksi"].values
    ao = g["Aktual origin"].values
    has_ci = g["Lower"].notna().all()
    g1 = g[g.h == 1]
    dm, dmp = (np.nan, np.nan) if m == "Naive" else dm_test(g1["Error"], g1["Error naive"])
    row = {
        "Metode": m, "RMSE": rmse_fn(e), "RMSE tanpa batas yoy": rmse_fn(g["Aktual"] - g["Prediksi mentah"]),
        "MAE": np.mean(np.abs(e)), "ME (bias)": np.mean(e),
        "sMAPE (%)": np.mean(2 * np.abs(e) / (np.abs(a) + np.abs(p))) * 100,
        "MASE": np.mean(np.abs(e)) / mase_scale,
        "Theil's U": rmse_fn(e) / rmse_fn(g["Error naive"].values),
        "Akurasi arah (%)": np.nan if m == "Naive" else np.mean(np.sign(p - ao) == np.sign(a - ao)) * 100,
        f"Coverage CI {SELANG_KEPERCAYAAN}% (%)": np.mean((a >= g["Lower"]) & (a <= g["Upper"])) * 100 if has_ci else np.nan,
        "DM stat (h=1) vs Naive": dm, "DM p-value": dmp, "Jumlah titik uji": len(e),
    }
    if MODE_LEVEL:
        row["RMSE qtq"] = rmse_fn((g["qtq Aktual"] - g["qtq Prediksi"]).values)
    met_rows.append(row)
metrik = pd.DataFrame(met_rows)
# metode yang titik ujinya kurang dari separuh (sering gagal) diurutkan paling bawah: RMSE-nya tidak sebanding
metrik["_kurang"] = metrik["Jumlah titik uji"] < 0.5 * metrik["Jumlah titik uji"].max()
metrik = metrik.sort_values(["_kurang", "RMSE"]).drop(columns="_kurang").reset_index(drop=True)
metrik.insert(0, "Peringkat", range(1, len(metrik) + 1))
rmse_h = bt.groupby(["Metode", "h"])["Error"].apply(rmse_fn).unstack()
rmse_h.columns = [f"h={c}" for c in rmse_h.columns]
rmse_h = rmse_h.loc[metrik["Metode"]]
peringkat_h = rmse_h.rank(axis=0, method="min").astype("Int64")      # peringkat tiap metode per horizon
print("\nMETRIK BACKTEST (urut RMSE terkecil)")
print(metrik[["Peringkat", "Metode", "RMSE", "MAE", "ME (bias)", "Theil's U", "Akurasi arah (%)"]
             + (["RMSE qtq"] if MODE_LEVEL else [])].round(3).to_string(index=False))
print("Kolom 'RMSE tanpa batas yoy' = error bila proyeksi tidak dipangkas BATAS_PERUBAHAN_YOY.")

# =============================================================================
# 6. PROYEKSI FINAL
# =============================================================================
def se_empiris(name):
    """RMSE backtest per horizon; bila horizon proyeksi lebih panjang dari backtest, diperpanjang dengan akar-h."""
    v = rmse_h.loc[name].dropna().values if name in rmse_h.index else np.array([])
    if len(v) == 0:
        return np.repeat(np.nan, H)
    if len(v) < H:
        v = np.r_[v, v[-1] * np.sqrt(np.arange(len(v) + 1, H + 1) / len(v))]
    return v[:H]


final, diag_rows, spesifikasi, dipangkas = {}, [], {}, {}
for name, fn in METHODS.items():
    try:
        r = rapikan(y_all.iloc[-1], fn(y_all, X_all, H), name)
    except Exception as e:                      # satu metode gagal tidak menghentikan notebook
        print(f"  {name} gagal di proyeksi final, dikeluarkan dari hasil: {e}")
        alasan_lewat[name] = f"gagal di proyeksi final: {e}"
        continue
    dipangkas[name] = r.get("dipangkas", 0)
    mean = np.asarray(r["mean"], dtype=float)
    if r["lo"] is None:
        se = se_empiris(name)
        lo, hi = mean - Z * se, mean + Z * se
    else:
        lo, hi = np.asarray(r["lo"], float), np.asarray(r["hi"], float)
    final[name] = pd.DataFrame({"Proyeksi": mean, "Lower": lo, "Upper": hi}, index=fc_periods)
    spesifikasi[name] = r.get("info", "")
    res = r.get("res")
    if res is None:
        continue
    if name == "VAR":
        resid = res.resid[:, 0]; aic, bic = res.aic, res.bic
        k_par = res.k_ar * len(VAR_VARS) + 1 + (0 if res.exog is None else res.exog.shape[1])
        actual = y_all.values[-len(resid):]
    elif r.get("level"):
        resid = np.asarray(res.resid)[5:]            # buang observasi awal yang hilang akibat differencing
        aic, bic = getattr(res, "aic", np.nan), getattr(res, "bic", np.nan)
        k_par = len(res.params)
        lg = np.log(_level_train(y_all).values)[5:]
        actual = lg - np.r_[np.log(_level_train(y_all).values)[4:-1]]  # R2 dihitung atas pertumbuhan qtq (log)
    else:
        resid = np.asarray(res.resid)[1:]
        aic, bic = getattr(res, "aic", np.nan), getattr(res, "bic", np.nan)
        k_par = len(res.params)
        actual = y_all.values[-len(resid):]
    r2 = 1 - np.sum(resid ** 2) / np.sum((actual - actual.mean()) ** 2)
    nn = len(resid)
    lb_p = acorr_ljungbox(resid, lags=[min(8, nn // 3)], return_df=True)["lb_pvalue"].iloc[0]
    jb_p = stats.jarque_bera(resid).pvalue
    diag_rows.append({"Metode": name, "Spesifikasi": spesifikasi[name], "R2": r2,
                      "Adj R2": 1 - (1 - r2) * (nn - 1) / max(nn - k_par - 1, 1),
                      "AIC": aic, "BIC": bic, "Ljung-Box p": lb_p, "Jarque-Bera p": jb_p,
                      "Residual tanpa autokorelasi": "Ya" if lb_p > 0.05 else "Tidak",
                      "Residual normal": "Ya" if jb_p > 0.05 else "Tidak"})
diagnostik = pd.DataFrame(diag_rows)

W = W[[m for m in W.index if m in final]]
if USE_ENS and len(W) >= 1:
    W = W / W.sum()
    ens_mean = gabung(pd.DataFrame({m: final[m]["Proyeksi"] for m in W.index}), W)
    if ENSEMBLE_CARA == "median":
        spesifikasi["Ensemble"] = "Median dari: " + ", ".join(W.index)
    else:
        spesifikasi["Ensemble"] = (f"{'Top ' + str(len(W)) + ', ' if ENSEMBLE_CARA == 'top' else ''}bobot inverse-RMSE: "
                                   + ", ".join(f"{k} {v:.0%}" for k, v in W.sort_values(ascending=False).items()))
    if DISARING:
        spesifikasi["Ensemble"] += (f". Tidak ikut (RMSE backtest > {ENSEMBLE_BATAS_RMSE:g} x random walk, "
                                    "atau titik uji kurang dari separuh karena sering gagal): " + ", ".join(DISARING))
    se_e = se_empiris("Ensemble")
    final["Ensemble"] = pd.DataFrame({"Proyeksi": ens_mean, "Lower": ens_mean - Z * se_e,
                                      "Upper": ens_mean + Z * se_e}, index=fc_periods)
    dipangkas["Ensemble"] = 0

ORDER = [m for m in metrik["Metode"] if m in final]
BEST = ORDER[0]

# ---- Penyesuaian judgment (add-factor) ----------------------------------------------
final_murni = {m: f.copy() for m, f in final.items()}
adj = pd.Series(0.0, index=fc_periods)
adj_log = []
for k_, v_ in PENYESUAIAN.items():
    p_ = to_period(k_, "PENYESUAIAN")
    if p_ in adj.index:
        adj[p_] = float(v_)
        adj_log.append({"Periode": str(p_), "Penyesuaian (pp yoy)": float(v_)})
    else:
        print(f"  Catatan: PENYESUAIAN {k_} di luar periode proyeksi, diabaikan.")
for m in final:
    final[m] = final[m].add(adj, axis=0)
if (adj != 0).any():
    print("\nPENYESUAIAN diterapkan (pp yoy): " + ", ".join(f"{p}: {v:+.2f}" for p, v in adj.items() if v != 0))

proj_wide = pd.DataFrame({m: final[m]["Proyeksi"] for m in ORDER}, index=fc_periods)
proj_murni = pd.DataFrame({m: final_murni[m]["Proyeksi"] for m in ORDER}, index=fc_periods)
proj_detail = pd.concat({m: final[m] for m in ORDER}, names=["Metode", "Periode"]).reset_index()
proj_detail["Periode"] = proj_detail["Periode"].astype(str)

# ---- Level & qtq (mode level) ---------------------------------------------------------
proj_level = proj_qtq = cek_musiman = pd.DataFrame()
if MODE_LEVEL:
    proj_level = pd.DataFrame({m: level_dari_yoy(LVL, fc_periods, final[m]["Proyeksi"].values) for m in ORDER},
                              index=fc_periods)
    full_lvl = {m: pd.concat([LVL, proj_level[m]]) for m in ORDER}
    proj_qtq = pd.DataFrame({m: [(full_lvl[m][p] / full_lvl[m][p - 1] - 1) * 100 for p in fc_periods] for m in ORDER},
                            index=fc_periods)
    qtq_hist = (LVL / LVL.shift(1) - 1) * 100
    ref = qtq_hist[qtq_hist.index >= to_period(POLA_MUSIMAN_MULAI, "POLA_MUSIMAN_MULAI")].dropna()
    pola = ref.groupby(ref.index.quarter).agg(["mean", "min", "max"])
    rows = []
    for p in fc_periods:
        qn = p.quarter
        row = {"Periode": str(p), "Triwulan": f"Q{qn}",
               f"qtq historis rata2 ({POLA_MUSIMAN_MULAI}+)": pola.loc[qn, "mean"],
               "qtq historis min": pola.loc[qn, "min"], "qtq historis maks": pola.loc[qn, "max"]}
        for m in ORDER:
            v = proj_qtq.loc[p, m]
            row[m] = v
            row[f"Status {m}"] = ("Di bawah pola" if v < pola.loc[qn, "min"] - 0.05 else
                                  "Di atas pola" if v > pola.loc[qn, "max"] + 0.05 else "Sesuai pola")
        rows.append(row)
    cek_musiman = pd.DataFrame(rows)

# ---- Cek Q4 vs Q3 per tahun proyeksi (yoy; qtq juga bila mode level) --------------------
q4q3 = []
for yr in sorted({p.year for p in fc_periods}):
    p3, p4 = pd.Period(f"{yr}Q3", "Q"), pd.Period(f"{yr}Q4", "Q")
    if p3 in fc_periods and p4 in fc_periods:
        for m in ORDER:
            row = {"Tahun": yr, "Metode": m, "yoy Q3": proj_wide.loc[p3, m], "yoy Q4": proj_wide.loc[p4, m],
                   "Selisih yoy Q4 - Q3 (pp)": proj_wide.loc[p4, m] - proj_wide.loc[p3, m],
                   "Rata-rata historis (pp)": Q4Q3_RATA2,
                   "yoy Q4 > Q3": "Ya" if proj_wide.loc[p4, m] > proj_wide.loc[p3, m] else "Tidak"}
            if MODE_LEVEL:
                row.update({"qtq Q3": proj_qtq.loc[p3, m], "qtq Q4": proj_qtq.loc[p4, m],
                            "qtq Q4 > Q3": "Ya" if proj_qtq.loc[p4, m] > proj_qtq.loc[p3, m] else "Tidak"})
            q4q3.append(row)
q4q3 = pd.DataFrame(q4q3)

# ---- Cek jarak yoy antarkuartal proyeksi vs batas historis -------------------------------
jarak = pd.DataFrame(index=fc_periods)
for m in ORDER:
    s = pd.concat([pd.Series([y_all.iloc[-1]], index=[y_all.index[-1]]), proj_wide[m]])
    jarak[m] = s.diff().iloc[1:].values
jarak_ringkas = pd.DataFrame({
    "Maks |perubahan yoy| (pp)": jarak.abs().max(),
    "Rata-rata |perubahan yoy| (pp)": jarak.abs().mean(),
    "Titik dipangkas (proyeksi final)": pd.Series(dipangkas),
}).reindex(ORDER)
jarak_ringkas["Historis median (pp)"] = DY_NORMAL.abs().median()
jarak_ringkas[f"Historis persentil {KUANTIL_BATAS} (pp)"] = DY_NORMAL.abs().quantile(KUANTIL_BATAS / 100)

# aktual sesudah DATA_SAMPAI (hanya ada bila DATA_SAMPAI diisi, untuk uji coba)
y_after = df_full[TARGET].reindex(fc_periods).dropna()
evaluasi_aktual = pd.DataFrame()
if len(y_after):
    rows = []
    for m in ORDER:
        e = y_after - final[m]["Proyeksi"].reindex(y_after.index)
        rows.append({"Metode": m, "RMSE": rmse_fn(e.values), "MAE": e.abs().mean(), "ME (bias)": e.mean(),
                     **{str(p): final[m].loc[p, "Proyeksi"] for p in y_after.index}})
    evaluasi_aktual = pd.DataFrame(rows).sort_values("RMSE")
    evaluasi_aktual.loc[len(evaluasi_aktual)] = {"Metode": "AKTUAL", **{str(p): v for p, v in y_after.items()}}
    print(f"\nUJI COBA vs DATA AKTUAL {y_after.index[0]} s.d. {y_after.index[-1]}")
    print(evaluasi_aktual.round(3).to_string(index=False))

series_full = pd.DataFrame(index=y_all.index.append(fc_periods))
series_full["Aktual"] = df_full[TARGET].reindex(series_full.index)
for m in ORDER:
    series_full[m] = final[m]["Proyeksi"]
series_full.index = series_full.index.astype(str)

years = sorted({p.year for p in fc_periods} | {fc_periods[0].year - 1})
def annual(m):
    if MODE_LEVEL:   # pertumbuhan tahunan sebenarnya: jumlah PDRB 4 triwulan dibanding tahun sebelumnya
        s = full_lvl[m]
        tot = {yr: s[[p for p in s.index if p.year == yr]] for yr in set(years) | {min(years) - 1}}
        return {str(yr): (tot[yr].sum() / tot[yr - 1].sum() - 1) * 100 if len(tot[yr]) == 4 and len(tot[yr - 1]) == 4
                else np.nan for yr in years}
    s = pd.concat([y_all, final[m]["Proyeksi"]])
    return {str(yr): s[[p for p in s.index if p.year == yr]].mean() for yr in years}
tahunan = pd.DataFrame({m: annual(m) for m in ORDER}).T
tahunan.index.name = "Metode"

print(f"\nMetode terbaik (RMSE backtest): {BEST}")
print("\nPROYEKSI (% yoy)")
print(proj_wide.round(2).to_string())
if MODE_LEVEL:
    print("\nPROYEKSI (% qtq)")
    print(proj_qtq.round(2).to_string())
    print(f"\nCEK POLA MUSIMAN ({BEST}): qtq proyeksi vs rentang historis {POLA_MUSIMAN_MULAI} s.d. {LVL.index[-1]}")
    print(cek_musiman[["Periode", "Triwulan", f"qtq historis rata2 ({POLA_MUSIMAN_MULAI}+)", "qtq historis min",
                       "qtq historis maks", BEST, f"Status {BEST}"]].round(2).to_string(index=False))
if len(q4q3):
    print(f"\nCEK YOY Q4 vs Q3 (rata-rata historis tahun normal: {Q4Q3_RATA2:+.2f} pp)")
    print(q4q3[q4q3.Metode.isin(ORDER[:4])][["Tahun", "Metode", "yoy Q3", "yoy Q4", "Selisih yoy Q4 - Q3 (pp)"]]
          .round(2).to_string(index=False))
print("\nJARAK YOY ANTARKUARTAL PROYEKSI")
print(jarak_ringkas.round(2).to_string())
print("\nPERTUMBUHAN TAHUNAN (%)" + (" dari level PDRB" if MODE_LEVEL else " (rata-rata yoy triwulanan)"))
print(tahunan.round(2).to_string())

# =============================================================================
# 7. GRAFIK
# =============================================================================
plt.rcParams.update({"figure.dpi": 130, "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.alpha": .3})
C_ACT = "#1b2a2f"
PAL = ["#0f6b5c", "#c2410c", "#2563eb", "#9333ea", "#ca8a04", "#db2777", "#0891b2", "#65a30d", "#57534e",
       "#1e3a8a", "#b91c1c", "#0d9488", "#7c2d12", "#4d7c0f", "#a21caf", "#475569"]
COL = {m: PAL[i % len(PAL)] for i, m in enumerate(ORDER)}
xh, xf = y_all.index.to_timestamp(), fc_periods.to_timestamp()
g_start = (max(y_all.index[0], p_sampai - 19) if str(GRAFIK_MULAI).lower() == "otomatis"
           else to_period(GRAFIK_MULAI, "GRAFIK_MULAI"))
mask = y_all.index >= g_start
OUT = FOLDER_OUTPUT


def plot_actual_after(ax):
    if len(y_after):
        ax.plot(y_after.index.to_timestamp(), y_after.values, color=C_ACT, lw=1.5, ls=":", marker="o",
                ms=4, mfc="white", label="Aktual (tidak dipakai model)")


# 7.1 data historis
cols = [TARGET] + EXOG_ALL
nc = 3; nr = int(np.ceil(len(cols) / nc))
fig, axes = plt.subplots(nr, nc, figsize=(13, 2.8 * nr), sharex=True, squeeze=False)
for ax, c in zip(axes.ravel(), cols):
    ax.plot(df_raw.index.to_timestamp(), df_raw[c], color=C_ACT if c == TARGET else "#6b7280", lw=1.6, label="asli")
    if c != TARGET and BERSIHKAN_OUTLIER and not df_raw[c].equals(df[c]):
        ax.plot(df.index.to_timestamp(), df[c], color="#0f6b5c", lw=1, ls="--", label="setelah dibersihkan")
        ax.legend(fontsize=7, loc="upper left")
    ax.axhline(0, color="k", lw=.6)
    ax.set_title(f"{LABEL[c]} [{c}]", fontsize=9, fontweight="bold" if c == TARGET else "normal")
for ax in axes.ravel()[len(cols):]:
    ax.axis("off")
fig.suptitle("Data historis (% yoy)", fontsize=12, fontweight="bold")
fig.tight_layout(); fig.savefig(f"{OUT}/01_data_historis.png"); plt.close(fig)

# 7.2 semua metode
fig, ax = plt.subplots(figsize=(12, 5.5))
ax.plot(xh[mask], y_all[mask], color=C_ACT, lw=2.4, label="Aktual", marker="o", ms=3)
plot_actual_after(ax)
for m in ORDER:
    if m in BENCHMARK and not TAMPILKAN_BENCHMARK:
        continue
    ax.plot(np.r_[xh[-1:], xf], np.r_[y_all.iloc[-1], final[m]["Proyeksi"].values], color=COL[m],
            lw=2.6 if m == BEST else 1.3, ls="-" if m == BEST else "--",
            label=f"{m}{' (terbaik)' if m == BEST else ''}", alpha=1 if m == BEST else .85)
ax.axvline(xh[-1], color="grey", ls=":", lw=1)
ax.text(xh[-1], ax.get_ylim()[1], "  proyeksi →", va="top", fontsize=8, color="grey")
ax.set_title(f"Proyeksi {LABEL[TARGET]}: semua metode", fontsize=12, fontweight="bold")
ax.set_ylabel("% yoy"); ax.legend(ncol=2, fontsize=8, frameon=False, loc="best")
fig.tight_layout(); fig.savefig(f"{OUT}/02_proyeksi_semua_metode.png"); plt.close(fig)

# 7.3 fan chart dua metode teratas
top2 = ORDER[:2]
fig, axes = plt.subplots(1, len(top2), figsize=(6.5 * len(top2), 4.6), sharey=True, squeeze=False)
for ax, m in zip(axes.ravel(), top2):
    f = final[m]
    ax.plot(xh[mask], y_all[mask], color=C_ACT, lw=2, marker="o", ms=3, label="Aktual")
    plot_actual_after(ax)
    ax.fill_between(np.r_[xh[-1:], xf], np.r_[y_all.iloc[-1], f["Lower"]], np.r_[y_all.iloc[-1], f["Upper"]],
                    color=COL[m], alpha=.18, label=f"Selang {SELANG_KEPERCAYAAN}%")
    ax.plot(np.r_[xh[-1:], xf], np.r_[y_all.iloc[-1], f["Proyeksi"]], color=COL[m], lw=2.4, marker="o", ms=4, label=m)
    for i, (x, v) in enumerate(zip(xf, f["Proyeksi"])):
        ax.annotate(f"{v:.2f}", (x, v), textcoords="offset points", xytext=(0, 8 if i % 2 == 0 else -13),
                    ha="center", fontsize=7.5, color=COL[m])
    ax.set_title(f"{m} (peringkat {ORDER.index(m) + 1})", fontweight="bold")
    ax.legend(fontsize=8, frameon=False, loc="lower left")
axes[0, 0].set_ylabel("% yoy")
fig.suptitle("Proyeksi dengan selang kepercayaan", fontsize=12, fontweight="bold")
fig.tight_layout(); fig.savefig(f"{OUT}/03_fan_chart.png"); plt.close(fig)

# 7.4 metrik
fig, axes = plt.subplots(1, 3, figsize=(14, 0.45 * len(ORDER) + 2.2))
for ax, col in zip(axes, ["RMSE", "MAE", "Theil's U"]):
    d = metrik.sort_values(col, ascending=False)
    bars = ax.barh(d["Metode"], d[col], color=[COL[m] for m in d["Metode"]])
    ax.bar_label(bars, fmt="%.2f", fontsize=7.5, padding=2)
    if col == "Theil's U":
        ax.axvline(1, color="red", ls="--", lw=1)
    ax.set_title(col + (" (garis merah = naive)" if col == "Theil's U" else ""), fontweight="bold")
    ax.grid(axis="y", visible=False)
fig.suptitle(f"Akurasi backtest ({JUMLAH_UJI_BACKTEST} uji, horizon 1 s.d. {H})", fontsize=12, fontweight="bold")
fig.tight_layout(); fig.savefig(f"{OUT}/04_perbandingan_error.png"); plt.close(fig)

# 7.5 RMSE per horizon
fig, ax = plt.subplots(figsize=(10, 4.8))
for m in ORDER:
    ax.plot(range(1, rmse_h.shape[1] + 1), rmse_h.loc[m].values, marker="o", color=COL[m],
            lw=2.4 if m == BEST else 1.2, label=m)
ax.set_xlabel("Horizon (triwulan ke depan)"); ax.set_ylabel("RMSE (pp)")
ax.set_title("RMSE menurut horizon proyeksi", fontsize=12, fontweight="bold")
ax.legend(ncol=2, fontsize=8, frameon=False)
fig.tight_layout(); fig.savefig(f"{OUT}/05_rmse_per_horizon.png"); plt.close(fig)

# 7.6 backtest h=1
nc = 5; nr = int(np.ceil(len(ORDER) / nc))
fig, axes = plt.subplots(nr, nc, figsize=(16, 3.3 * nr), sharex=True, sharey=True, squeeze=False)
for ax, m in zip(axes.ravel(), ORDER):
    g = bt[(bt.Metode == m) & (bt.h == 1)]
    x = pd.PeriodIndex(g["Periode"], freq="Q").to_timestamp()
    ax.plot(x, g["Aktual"], color=C_ACT, lw=1.8, marker="o", ms=3, label="Aktual")
    ax.plot(x, g["Prediksi"], color=COL[m], lw=1.6, marker="s", ms=3, ls="--", label="Prediksi h=1")
    r = metrik.set_index("Metode").loc[m]
    ax.set_title(f"{m}\nRMSE {r['RMSE']:.2f} · MAE {r['MAE']:.2f}", fontsize=8.5)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
axes[0, 0].legend(fontsize=7, frameon=False)
for ax in axes.ravel()[len(ORDER):]:
    ax.axis("off")
fig.suptitle("Backtest 1 triwulan ke depan: aktual vs prediksi", fontsize=12, fontweight="bold")
fig.tight_layout(); fig.savefig(f"{OUT}/06_backtest_h1.png"); plt.close(fig)

# 7.7 pola musiman qtq (mode level)
n_grafik = 6
if MODE_LEVEL:
    n_grafik = 7
    top3 = [m for m in ORDER if m not in BENCHMARK][:3]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4.8), gridspec_kw={"width_ratios": [1.6, 1]})
    qh = qtq_hist[qtq_hist.index >= g_start]
    ax1.plot(qh.index.to_timestamp(), qh.values, color=C_ACT, lw=2, marker="o", ms=3, label="Aktual")
    for m in top3:
        ax1.plot(np.r_[qh.index[-1:].to_timestamp(), xf], np.r_[qh.iloc[-1], proj_qtq[m].values], color=COL[m],
                 lw=2.2 if m == top3[0] else 1.3, ls="-" if m == top3[0] else "--", marker="o", ms=3, label=m)
    for p in qh.index.append(fc_periods):
        if p.quarter == 4:
            ax1.axvspan(p.to_timestamp(), (p + 1).to_timestamp(), color="#ca8a04", alpha=.08, lw=0)
    ax1.axvline(xh[-1], color="grey", ls=":", lw=1)
    ax1.set_title("Pertumbuhan qtq (arsiran = Q4)", fontweight="bold"); ax1.set_ylabel("% qtq")
    ax1.legend(fontsize=8, frameon=False, ncol=2)
    qx = np.arange(1, 5)
    ax2.bar(qx, pola["mean"], color="#cbd5d1", width=.55, label=f"Rata-rata {POLA_MUSIMAN_MULAI}+")
    ax2.errorbar(qx, pola["mean"], yerr=[pola["mean"] - pola["min"], pola["max"] - pola["mean"]], fmt="none",
                 ecolor="#6b7280", capsize=4, lw=1, label="Rentang historis")
    yrs = sorted({p.year for p in fc_periods})
    for i, yr in enumerate(yrs):
        ps = [p for p in fc_periods if p.year == yr]
        ax2.scatter([p.quarter + (i - (len(yrs) - 1) / 2) * 0.18 for p in ps], [proj_qtq.loc[p, top3[0]] for p in ps],
                    color=COL[top3[0]], marker=["o", "s", "D", "^"][i % 4], s=38, zorder=3,
                    label=f"{top3[0]} {yr}")
    ax2.set_xticks(qx); ax2.set_xticklabels(["Q1", "Q2", "Q3", "Q4"])
    ax2.set_title("Pola musiman: historis vs proyeksi", fontweight="bold"); ax2.set_ylabel("% qtq")
    ax2.legend(fontsize=7.5, frameon=False)
    fig.suptitle(f"Cek pola musiman {TARGET_LEVEL} (qtq)", fontsize=12, fontweight="bold")
    fig.tight_layout(); fig.savefig(f"{OUT}/07_pola_musiman_qtq.png"); plt.close(fig)

# =============================================================================
# 8. EKSPOR EXCEL
# =============================================================================
penjelasan = {
    "Naive": "Benchmark. Proyeksi = pertumbuhan yoy terakhir yang diulang. Garis datar memang definisinya.",
    "Rata-rata 8Q": f"Benchmark. Proyeksi = rata-rata {RATA2_JUMLAH_TRIWULAN} triwulan terakhir. Garis datar memang definisinya.",
    "ARIMA": "Hanya memakai pola target sendiri (+ dummy pandemi; opsional variabel kalender/dummy triwulan). Proyeksi cepat kembali ke rata-rata jangka panjang.",
    "ETS": "Exponential smoothing pada yoy. Tanpa tren yang jelas di data, hasilnya mendekati datar di level terakhir.",
    "Theta": "Garis tren jangka panjang digabung exponential smoothing. Sederhana, sering sulit dikalahkan untuk data pendek.",
    "ARIMAX": "ARIMA + indikator pendukung. Indikator dipilih dari korelasi di luar masa pandemi, lalu diproyeksi dengan AR(1) + dummy pandemi sehingga kembali ke rata-rata periode normal. Proyeksi bergerak landai menuju rata-rata jangka panjang.",
    "VAR": "Target dan indikator saling memengaruhi. Indikator dipilih otomatis dari korelasi di luar masa pandemi (atau sesuai VAR_INDIKATOR). Proyeksi bergerak landai menuju keseimbangan.",
    "BVAR": "VAR Bayesian (prior Minnesota). Koefisien ditarik ke nilai wajar sehingga tidak meledak walau data pendek.",
    "Ridge": "Regresi linier memakai indikator h triwulan sebelumnya + variabel kalender periode sasaran.",
    "Elastic Net": "Regresi seperti Ridge, tetapi indikator yang lemah otomatis diberi koefisien nol (seleksi indikator).",
    "Faktor (PCA)": "Semua indikator diringkas menjadi beberapa faktor bersama (PCA), lalu faktor dipakai memproyeksi target. Cocok bila indikator banyak tapi data pendek.",
    "Random Forest": "Machine learning berbasis pohon keputusan. Hasil bisa naik turun mengikuti pola indikator.",
    "Gradient Boosting": "Machine learning berbasis pohon keputusan bertahap. Hasil bisa naik turun mengikuti pola indikator.",
    "SARIMA Musiman": "Memodelkan log PDRB ADHK level dengan komponen musiman triwulanan"
                      + (f" + porsi hari {', '.join(_kal_aktif)} per triwulan" if PAKAI_EFEK_KALENDER and _kal_aktif else "")
                      + ". Efek Nataru/HBKN (selalu di Q4) tertangkap komponen musiman Q4. Yoy dan qtq diturunkan dari level.",
    "ETS Musiman": "Holt-Winters pada log PDRB ADHK level (tren damped + musiman). Pola musiman diperbarui bertahap mengikuti data terbaru. Yoy dan qtq diturunkan dari level.",
    "Ensemble": {"inverse-rmse": "Gabungan semua metode non-benchmark, bobot lebih besar untuk error backtest lebih kecil.",
                 "top": f"Gabungan {ENSEMBLE_TOP} metode non-benchmark terbaik, bobot sesuai error backtest.",
                 "median": "Nilai tengah semua metode non-benchmark."}[ENSEMBLE_CARA],
}
catatan = pd.DataFrame([{"Metode": m, "Peringkat": ORDER.index(m) + 1, "Spesifikasi terpilih": spesifikasi.get(m, ""),
                         "Penjelasan": penjelasan.get(m, "")} for m in ORDER])

pengaturan = pd.DataFrame({"Pengaturan": [
    "FILE_DATA", "SHEET_DATA", "TARGET", "Mode", "Sumber yoy target", "DATA_MULAI", "DATA_SAMPAI", "PROYEKSI_SAMPAI", "INDIKATOR_DIPAKAI",
    "METODE aktif", "PAKAI_ENSEMBLE", "ENSEMBLE_CARA", "ETS_TREN", "ARIMAX_JUMLAH_INDIKATOR", "ARIMAX_KORELASI_MIN",
    "ARIMAX_PILIH_TANPA_PANDEMI", "ARIMAX_PROYEKSI_INDIKATOR", "VAR_INDIKATOR", "VAR/BVAR (variabel)", "BVAR_LAG / BVAR_KETATAN",
    "FAKTOR_JUMLAH", "Batas perubahan yoy antarkuartal",
    "PAKAI_DUMMY_PANDEMI", "Triwulan krisis (dummy)", "Deteksi krisis", "PAKAI_EFEK_KALENDER", "KALENDER_DI_MODEL_YOY",
    "EFEK_TRIWULAN_YOY",
    "Jendela Lebaran", "Ramadan / Idul Fitri / Idul Adha", "Jendela Idul Adha", "JUMLAH_UJI_BACKTEST", "SELANG_KEPERCAYAAN", "PENYESUAIAN (pp yoy)",
    "BERSIHKAN_OUTLIER", "BATAS_OUTLIER", "Metode terbaik (RMSE)", "Pertumbuhan tahunan",
    "Metode dilewati", "Penyesuaian otomatis", "POLA_MUSIMAN_MULAI"],
    "Nilai": [FILE_DATA, SHEET_DATA, f"{TARGET} ({LABEL[TARGET]})",
              f"Level ({TARGET_LEVEL})" if MODE_LEVEL else "Yoy", SUMBER_YOY, str(df_raw.index[0]), str(df_raw.index[-1]),
              str(p_proj), ", ".join(EXOG_ALL), ", ".join(aktif), str(USE_ENS), ENSEMBLE_CARA, ETS_TREN,
              ARIMAX_JUMLAH_INDIKATOR, ARIMAX_KORELASI_MIN, str(ARIMAX_PILIH_TANPA_PANDEMI), ARIMAX_PROYEKSI_INDIKATOR,
              "otomatis" if VAR_INDIKATOR == "otomatis" else ", ".join(VAR_INDIKATOR),
              ", ".join(VAR_VARS), f"{BVAR_LAG} / {BVAR_KETATAN}", FAKTOR_JUMLAH,
              "tidak ada" if BATAS_YOY is None else f"{BATAS_YOY:.2f} pp ({BATAS_PERUBAHAN_YOY})", str(PAKAI_DUMMY_PANDEMI), ringkas_periode(KRISIS),
              INFO_KRISIS, str(PAKAI_EFEK_KALENDER), str(KALENDER_DI_MODEL_YOY),
              str(EFEK_TRIWULAN_YOY),
              f"Ramadan {RAMADAN_HARI} hari; Lebaran H-{LEBARAN_HARI_SEBELUM} s.d. H+{LEBARAN_HARI_SESUDAH}",
              f"{PAKAI_RAMADAN} / {PAKAI_IDUL_FITRI} / {PAKAI_IDUL_ADHA}",
              f"H-{IDUL_ADHA_HARI_SEBELUM} s.d. H+{IDUL_ADHA_HARI_SESUDAH}",
              JUMLAH_UJI_BACKTEST, f"{SELANG_KEPERCAYAAN}%",
              ", ".join(f"{k}: {v:+.2f}" for k, v in PENYESUAIAN.items()) or "-",
              str(BERSIHKAN_OUTLIER), BATAS_OUTLIER, BEST,
              "Dari jumlah level PDRB 4 triwulan" if MODE_LEVEL else "Rata-rata yoy triwulanan (pendekatan)",
              "; ".join(f"{m_} ({a_})" for m_, a_ in alasan_lewat.items()) or "-",
              "; ".join(CATATAN_AUTO + PERINGATAN_DATA) or "-", POLA_MUSIMAN_MULAI if MODE_LEVEL else "-"]})

_tambah = [
    ("OUTLIER_MANUAL", "-" if OUTLIER_MANUAL is None else (", ".join(f"{k}: {', '.join(map(str, v))}" for k, v in OUTLIER_MANUAL.items() if v) or "tidak ada")),
    ("OUTLIER_CARA", OUTLIER_CARA),
    ("ARIMA_MAX_PQ / ARIMAX_MAX_PQ / VAR_MAXLAG", f"{ARIMA_MAX_PQ} / {ARIMAX_MAX_PQ} / {VAR_MAXLAG}"),
    ("RF (pohon / kedalaman / min daun)", f"{RF_POHON} / {RF_KEDALAMAN} / {RF_MIN_DAUN}"),
    ("GB (pohon / learning rate / kedalaman)", f"{GB_POHON} / {GB_LEARNING_RATE} / {GB_KEDALAMAN}"),
    ("RATA2_JUMLAH_TRIWULAN", RATA2_JUMLAH_TRIWULAN),
    ("ENSEMBLE_SARING / BATAS_RMSE", f"{ENSEMBLE_SARING} / {ENSEMBLE_BATAS_RMSE}"),
]
pengaturan = pd.concat([pengaturan, pd.DataFrame(_tambah, columns=["Pengaturan", "Nilai"])], ignore_index=True)
pengaturan["Nilai"] = pengaturan["Nilai"].astype(str)
kalender_out = pd.concat([KAL_LVL, KAL_YOY], axis=1).reindex(ALL_IDX) if PAKAI_EFEK_KALENDER else pd.DataFrame()
sheets = {
    "Pengaturan": (pengaturan, False),
    "Penjelasan_Metode": (catatan, False),
    "Series_Aktual_Proyeksi": (series_full.round(3), True),
    "Proyeksi_yoy": (proj_wide.set_axis(proj_wide.index.astype(str)).round(3), True),
}
if MODE_LEVEL:
    sheets["Proyeksi_qtq"] = (proj_qtq.set_axis(proj_qtq.index.astype(str)).round(3), True)
    sheets["Proyeksi_Level"] = (proj_level.set_axis(proj_level.index.astype(str)).round(0), True)
    sheets["Cek_Pola_Musiman"] = (cek_musiman.round(3), False)
if len(q4q3):
    sheets["Cek_Q4_vs_Q3"] = (q4q3.round(3), False)
sheets["Pola_yoy_Historis"] = (pola_yoy_hist.round(3), True)
sheets["Cek_Jarak_yoy"] = (pd.concat([jarak.set_axis(jarak.index.astype(str)).T.add_prefix("Perubahan ").round(3),
                                      jarak_ringkas.round(3)], axis=1), True)
sheets.update({
    "Proyeksi_dengan_CI": (proj_detail.round(3), False),
    "Pertumbuhan_Tahunan": (tahunan.round(3), True),
    "Penyesuaian": (pd.DataFrame(adj_log if adj_log else [{"Periode": "-", "Penyesuaian (pp yoy)": 0.0}]), False),
    "Proyeksi_yoy_Model_Murni": (proj_murni.set_axis(proj_murni.index.astype(str)).round(3), True),
    "Metrik_Error_Backtest": (metrik.round(4), False),
    "RMSE_per_Horizon": (rmse_h.round(4), True),
    "Peringkat_per_Horizon": (peringkat_h, True),
    "Detail_Backtest": (bt.drop(columns="Error naive").round(4), False),
    "Diagnostik_InSample": (diagnostik.round(4), False),
    "Validasi_Data": (validasi.round(4), False),
    "Log_Pembersihan": (pd.DataFrame(winsor_log if winsor_log else [{"Kode": "-", "Nilai dipangkas": 0}]).round(3), False),
    "Data_Asli": (df_raw.set_axis(df_raw.index.astype(str)), True),
})
if PAKAI_EFEK_KALENDER:
    sheets["Variabel_Kalender"] = (kalender_out.set_axis(kalender_out.index.astype(str)).round(4), True)
if USE_ENS:
    sheets["Bobot_Ensemble"] = (W.rename("Bobot").round(4).to_frame(), True)
if len(evaluasi_aktual):
    sheets["Uji_vs_Aktual"] = (evaluasi_aktual.round(3), False)

xlsx = f"{OUT}/{NAMA_FILE_EXCEL}"
with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
    for nama, (data, idx) in sheets.items():
        data.to_excel(w, sheet_name=nama, index=idx)
    for ws in w.book.worksheets:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(max(len(str(c.value or "")) for c in col) + 2, 60)
        ws.freeze_panes = "B2"

print(f"\nSelesai. Hasil tersimpan di folder '{OUT}/' ({NAMA_FILE_EXCEL} + {n_grafik} grafik PNG)")
