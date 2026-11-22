"""
Menghitung ulang Table 3 artikel (kesepakatan penilaian pertama yang independen, N = 44) dari
legal_alignment/skor_per_butir.csv, tanpa data mentah dan tanpa identitas penilai (2026-11-12; RENCANA_REVISI K7).

Ukuran: tabel kontingensi gabungan a/b/c/d, p_o, p_e, Cohen's kappa, ambang 0,70, p_pos, p_neg, Gwet's AC1,
PABAK, PI, BI. Rincian per kelompok hanya berupa tabel silang dan jumlah setuju/tidak setuju; kappa per kelompok
TIDAK dihitung, sesuai aturan pelaporan yang ditetapkan sebelum penilaian (CHANGELOG Tahap 11a §2).
Fungsi metrics() disalin tanpa perubahan dari PERBAIKAN/instrumen_kappa/hitung_kappa.py.

Bila skrip dijalankan di proyek asli, hasilnya dicocokkan dengan PERBAIKAN/instrumen_kappa/hasil/kappa_ringkasan.json
(keluar dengan kode 1 bila berbeda). Di repositori publik berkas itu tidak ada, dan pencocokan dilewati.

Jalankan: python hitung_tabel3.py
"""

import csv
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
if os.name == "nt" and not HERE.startswith("\\\\?\\"):  # path proyek mendekati MAX_PATH (260)
    HERE = "\\\\?\\" + HERE
SKOR = os.path.join(HERE, "legal_alignment", "skor_per_butir.csv")
RINGKASAN = os.path.join(os.path.dirname(os.path.dirname(HERE)), "PERBAIKAN", "instrumen_kappa", "hasil", "kappa_ringkasan.json")
AMBANG = 0.70


def metrics(a, b, c, d):
    n = a + b + c + d
    po = (a + d) / n
    r1_1, r2_1 = (a + b) / n, (a + c) / n
    pe = r1_1 * r2_1 + (1 - r1_1) * (1 - r2_1)
    kappa = None if abs(1 - pe) < 1e-12 else (po - pe) / (1 - pe)
    pi = (r1_1 + r2_1) / 2  # rerata proporsi kategori 1 (Gwet, dua kategori)
    pe_ac1 = 2 * pi * (1 - pi)
    ac1 = (po - pe_ac1) / (1 - pe_ac1)
    p_pos = None if (2 * a + b + c) == 0 else 2 * a / (2 * a + b + c)
    p_neg = None if (2 * d + b + c) == 0 else 2 * d / (2 * d + b + c)
    return {"N": n, "a": a, "b": b, "c": c, "d": d, "p_o": po, "p_e": pe, "kappa": kappa,
            "kappa_memenuhi_ambang": None if kappa is None else kappa >= AMBANG,
            "p_pos": p_pos, "p_neg": p_neg, "AC1": ac1, "p_e_AC1": pe_ac1, "PABAK": 2 * po - 1,
            "PI": (a - d) / n, "BI": (b - c) / n}


def silang(rows):
    a = sum(r["s1"] == 1 and r["s2"] == 1 for r in rows)
    b = sum(r["s1"] == 1 and r["s2"] == 0 for r in rows)
    c = sum(r["s1"] == 0 and r["s2"] == 1 for r in rows)
    d = sum(r["s1"] == 0 and r["s2"] == 0 for r in rows)
    return a, b, c, d


def main():
    rows = [{"id": r["id"], "kelompok": r["kelompok"], "s1": int(r["skor_penilai1"]), "s2": int(r["skor_penilai2"])}
            for r in csv.DictReader(open(SKOR, encoding="utf-8-sig", newline=""))]
    m = metrics(*silang(rows))
    print(f"Gabungan (N = {m['N']}): a {m['a']}  b {m['b']}  c {m['c']}  d {m['d']}")
    for k in ("p_o", "p_e", "kappa", "p_pos", "p_neg", "AC1", "PABAK", "PI", "BI"):
        print(f"  {k:6s} = {m[k]:.4f}")
    print(f"  kappa >= {AMBANG}: {m['kappa_memenuhi_ambang']}")
    per = {}
    for kel in sorted({r["kelompok"] for r in rows}):
        a, b, c, d = silang([r for r in rows if r["kelompok"] == kel])
        per[kel] = {"N": a + b + c + d, "setuju": a + d, "tidak_setuju": b + c, "a": a, "b": b, "c": c, "d": d}
        print(f"{kel}: {per[kel]}  (kappa per kelompok tidak dihitung)")
    galat = []
    if os.path.exists(RINGKASAN):
        ref = json.load(open(RINGKASAN, encoding="utf-8"))
        for k, v in ref["gabungan"].items():
            if isinstance(v, float) and abs(v - m[k]) > 1e-12 or not isinstance(v, float) and v != m[k]:
                galat.append(f"gabungan.{k}: {m[k]} != {v}")
        for kel, v in ref["per_kelompok"].items():
            if per.get(kel) != v:
                galat.append(f"per_kelompok {kel}: {per.get(kel)} != {v}")
        print("Cocok dengan kappa_ringkasan.json" if not galat else "TIDAK cocok: " + "; ".join(galat))
    else:
        print("kappa_ringkasan.json tidak tersedia; pencocokan dilewati.")
    sys.exit(1 if galat else 0)


if __name__ == "__main__":
    main()
