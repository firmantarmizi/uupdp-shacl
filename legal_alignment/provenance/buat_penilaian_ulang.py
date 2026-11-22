"""
Membuat legal_alignment/penilaian_ulang.csv: hasil penilaian ulang aturan Pasal 35 (FO-16R) dan Pasal 52 (FO-30R)
versi pasca-deliberasi, 2026-11-09 (2026-11-12; RENCANA_REVISI K7).

Sumber: kartu isian penilai PERBAIKAN/instrumen_kappa/penilaian_ulang/KARTU_PENILAIAN_ULANG_Rater{1,2}_isian.pdf.
Nilainya ditranskripsi dari tabel "Hasil" CHANGELOG_PERBAIKAN.md entri "2026-11-09 (lanjutan) - Hasil kartu penilaian
ulang diterima", yang dibaca dari kedua PDF tersebut. Sebelum menulis, skrip mencocokkan awalan SHA-256 kedua PDF
dengan nilai di CHANGELOG (ff7ed4efda0f641b, 47849defb9d7f4ab); bila berbeda, skrip berhenti dengan kode 1.
Bila PDF tidak tersedia (repositori publik), pencocokan dilewati dan CSV yang ada dipakai apa adanya.

Yang disimpan hanya skor dan kategori baku jenis ketidaksesuaian. Nama, tanda tangan, dan teks alasan bebas penilai
tidak disalin.

Jalankan dari root proyek: .venv\\Scripts\\python.exe -I 03_Publikasi\\repositori\\buat_penilaian_ulang.py
"""

import csv
import hashlib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
if os.name == "nt" and not HERE.startswith("\\\\?\\"):
    HERE = "\\\\?\\" + HERE
ROOT = os.path.dirname(os.path.dirname(HERE))
PDF = os.path.join(ROOT, "PERBAIKAN", "instrumen_kappa", "penilaian_ulang")
SHA_CHANGELOG = {"KARTU_PENILAIAN_ULANG_Rater1_isian.pdf": "ff7ed4efda0f641b",
                 "KARTU_PENILAIAN_ULANG_Rater2_isian.pdf": "47849defb9d7f4ab"}
KELUARAN = os.path.join(HERE, "legal_alignment", "penilaian_ulang.csv")
KOLOM = ["id", "pasal", "aturan_yang_dinilai", "skor_penilai1", "skor_penilai2",
         "jenis_ketidaksesuaian_penilai1", "jenis_ketidaksesuaian_penilai2"]
# Transkripsi CHANGELOG 2026-11-09, tabel "Hasil" (kategori baku instrumen)
BARIS = [
    {"id": "FO-16R", "pasal": "Pasal 35", "aturan_yang_dinilai": "shapes_pdp.ttl v2.4 (pasca-deliberasi): SecurityMeasuresShape",
     "skor_penilai1": 0, "skor_penilai2": 0,
     "jenis_ketidaksesuaian_penilai1": "ada isi pasal yang terlewat; perlu pertimbangan manusia",
     "jenis_ketidaksesuaian_penilai2": "ada isi pasal yang terlewat"},
    {"id": "FO-30R", "pasal": "Pasal 52", "aturan_yang_dinilai": "shapes_pdp.ttl v2.4 (pasca-deliberasi): grup Pasal 52 untuk Prosesor",
     "skor_penilai1": 0, "skor_penilai2": 0,
     "jenis_ketidaksesuaian_penilai1": "ada isi pasal yang terlewat",
     "jenis_ketidaksesuaian_penilai2": "ada isi pasal yang terlewat"},
]


def main():
    if os.path.isdir(PDF):
        salah = []
        for nama, awalan in SHA_CHANGELOG.items():
            h = hashlib.sha256(open(os.path.join(PDF, nama), "rb").read()).hexdigest()
            print(f"{nama}: {h[:16]} (CHANGELOG {awalan})")
            if not h.startswith(awalan):
                salah.append(nama)
        if salah:
            print("SHA-256 tidak cocok:", salah)
            sys.exit(1)
    else:
        print("PDF kartu isian tidak tersedia; pencocokan SHA-256 dilewati.")
    os.makedirs(os.path.dirname(KELUARAN), exist_ok=True)
    with open(KELUARAN, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM)
        w.writeheader()
        w.writerows(BARIS)
    print(f"{len(BARIS)} baris ditulis ke legal_alignment/penilaian_ulang.csv")


if __name__ == "__main__":
    main()
