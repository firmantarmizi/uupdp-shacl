"""
Perhitungan kesepakatan antar-penilai untuk instrumen Legal Alignment (Tahap 11c).

Penilai: dua validator independen (Rater 1 dan Rater 2); peneliti tidak menilai (CHANGELOG 2026-10-14).
Masukan: rater1.xlsx dan rater2.xlsx yang sudah terisi (lembar "Penilaian", kolom "SKOR (1/0)"), atau
--dari-gform <csv>: CSV unduhan Google Sheet respons Google Form (buat_google_form.gs). Baris dipisah menurut
kolom "Peran"; jawaban dipetakan lewat prefiks id klausul pada judul kolom, mis. "[FO-01] Skor".
Aturan pelaporan ditetapkan sebelum penilaian (lihat CHANGELOG Tahap 11a):
  - Ukuran utama (Bab 3): Cohen's kappa, ambang >= 0,70, beserta tabel kontingensi, p_o, dan p_e.
  - Ukuran pendamping (deskriptif, bukan kriteria lulus): p_o, kesepakatan spesifik positif/negatif
    (p_pos, p_neg), Gwet's AC1, PABAK, indeks prevalensi (PI), dan indeks bias (BI).
  - kappa "tidak terdefinisi" bila p_e = 1 (kedua penilai memberi satu kategori yang sama untuk semua butir).
  - Rincian per kelompok (FO dan kontrol) berupa jumlah setuju/tidak setuju; kappa per kelompok tidak dihitung.
Tabel kontingensi: a = (R1=1, R2=1), b = (R1=1, R2=0), c = (R1=0, R2=1), d = (R1=0, R2=0).

Contoh:
  ..\\..\\.venv\\Scripts\\python.exe hitung_kappa.py
  ..\\..\\.venv\\Scripts\\python.exe hitung_kappa.py --uji
  ..\\..\\.venv\\Scripts\\python.exe hitung_kappa.py --dari-gform respons.csv
"""

import argparse
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AMBANG = 0.70
CSV_KLAUSUL = os.path.join(HERE, "klausul_instrumen.csv")
KOLOM_ID = re.compile(r"^\[((?:FO|KT)-\d{2})\] (Skor|Jenis ketidaksesuaian|Catatan)")


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


def read_sheet(path):
    from openpyxl import load_workbook
    ws = load_workbook(path, data_only=True)["Penilaian"]
    head = [c.value for c in ws[1]]
    idx = {k: head.index(k) for k in ("No", "Kelompok", "Pasal/Ayat", "SKOR (1/0)", "Jenis ketidaksesuaian (bila skor 0)",
                                      "Catatan penilai")}
    rows, errs = {}, []
    for i, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if r[idx["No"]] in (None, ""):
            continue
        v = r[idx["SKOR (1/0)"]]
        v = str(v).strip() if v is not None else ""
        if v in ("1", "1.0"):
            s = 1
        elif v in ("0", "0.0"):
            s = 0
        else:
            s = None
            errs.append(f"{os.path.basename(path)} baris {i} ({r[idx['No']]}): skor "
                        f"{'belum terisi' if v == '' else repr(v) + ' bukan 0/1'}")
        jenis = str(r[idx["Jenis ketidaksesuaian (bila skor 0)"]] or "").strip()
        catatan = str(r[idx["Catatan penilai"]] or "").strip()
        errs += cek_alasan(f"{os.path.basename(path)} baris {i} ({r[idx['No']]})", s, jenis,
                           lainnya_tanpa_alasan=jenis == "lainnya" and not catatan)
        rows[r[idx["No"]]] = {"kelompok": r[idx["Kelompok"]], "pasal": r[idx["Pasal/Ayat"]], "skor": s,
                              "jenis_deviasi": jenis, "catatan": catatan}
    return rows, errs


def cek_alasan(lokasi, skor, jenis, lainnya_tanpa_alasan=False):
    """Aturan instrumen: bila skor 0, jenis ketidaksesuaian wajib; bila memilih "lainnya", alasannya wajib ditulis."""
    errs = []
    if skor == 0 and not jenis:
        errs.append(f"{lokasi}: skor 0 tetapi jenis ketidaksesuaian belum diisi")
    if lainnya_tanpa_alasan:
        errs.append(f"{lokasi}: memilih \"lainnya\" tetapi alasannya belum ditulis")
    return errs


