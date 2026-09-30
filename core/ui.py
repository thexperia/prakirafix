"""Tampilan bersama: gaya, glosarium untuk tooltip, grafik, format angka."""
import io
import json
import zipfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

TEAL, INK, CORAL, CREAM, SAND, MUTED = "#0F6B5C", "#1C2B33", "#B83C0A", "#FBF6EC", "#F1E6D2", "#56636B"

GLOSARIUM = json.loads((Path(__file__).parent / "glosarium.json").read_text(encoding="utf-8"))
_FLAT = {k: v for grp in GLOSARIUM.values() for k, v in grp.items()}


def g(term):
    """Teks penjelasan istilah untuk parameter help= (tooltip ⓘ)."""
    return _FLAT.get(term, "")


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rubik:wght@500;700&family=Nunito+Sans:wght@400;600;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, p, li, label { font-family: 'Nunito Sans', sans-serif; }
h1, h2, h3, h4 { font-family: 'Rubik', sans-serif !important; color: #1C2B33; }
[data-testid="stSidebar"] { background: #16303A; }
[data-testid="stSidebar"] * { color: #F5F1E8; }
[data-testid="stSidebar"] button, [data-testid="stSidebar"] button * { color: #16303A !important; }
[data-testid="stSidebar"] a[aria-current="page"] { background: #1F4450; border-radius: 8px; }
.eyebrow { font-size: 13px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; color: #B83C0A; margin-bottom: -6px; }
.kpi { background: #FFFDF8; border: 1px solid #E6DDCB; border-radius: 14px; padding: 14px 18px; }
.kpi .l { font-size: 13px; font-weight: 700; color: #56636B; }
.kpi .v { font-family: 'Rubik', sans-serif; font-size: 28px; font-weight: 700; color: #1C2B33; }
.kpi .s { font-size: 13px; color: #56636B; }
.chip { display: inline-block; padding: 3px 10px; margin: 2px 4px 2px 0; border-radius: 999px; background: #F1E6D2; font-size: 13px; font-weight: 700; color: #1C2B33; }
.msg-err { background: #FDECEA; border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; }
.msg-warn { background: #FFF4DB; border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; }
.msg-err b { color: #B42318; } .msg-warn b { color: #8A5A00; }
</style>
"""


def style():
    st.markdown(CSS, unsafe_allow_html=True)


def header(eyebrow, title, caption=None):
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.title(title)
    if caption:
        st.caption(caption)


def kpi(col, label, value, sub="", tip=""):
    t = f' <span title="{tip}" style="cursor:help;color:{TEAL}">ⓘ</span>' if tip else ""
    col.markdown(f'<div class="kpi"><div class="l">{label}{t}</div><div class="v">{value}</div><div class="s">{sub}</div></div>',
                 unsafe_allow_html=True)


def fmt(x, d=2, pct=False):
    if x is None:
        return "-"
    try:
        s = f"{float(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s + ("%" if pct else "")
    except Exception:
        return str(x)


def chips(items):
    st.markdown("".join(f'<span class="chip">{i}</span>' for i in items), unsafe_allow_html=True)


def chart_proyeksi(summary, height=320):
    hist = pd.DataFrame(summary.get("historis", []))
    proj = pd.DataFrame(summary.get("proyeksi", []))
    if hist.empty or proj.empty:
        return None
    hist["t"] = pd.PeriodIndex(hist["periode"], freq="Q").to_timestamp()
    proj["t"] = pd.PeriodIndex(proj["periode"], freq="Q").to_timestamp()
    last = hist.iloc[[-1]].assign(lower=hist["yoy"].iloc[-1], upper=hist["yoy"].iloc[-1])
    band = pd.concat([last[["t", "lower", "upper"]], proj[["t", "lower", "upper"]]])
    line_p = pd.concat([last[["t", "periode", "yoy"]], proj[["t", "periode", "yoy"]]])
    lo = min(hist["yoy"].min(), proj["lower"].min()) - 0.3
    hi = max(hist["yoy"].max(), proj["upper"].max()) + 0.3
    y = alt.Scale(domain=[lo, hi])
    xax = alt.X("t:T", title=None, axis=alt.Axis(format="%Y", tickCount="year", labelAngle=0))
    a = alt.Chart(band).mark_area(color=TEAL, opacity=0.15).encode(x=xax, y=alt.Y("lower:Q", scale=y, title="% yoy"), y2="upper:Q")
    b = alt.Chart(hist).mark_line(color=INK, point=alt.OverlayMarkDef(color=INK, size=40), strokeWidth=2.5).encode(
        x=xax, y=alt.Y("yoy:Q", scale=y), tooltip=[alt.Tooltip("periode:N", title="Periode"), alt.Tooltip("yoy:Q", title="Aktual (%)", format=".2f")])
    c = alt.Chart(line_p).mark_line(color=TEAL, point=alt.OverlayMarkDef(color=TEAL, size=50), strokeWidth=3).encode(
        x=xax, y=alt.Y("yoy:Q", scale=y), tooltip=[alt.Tooltip("periode:N", title="Periode"), alt.Tooltip("yoy:Q", title="Proyeksi (%)", format=".2f")])
    return (a + b + c).properties(height=height)


def read_excel_sheets(excel_bytes):
    x = pd.ExcelFile(io.BytesIO(excel_bytes))
    return {s: pd.read_excel(x, sheet_name=s) for s in x.sheet_names}


def read_charts(zip_bytes):
    out = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for n in sorted(z.namelist()):
            out[n] = z.read(n)
    return out


METRIK_HELP = {
    "RMSE": g("RMSE"), "MAE": g("MAE"), "ME (bias)": g("ME (bias)"), "sMAPE (%)": g("sMAPE"), "MASE": g("MASE"),
    "Theil's U": g("Theil's U"), "Akurasi arah (%)": g("Akurasi arah"), "DM p-value": g("Uji Diebold-Mariano (DM)"),
    "RMSE qtq": "RMSE pertumbuhan antartriwulan (mode level). Lower better.", "R2": g("R2"), "AIC": g("AIC / BIC"),
    "BIC": g("AIC / BIC"), "Ljung-Box p": g("Ljung-Box"), "Jarque-Bera p": g("Jarque-Bera"), "ADF p-value": g("ADF / stasioner"),
}


def df_with_help(df, extra_help=None, **kw):
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            conv = pd.to_numeric(df[c], errors="coerce")
            if conv.notna().sum() and conv.notna().sum() == df[c].notna().sum():
                df[c] = conv
            else:
                df[c] = df[c].map(lambda v: "" if pd.isna(v) else str(v))
        if pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].round(3)
    helpmap = dict(METRIK_HELP)
    helpmap.update(extra_help or {})
    cfg = {}
    for c in df.columns:
        key = next((k for k in helpmap if str(c).startswith(k)), None)
        if key and helpmap[key]:
            cfg[c] = st.column_config.Column(help=helpmap[key])
        elif str(c).startswith("Coverage CI"):
            cfg[c] = st.column_config.Column(help=g("Coverage CI"))
    st.dataframe(df, column_config=cfg, hide_index=True, use_container_width=True, **kw)


def chart_bobot(bobot):
    d = pd.DataFrame({"Metode": list(bobot), "Bobot": [v * 100 for v in bobot.values()]})
    return alt.Chart(d).mark_bar(color=TEAL, cornerRadiusEnd=4).encode(
        x=alt.X("Bobot:Q", title="Bobot (%)"), y=alt.Y("Metode:N", sort="-x", title=None, axis=alt.Axis(labelLimit=200)),
        tooltip=["Metode", alt.Tooltip("Bobot:Q", format=".1f")]).properties(height=24 * len(d) + 30)
