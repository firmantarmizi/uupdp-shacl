"""
Membuat skor_per_butir.csv untuk repositori publik (keputusan peneliti 2026-11-01, butir 2d).

Masukan : PERBAIKAN/instrumen_kappa/hasil/penilaian_gabungan.csv (44 butir, penilaian pertama yang independen)
Keluaran: 03_Publikasi/repositori/legal_alignment/skor_per_butir.csv

Yang TIDAK disalin: catatan bebas penilai (catatan_r1, catatan_r2) dan teks bebas sesudah "lainnya:" pada kolom
jenis ketidaksesuaian. Hanya kategori baku yang disimpan.

Skor akhir deliberasi: butir sepakat = skor yang disepakati; butir tidak sepakat = KONSENSUS (0), sesuai
CHANGELOG_PERBAIKAN.md 2026-10-28 §13 dan REVISI_BAB4.md A.3. Tidak ada berkas data yang memuat skor akhir.

Pemeriksaan (kode keluar 1 bila gagal): 44 baris; tabel kontingensi sama dengan hasil/kappa_ringkasan.json;
kolom kategori hanya berisi kategori baku.

Jalankan dari root proyek: .venv\\Scripts\\python.exe -I 03_Publikasi\\repositori\\buat_skor_per_butir.py
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
HASIL = os.path.join(ROOT, "PERBAIKAN", "instrumen_kappa", "hasil")
MASUKAN = os.path.join(HASIL, "penilaian_gabungan.csv")
RINGKASAN = os.path.join(HASIL, "kappa_ringkasan.json")
KELUARAN = os.path.join(HERE, "legal_alignment", "skor_per_butir.csv")

KONSENSUS = 0  # skor akhir kelima butir tidak sepakat (CHANGELOG 2026-10-28 §13)
KATEGORI_BAKU_LAINNYA = "lainnya"
KOLOM = ["id", "kelompok", "pasal", "skor_penilai1", "skor_penilai2", "sepakat",
         "jenis_ketidaksesuaian_penilai1", "jenis_ketidaksesuaian_penilai2", "skor_akhir_deliberasi"]


def kategori(teks):
    """Ambil kategori baku; 'lainnya: <teks bebas>' dipotong menjadi 'lainnya'."""
    hasil = []
    for bagian in teks.split(";"):
        bagian = bagian.strip()
        if not bagian:
            continue
        if bagian.lower().startswith(KATEGORI_BAKU_LAINNYA):
            bagian = KATEGORI_BAKU_LAINNYA
        hasil.append(bagian)
    return "; ".join(hasil)


def main():
    with open(MASUKAN, encoding="utf-8-sig", newline="") as f:
        baris = list(csv.DictReader(f))
    galat = []
    if len(baris) != 44:
        galat.append(f"jumlah baris {len(baris)}, seharusnya 44")

    keluar = []
    for b in baris:
        s1, s2 = int(b["skor_r1"]), int(b["skor_r2"])
        sepakat = s1 == s2
        keluar.append({
            "id": b["id"], "kelompok": b["kelompok"], "pasal": b["pasal"],
            "skor_penilai1": s1, "skor_penilai2": s2, "sepakat": sepakat,
            "jenis_ketidaksesuaian_penilai1": kategori(b["deviasi_r1"]),
            "jenis_ketidaksesuaian_penilai2": kategori(b["deviasi_r2"]),
            "skor_akhir_deliberasi": s1 if sepakat else KONSENSUS,
        })

    # Kategori baku yang muncul (dicetak agar dapat diperiksa; tidak boleh ada teks bebas)
    kat = sorted({k.strip() for r in keluar for c in ("jenis_ketidaksesuaian_penilai1", "jenis_ketidaksesuaian_penilai2")
                  for k in r[c].split(";") if k.strip()})
    for k in kat:
        if ":" in k or len(k) > 60:
            galat.append(f"kategori tampak memuat teks bebas: {k!r}")

    # Tabel kontingensi harus sama dengan kappa_ringkasan.json
    a = sum(r["skor_penilai1"] == 1 and r["skor_penilai2"] == 1 for r in keluar)
    b_ = sum(r["skor_penilai1"] == 1 and r["skor_penilai2"] == 0 for r in keluar)
    c = sum(r["skor_penilai1"] == 0 and r["skor_penilai2"] == 1 for r in keluar)
    d = sum(r["skor_penilai1"] == 0 and r["skor_penilai2"] == 0 for r in keluar)
    with open(RINGKASAN, encoding="utf-8") as f:
        g = json.load(f)["gabungan"]
    if (a, b_, c, d) != (g["a"], g["b"], g["c"], g["d"]):
        galat.append(f"kontingensi {(a, b_, c, d)} != kappa_ringkasan.json {(g['a'], g['b'], g['c'], g['d'])}")

    if galat:
        for e in galat:
            print("GAGAL:", e)
        sys.exit(1)

    os.makedirs(os.path.dirname(KELUARAN), exist_ok=True)
    with open(KELUARAN, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM)
        w.writeheader()
        w.writerows(keluar)

    tidak_sepakat = [r["id"] for r in keluar if not r["sepakat"]]
    print(f"Ditulis {KELUARAN}: {len(keluar)} butir")
    print(f"Kontingensi a/b/c/d = {a}/{b_}/{c}/{d} (cocok dengan kappa_ringkasan.json)")
    print(f"Tidak sepakat ({len(tidak_sepakat)}): {', '.join(tidak_sepakat)} -> skor akhir {KONSENSUS}")
    print(f"Kategori yang disimpan: {kat}")


if __name__ == "__main__":
    main()