def pisah_jenis_gform(sel):
    """Sel kotak centang Google Sheet -> (pilihan baku, teks "Lainnya"). Sheet menggabungkan pilihan dengan ", ";
    teks opsi "Lainnya" ditulis apa adanya sehingga dikenali sebagai sisa setelah pilihan baku dikeluarkan."""
    import buat_instrumen as bi
    sisa, baku = sel, []
    for p in bi.JENIS_DEVIASI[:-1]:
        if p in sisa:
            baku.append(p)
            sisa = sisa.replace(p, "")
    sisa = re.sub(r"^[\s,]+|[\s,]+$", "", re.sub(r"(,\s*){2,}", ", ", sisa))
    return baku, sisa


def parse_skor(v):
    """'1 = ...' / '0 = ...' / '1' -> (skor, galat)."""
    v = "" if v is None else str(v).strip()
    if v[:1] in ("0", "1") and (len(v) == 1 or not v[1].isdigit()):
        return int(v[0]), ""
    return None, "belum terisi" if v == "" else f"{v[:30]!r} bukan 0/1"


def read_gform(path, klausul_path=CSV_KLAUSUL):
    """CSV Google Sheet -> (rater1, rater2, galat). Tepat satu respons per peran; bila lebih, berhenti tanpa memilih."""
    with open(klausul_path, encoding="utf-8-sig", newline="") as f:
        ref = {r["id"]: r for r in csv.DictReader(f)}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        head = next(reader)
        data = [row for row in reader if any(c.strip() for c in row)]
    peran_col = next((i for i, h in enumerate(head) if h.strip().lower().startswith("peran")), None)
    waktu_col = next((i for i, h in enumerate(head) if h.strip().lower() in ("timestamp", "stempel waktu")), None)
    if peran_col is None:
        return {}, {}, ["kolom 'Peran' tidak ditemukan pada CSV"]
    cols = {}
    for i, h in enumerate(head):
        m = KOLOM_ID.match(h.strip())
        if m:
            cols.setdefault(m.group(1), {})[m.group(2)] = i
    errs = []
    asing = sorted(set(cols) - set(ref))
    hilang = sorted(set(ref) - {i for i, c in cols.items() if "Skor" in c})
    if asing:
        errs.append(f"id di CSV yang tidak ada di klausul_instrumen.csv: {asing}")
    if hilang:
        errs.append(f"kolom skor tidak ditemukan untuk id: {hilang}")
    per_peran = {}
    for n, row in enumerate(data, start=2):
        per_peran.setdefault(row[peran_col].strip(), []).append((n, row))
    out = {}
    for label, key in (("Rater 1", "r1"), ("Rater 2", "r2")):
        rs = [x for p, lst in per_peran.items() if p.startswith(label) for x in lst]
        if not rs:
            errs.append(f"tidak ada respons dengan peran {label}")
            continue
        if len(rs) > 1:
            waktu = [row[waktu_col] if waktu_col is not None else f"baris {n}" for n, row in rs]
            errs.append(f"peran {label} mengirim {len(rs)} respons ({'; '.join(waktu)}). Peneliti harus memutuskan "
                        "respons yang berlaku dan menghapus yang lain dari CSV; skrip tidak memilih.")
            continue
        row, rows = rs[0][1], {}
        for i in sorted(ref):
            c = cols.get(i, {})
            skor, e = parse_skor(row[c["Skor"]]) if "Skor" in c else (None, "kolom tidak ada")
            if e:
                errs.append(f"{label} {i}: skor {e}")
            sel = row[c["Jenis ketidaksesuaian"]].strip() if "Jenis ketidaksesuaian" in c else ""
            baku, lainnya = pisah_jenis_gform(sel)
            jenis = "; ".join(baku + ([f"lainnya: {lainnya}"] if lainnya else []))
            errs += cek_alasan(f"{label} {i}", skor, jenis)
            rows[i] = {"kelompok": ref[i]["kelompok"], "pasal": ref[i]["pasal_ayat"], "skor": skor,
                       "jenis_deviasi": jenis, "catatan": row[c["Catatan"]].strip() if "Catatan" in c else ""}
        out[key] = rows
    lain = sorted(p for p in per_peran if not p.startswith(("Rater 1", "Rater 2")))
    if lain:
        errs.append(f"nilai peran tidak dikenal: {lain}")
    return out.get("r1", {}), out.get("r2", {}), errs


