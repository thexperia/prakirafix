"""Membuat file template Excel untuk diunduh pengguna."""
import io

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side

HEAD = PatternFill("solid", fgColor="16303A")
CODE = PatternFill("solid", fgColor="DCEFE9")
INPUT = PatternFill("solid", fgColor="FFF7E0")
WHITE = Font(name="Arial", bold=True, color="FFFFFF", size=10)
BOLD = Font(name="Arial", bold=True, size=10)
NORM = Font(name="Arial", size=10)
THIN = Border(bottom=Side(style="thin", color="E6DDCB"))

KOLOM_CONTOH = [
    ("PDRB (%)", "GPDRB", "Target: pertumbuhan PDRB, % yoy"),
    ("PDRB ADHK (Rp juta, level)", "PDRB_ADHK", "Opsional. Level PDRB harga konstan, untuk pola musiman"),
    ("PDB Nasional (%)", "GPDB", "Indikator pendukung, % yoy"),
    ("Indikator 1 (%)", "IND_1", "Ganti nama dan kode sesuai indikator Anda"),
    ("Indikator 2 (%)", "IND_2", "Ganti nama dan kode sesuai indikator Anda"),
]


def _sheet_data(ws, tahun_awal=2016, tahun_akhir=2026, isi=None):
    ws["A1"], ws["B1"] = "Tahun", "Triwulan"
    ws["A2"], ws["B2"] = "(kode)", "(kode)"
    for c in ("A1", "B1"):
        ws[c].font, ws[c].fill = WHITE, HEAD
    for c in ("A2", "B2"):
        ws[c].font, ws[c].fill = BOLD, CODE
    for j, (nama, kode, ket) in enumerate(KOLOM_CONTOH, start=3):
        a = ws.cell(1, j, nama); a.font, a.fill = WHITE, HEAD; a.alignment = Alignment(wrap_text=True)
        a.comment = Comment(ket, "Template")
        b = ws.cell(2, j, kode); b.font, b.fill = BOLD, CODE
        ws.column_dimensions[a.column_letter].width = 18
    r = 3
    for t in range(tahun_awal, tahun_akhir + 1):
        for q in range(1, 5):
            if q == 1:
                ws.cell(r, 1, t)
            ws.cell(r, 2, f"Q{q}")
            for j in range(3, 3 + len(KOLOM_CONTOH)):
                c = ws.cell(r, j)
                if isi and (t, q) in isi:
                    c.value = isi[(t, q)][j - 3]
                c.fill = INPUT if not isi else PatternFill()
                c.font = NORM
                c.border = THIN
            r += 1
    ws.column_dimensions["A"].width = 9
    ws.column_dimensions["B"].width = 10
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "C3"


def buat_template():
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    _sheet_data(ws)

    p = wb.create_sheet("Petunjuk")
    baris = [
        ("PETUNJUK PENGISIAN TEMPLATE", True),
        ("", False),
        ("1. Isi data di sheet \"Data\". Sheet ini yang dibaca aplikasi.", False),
        ("2. Baris 1: nama indikator (bebas). Baris 2: kode singkat tanpa spasi, diawali huruf (contoh: GPDRB, G_SEMEN).", False),
        ("3. Kolom A: tahun (cukup diisi di baris Q1). Kolom B: triwulan Q1, Q2, Q3, atau Q4. Periode harus berurutan.", False),
        ("4. Indikator mulai kolom C. Boleh menambah atau menghapus kolom indikator.", False),
        ("5. Isi pertumbuhan dalam % yoy (contoh: 5,12 berarti tumbuh 5,12%).", False),
        ("6. Kolom level PDRB (Rp juta) opsional. Bila diisi, aplikasi bisa memakai mode level (pola musiman Lebaran dan akhir tahun).", False),
        ("7. Sel yang belum ada datanya dibiarkan KOSONG, jangan diisi 0 atau tanda \"-\".", False),
        ("8. Disarankan minimal 30 triwulan (mis. mulai 2016Q1). Data lebih pendek tetap bisa diproses, dengan peringatan.", False),
        ("9. Baris untuk periode yang belum terjadi boleh dibiarkan kosong.", False),
        ("", False),
        ("Sheet \"Contoh\" berisi contoh pengisian dengan angka ilustrasi (bukan data resmi).", False),
    ]
    for i, (t, b) in enumerate(baris, start=1):
        c = p.cell(i, 1, t)
        c.font = Font(name="Arial", bold=b, size=12 if b else 10)
    p.column_dimensions["A"].width = 120

    c = wb.create_sheet("Contoh")
    ilustrasi = {}
    lvl = 30000000.0
    vals = [(5.10, 5.00, 3.2, 1.5), (5.25, 5.05, -1.1, 2.4), (5.05, 4.95, 4.0, 0.8), (5.30, 5.10, 2.2, 3.1)]
    for t in range(2024, 2026):
        for q in range(1, 5):
            g, pdb, i1, i2 = vals[q - 1]
            g += (t - 2024) * 0.2
            lvl *= 1.012 if q != 4 else 1.03
            ilustrasi[(t, q)] = (round(g, 2), round(lvl, 0), pdb, i1, i2)
    _sheet_data(c, 2024, 2025, ilustrasi)
    c.cell(12, 1, "Angka di sheet ini hanya ilustrasi format, bukan data resmi.").font = Font(name="Arial", italic=True, size=9)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