def fmt(x):
    return "tidak terdefinisi" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))


def report(m, title):
    print(f"\n{title}")
    print("                 R2 = 1   R2 = 0   Total")
    print(f"  R1 = 1        {m['a']:>6}   {m['b']:>6}   {m['a'] + m['b']:>5}")
    print(f"  R1 = 0        {m['c']:>6}   {m['d']:>6}   {m['c'] + m['d']:>5}")
    print(f"  Total         {m['a'] + m['c']:>6}   {m['b'] + m['d']:>6}   {m['N']:>5}")
    for k in ("p_o", "p_e", "kappa", "p_pos", "p_neg", "AC1", "PABAK", "PI", "BI"):
        print(f"  {k:<6} = {fmt(m[k])}")
    if m["kappa"] is None:
        print("  Catatan: p_e = 1, sehingga kappa tidak terdefinisi; laporkan ukuran pendamping.")
    else:
        print(f"  kappa >= {AMBANG}: {'ya' if m['kappa_memenuhi_ambang'] else 'tidak'}")
    if abs(m["PI"]) >= 0.5:
        print("  Catatan: |PI| >= 0,5 (prevalensi timpang); kappa ditafsirkan bersama AC1, p_pos, dan p_neg "
              "(paradoks kappa).")


def self_test():
    ok = True

    def cek(nama, cond, info):
        nonlocal ok
        print(f"  [{'OK' if cond else 'GAGAL'}] {nama}: {info}")
        ok &= cond

    print("Swa-uji hitung_kappa.py")
    m = metrics(34, 2, 1, 10)  # tabel arsip GOLD bagian 3
    cek("tabel arsip 34/2/1/10", abs(m["kappa"] - 0.8275) < 0.001,
        f"kappa = {m['kappa']:.4f} (GOLD: 0,8275 dari p_o/p_e yang dibulatkan), p_o = {m['p_o']:.4f}, "
        f"p_e = {m['p_e']:.4f}")
    m = metrics(40, 2, 2, 0)  # paradoks: kesepakatan tinggi, kappa negatif
    pi = 42 / 44
    ac1 = (40 / 44 - 2 * pi * (1 - pi)) / (1 - 2 * pi * (1 - pi))
    cek("paradoks 40/2/2/0", m["kappa"] < 0 and abs(m["p_o"] - 40 / 44) < 1e-9 and abs(m["AC1"] - ac1) < 1e-9,
        f"p_o = {m['p_o']:.4f}, kappa = {m['kappa']:.4f}, AC1 = {m['AC1']:.4f} (hitung tangan {ac1:.4f}), "
        f"PI = {m['PI']:.4f}")
    m = metrics(44, 0, 0, 0)
    cek("semua bernilai 1", m["kappa"] is None and m["AC1"] == 1.0 and m["PABAK"] == 1.0,
        f"kappa = {fmt(m['kappa'])}, AC1 = {m['AC1']}, PABAK = {m['PABAK']}")
    m = metrics(22, 0, 0, 22)
    cek("kesepakatan sempurna seimbang", abs(m["kappa"] - 1) < 1e-12 and abs(m["AC1"] - 1) < 1e-12,
        f"kappa = {m['kappa']:.4f}, AC1 = {m['AC1']:.4f}")
    print("Swa-uji " + ("LOLOS" if ok else "GAGAL"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rater1", default=os.path.join(HERE, "rater1.xlsx"))
    ap.add_argument("--rater2", default=os.path.join(HERE, "rater2.xlsx"))
    ap.add_argument("--keluaran", default=os.path.join(HERE, "hasil"))
    ap.add_argument("--uji", action="store_true", help="swa-uji rumus tanpa membaca berkas penilaian")
    ap.add_argument("--dari-gform", metavar="CSV", help="CSV unduhan Google Sheet respons Google Form")
    a = ap.parse_args()
    if a.uji:
        return self_test()

    if a.dari_gform:
        r1, r2, errs = read_gform(a.dari_gform)
    else:
        r1, e1 = read_sheet(a.rater1)
        r2, e2 = read_sheet(a.rater2)
        errs = e1 + e2
    if r1 and r2 and set(r1) != set(r2):
        errs.append(f"id butir berbeda: hanya di rater1 {sorted(set(r1) - set(r2))}, "
                    f"hanya di rater2 {sorted(set(r2) - set(r1))}")
    if errs:
        print("Berkas penilaian belum lengkap atau tidak valid; perhitungan dihentikan:")
        for e in errs[:20]:
            print(" -", e)
        if len(errs) > 20:
            print(f" - ... dan {len(errs) - 20} lainnya")
        return 1

    def table(ids):
        cnt = {"a": 0, "b": 0, "c": 0, "d": 0}
        for i in ids:
            s1, s2 = r1[i]["skor"], r2[i]["skor"]
            cnt["a" if (s1, s2) == (1, 1) else "b" if (s1, s2) == (1, 0) else "c" if (s1, s2) == (0, 1) else "d"] += 1
        return cnt

    ids = sorted(r1)
    total = metrics(**table(ids))
    report(total, f"Gabungan ({len(ids)} butir)")
    per_grup = {}
    for g in sorted({r1[i]["kelompok"] for i in ids}):
        gid = [i for i in ids if r1[i]["kelompok"] == g]
        t = table(gid)
        per_grup[g] = {"N": len(gid), "setuju": t["a"] + t["d"], "tidak_setuju": t["b"] + t["c"], **t}
        print(f"\n{g}: N = {len(gid)}, setuju = {t['a'] + t['d']}, tidak setuju = {t['b'] + t['c']} "
              f"(a={t['a']}, b={t['b']}, c={t['c']}, d={t['d']})")
    beda = [{"id": i, "pasal": r1[i]["pasal"], "kelompok": r1[i]["kelompok"], "skor_r1": r1[i]["skor"],
             "skor_r2": r2[i]["skor"], "deviasi_r1": r1[i]["jenis_deviasi"], "catatan_r1": r1[i]["catatan"],
             "deviasi_r2": r2[i]["jenis_deviasi"], "catatan_r2": r2[i]["catatan"]}
            for i in ids if r1[i]["skor"] != r2[i]["skor"]]
    print(f"\nKetidaksepakatan ({len(beda)} butir):")
    for x in beda:
        print(f"  {x['id']} {x['pasal']}: R1 = {x['skor_r1']} ({x['deviasi_r1']}; {x['catatan_r1']}) | "
              f"R2 = {x['skor_r2']} ({x['deviasi_r2']}; {x['catatan_r2']})")

    os.makedirs(a.keluaran, exist_ok=True)
    with open(os.path.join(a.keluaran, "kappa_ringkasan.json"), "w", encoding="utf-8") as f:
        json.dump({"gabungan": total, "per_kelompok": per_grup, "ambang_kappa": AMBANG}, f, ensure_ascii=False,
                  indent=2)
    with open(os.path.join(a.keluaran, "penilaian_gabungan.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "kelompok", "pasal", "skor_r1", "skor_r2", "sepakat", "deviasi_r1", "catatan_r1",
                    "deviasi_r2", "catatan_r2"])
        for i in ids:
            w.writerow([i, r1[i]["kelompok"], r1[i]["pasal"], r1[i]["skor"], r2[i]["skor"],
                        r1[i]["skor"] == r2[i]["skor"], r1[i]["jenis_deviasi"], r1[i]["catatan"],
                        r2[i]["jenis_deviasi"], r2[i]["catatan"]])
    with open(os.path.join(a.keluaran, "ketidaksepakatan.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "pasal", "kelompok", "skor_r1", "skor_r2", "deviasi_r1",
                                          "catatan_r1", "deviasi_r2", "catatan_r2"])
        w.writeheader()
        w.writerows(beda)
    print(f"\nHasil tersimpan di {a.keluaran}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
