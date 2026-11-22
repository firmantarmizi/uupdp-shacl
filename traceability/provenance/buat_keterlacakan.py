"""
Berkas keterlacakan berbahasa Inggris untuk repositori publik (keputusan peneliti 2026-11-01, butir 1).
Dokumen Fase 1-2 asli tidak diubah dan tidak dibuka; dua CSV ini diturunkan dari artefak final.

Keluaran (folder traceability/):
  operability_screening.csv  76 pasal: nomor, bab resmi, skor S-A-K-T-D, total, kelas operabilitas
  traceability.csv           33 klausul Fully Operable: pasal/ayat, kutipan resmi (bahasa Indonesia), NodeShape,
                             unit constraint, kelas target, jenis pemicu, severity, modalitas deontik, catatan
  log_keterlacakan.txt       hasil pemeriksaan konsistensi

Sumber:
  - 02_Development/FASE_1_PENYARINGAN_OPERABILITAS/MATRIKS_PENYARINGAN_OPERABILITAS.md (skor per pasal, bab)
  - 02_Development/FASE_1_PENYARINGAN_OPERABILITAS/SELECTED_CLAUSES.md (pasal/ayat final, tipe deontik)
  - 02_Development/FASE_3_DATASET_SEMANTIK/shapes_pdp.ttl dan ontology_pdp.ttl (pemetaan ke shape, target, severity)
  - PERBAIKAN/instrumen_kappa/klausul_instrumen.csv: HANYA kolom kutipan_resmi (teks UU verbatim) dan penanda
    "Interpretasi peneliti". Kolom aturan pemeriksaan/node_shapes di berkas itu berasal dari sebelum deliberasi
    dan tidak dipakai.
  - 02_Development/FASE_4_VALIDASI/validation_results/resmi_v3/tabel_bab4_20261029/tabel_4_2.csv (pembanding)

Kode keluar 1 bila salah satu pemeriksaan konsistensi gagal.
Jalankan dari root proyek: .venv\\Scripts\\python.exe -I 03_Publikasi\\repositori\\buat_keterlacakan.py
"""

import csv
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEV = os.path.join(ROOT, "02_Development")
FASE1 = os.path.join(DEV, "FASE_1_PENYARINGAN_OPERABILITAS")
FASE4 = os.path.join(DEV, "FASE_4_VALIDASI")
sys.path.insert(0, FASE4)
import alat_evaluasi as ae  # noqa: E402
from rdflib.namespace import RDF, RDFS, SH  # noqa: E402

MATRIKS = os.path.join(FASE1, "MATRIKS_PENYARINGAN_OPERABILITAS.md")
SELECTED = os.path.join(FASE1, "SELECTED_CLAUSES.md")
INSTRUMEN = os.path.join(ROOT, "PERBAIKAN", "instrumen_kappa", "klausul_instrumen.csv")
TABEL_4_2 = os.path.join(FASE4, "validation_results", "resmi_v3", "tabel_bab4_20261029", "tabel_4_2.csv")
OUT = os.path.join(HERE, "traceability")

KELAS = {"FO": "Fully Operable", "P": "Partial", "NO": "Non-Operable"}
TERLARANG = ("PERBAIKAN/", "referensi/", "KOREKSI_PASAL", "CHANGELOG", "Bagian ", "Tahap ")
LOG, GAGAL = [], []


def log(t):
    LOG.append(t)
    print(t)


def cek(syarat, pesan):
    log(("LULUS  " if syarat else "GAGAL  ") + pesan)
    if not syarat:
        GAGAL.append(pesan)


# ----------------------------------------------------------------------------------------------------------------
# 1. Matriks penyaringan (76 pasal)
# ----------------------------------------------------------------------------------------------------------------
def baca_matriks():
    bab, rows = None, []
    for b in open(MATRIKS, encoding="utf-8").read().splitlines():
        m = re.match(r"^## (BAB [IVX]+) — (.*?) \(Pasal", b)
        if m:
            bab = (m.group(1).replace("BAB ", ""), m.group(2).strip())
            continue
        if b.startswith("## ") and not b.startswith("## BAB"):
            bab = None
        m = re.match(r"^\| (\d+) \|", b)
        if m and bab:
            c = [x.strip() for x in b.strip().strip("|").split("|")]
            skor = [int(x) for x in c[3:8]]
            total = int(c[8].replace("*", ""))
            status = c[9].replace("*", "").split()[0]
            rows.append({"article": int(c[0]), "chapter": bab[0], "chapter_title_official_id": bab[1],
                         "S": skor[0], "A": skor[1], "K": skor[2], "T": skor[3], "D": skor[4],
                         "total": total, "operability_class": KELAS[status]})
    return rows


# ----------------------------------------------------------------------------------------------------------------
# 2. Klausul terpilih
# ----------------------------------------------------------------------------------------------------------------
def label_inggris(label):
    """'Ps. 35 huruf a' -> 'Art. 35(a)'; 'Ps. 46 ayat (1)–(2)' -> 'Art. 46(1)–(2)'; 'Ps. 24' -> 'Art. 24'."""
    m = re.match(r"Ps\. (\d+)(.*)$", label.strip())
    n, sisa = m.group(1), m.group(2).strip()
    sisa = re.sub(r"^ayat ", "", sisa)
    sisa = re.sub(r"^huruf ([a-z])$", r"(\1)", sisa)
    return f"Art. {n}{sisa.replace(' ', '')}"


def baca_selected():
    rows = []
    for b in open(SELECTED, encoding="utf-8").read().splitlines():
        m = re.match(r"^\| (\d+) \| \*\*(Ps\. [^*]+)\*\* \| \**(\d)\** \| (.*)$", b)
        if not m:
            continue
        dm = re.search(r"\|\s*\**(Obligation|Prohibition|Permission)\b", m.group(4))
        if not dm:
            raise SystemExit(f"Tipe deontik tidak terbaca: {b[:80]}")
        deontik = dm.group(1)
        label = m.group(2).strip()
        rows.append({"no": int(m.group(1)), "label_id": label, "article": int(re.search(r"\d+", label).group()),
                     "article_paragraph": label_inggris(label), "deontic": deontik.lower()})
    return rows


def ayat_dari(teks, n):
    """Himpunan nomor ayat yang menyertai 'Pasal n ayat ...' / 'Ps. n ayat ...' (rentang '–'/'sampai' dibuka)."""
    hasil = set()
    for m in re.finditer(rf"(?:Pasal|Ps\.) {n} ayat ((?:\(\d+\)(?:\s*(?:–|-|sampai|dan|,)\s*)?)+)", teks):
        nums = [int(x) for x in re.findall(r"\((\d+)\)", m.group(1))]
        if re.search(r"–|-|sampai", m.group(1)) and len(nums) == 2:
            nums = list(range(nums[0], nums[1] + 1))
        hasil.update(nums)
    return hasil


# ----------------------------------------------------------------------------------------------------------------
# 3. Pemetaan dari shapes_pdp.ttl final
# ----------------------------------------------------------------------------------------------------------------
def pemetaan_shapes():
    g = ae.load_graph(ae.SHAPES_PATH)
    units = ae.property_shapes(g)
    label_ns = {ae.local(ns): str(g.value(ns, RDFS.label) or "") for ns in g.subjects(RDF.type, SH.NodeShape)}
    pesan = {}
    for node, d in units.items():
        msg = g.value(node, SH.message)
        pesan[d["id"]] = str(msg) if msg is not None else ""
    per_pasal = defaultdict(list)
    for node, d in units.items():
        sumber = pesan[d["id"]] if re.search(r"Pasal \d+", pesan[d["id"]]) else label_ns[d["node_shape"]]
        for n in {int(x) for x in re.findall(r"Pasal (\d+)", sumber)}:
            per_pasal[n].append(d)
    # Pasal yang hanya disebut di label NodeShape (mis. Pasal 52 untuk Prosesor): semua unit NodeShape itu
    for ns, lab in label_ns.items():
        for n in {int(x) for x in re.findall(r"Pasal (\d+)", lab)}:
            if n not in per_pasal:
                per_pasal[n].extend(d for d in units.values() if d["node_shape"] == ns)
    return g, units, label_ns, pesan, per_pasal


def jenis_pemicu(target, ont):
    kelas = {ae.local(c) for c in ont.subjects(RDF.type, RDFS.Class)}
    induk = {k: set() for k in kelas}
    for c in ont.subjects(RDF.type, RDFS.Class):
        for s in ont.objects(c, RDFS.subClassOf):
            induk[ae.local(c)].add(ae.local(s))

    def leluhur(k):
        hasil, antre = set(), list(induk.get(k, ()))
        while antre:
            p = antre.pop()
            if p not in hasil:
                hasil.add(p)
                antre.extend(induk.get(p, ()))
        return hasil

    if target in ae.EVENT_CLASSES or leluhur(target) & set(ae.EVENT_CLASSES):
        return "event"
    if "DataController" in leluhur(target) or target == ae.DPO_TRIGGER or ae.DPO_TRIGGER in leluhur(target):
        return "characteristic"
    return "none"


def kutipan_instrumen():
    rows = list(csv.DictReader(open(INSTRUMEN, encoding="utf-8-sig", newline="")))
    hasil = {}
    for r in rows:
        if not r["kelompok"].startswith("A."):
            continue
        n = int(re.search(r"\d+", r["pasal_ayat"]).group())
        hasil[n] = {"kutipan": r["kutipan_resmi"].strip(), "interpretasi": "Interpretasi peneliti" in r["penanda"]}
    return hasil


def main():
    os.makedirs(OUT, exist_ok=True)
    log("buat_keterlacakan.py - sumber: MATRIKS_PENYARINGAN_OPERABILITAS.md, SELECTED_CLAUSES.md, shapes_pdp.ttl, "
        "ontology_pdp.ttl, klausul_instrumen.csv (kutipan_resmi, penanda)")

    # ---- operability_screening.csv
    mat = baca_matriks()
    nomor = [r["article"] for r in mat]
    cek(len(mat) == 76 and sorted(nomor) == list(range(1, 77)), f"1a. 76 pasal unik bernomor 1-76 (terbaca {len(mat)})")
    cek(all(r["total"] == r["S"] + r["A"] + r["K"] + r["T"] + r["D"] for r in mat), "1b. total = S+A+K+T+D")
    ambang = lambda t: "Fully Operable" if t >= 4 else ("Partial" if t == 3 else "Non-Operable")  # noqa: E731
    cek(all(r["operability_class"] == ambang(r["total"]) for r in mat), "1c. kelas sesuai ambang >= 4 / 3 / <= 2")

    t42 = list(csv.DictReader(open(TABEL_4_2, encoding="utf-8-sig", newline="")))
    resmi = {}
    for r in t42:
        for k, v in (("Fully Operable", "Fully"), ("Partial", "Parsial"), ("Non-Operable", "Non-Operable")):
            if r["kategori"].startswith(v):
                resmi[k] = (int(r["jumlah"]), {int(x) for x in r["pasal"].split(",") if x.strip()})
    for k, (jml, daftar) in resmi.items():
        ada = {r["article"] for r in mat if r["operability_class"] == k}
        cek(len(ada) == jml and ada == daftar, f"2. {k}: {len(ada)} pasal, sama dengan tabel_4_2.csv ({jml})")

    with open(os.path.join(OUT, "operability_screening.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mat[0].keys()))
        w.writeheader()
        w.writerows(sorted(mat, key=lambda r: r["article"]))

    # ---- traceability.csv
    sel = baca_selected()
    g, units, label_ns, pesan, per_pasal = pemetaan_shapes()
    ont = ae.load_graph(ae.ONTOLOGY_PATH)
    kut = kutipan_instrumen()
    fo_mat = {r["article"] for r in mat if r["operability_class"] == "Fully Operable"}
    fo_sel = {r["article"] for r in sel}
    fo_shp = {n for n in per_pasal if n in fo_mat or n in fo_sel}
    cek(len(sel) == 33 and fo_mat == fo_sel, f"3a. pasal FO matriks = SELECTED_CLAUSES ({len(fo_sel)})")
    tak_dikutip = sorted(fo_sel - set(per_pasal))
    cek(not tak_dikutip, f"3b. setiap pasal FO dikutip shapes_pdp.ttl (tidak dikutip: {tak_dikutip or '-'})")
    lebih = sorted(set(per_pasal) - fo_sel)
    log(f"       pasal yang dikutip shapes tetapi bukan klausul FO tersendiri: {lebih or '-'}")

    keluar = []
    for r in sel:
        n = r["article"]
        d = per_pasal.get(n, [])
        ns = sorted({x["node_shape"] for x in d})
        targets = sorted({t for x in d for t in x["targets"]})
        if n == 52:
            targets = ["DataProcessor"]  # Pasal 52 memperluas kewajiban Pengendali kepada Prosesor
        jenis = sorted({jenis_pemicu(t, ont) for t in targets} - {"none"}) or ["none"]
        q = kut.get(n, {}).get("kutipan", "")
        catatan = []
        if r["label_id"].endswith("huruf a"):
            potong = re.search(r"\n\s*b\.", q)
            if potong:
                q = re.sub(r";?\s*dan\s*$", "", q[:potong.start()].rstrip()) + "; […]"
            catatan.append("letter (b) not encoded: requires human judgement")
        if kut.get(n, {}).get("interpretasi"):
            catatan.append("trigger condition is the authors' interpretation")
        if n == 29:  # keputusan peneliti P6 B9 (2026-11-01); lihat Catatan Ps. 29 di SELECTED_CLAUSES
            catatan.append("paragraph (2) is checked as evidence of the obligation in paragraph (1)")
        if n == 53:
            catatan.append("letters (a)-(c) alternative per Constitutional Court Decision 151/PUU-XXII/2024")
        if n == 52 or any(x["node_shape"] in ns and "DataProcessor" in x["targets"] for x in d) and n != 52:
            if n in (29, 31, 35, 36, 37, 38, 39):
                catatan.append("also applies to processors via Art. 52")
        keluar.append({
            "article_paragraph": r["article_paragraph"],
            "official_text_id": " ".join(q.split()),
            "node_shapes": "; ".join(ns),
            "constraint_units": "; ".join(sorted(x["id"] for x in d)),
            "target_classes": "; ".join(targets),
            "trigger_type": "; ".join(jenis),
            "severity": "; ".join(sorted({x["severity"] for x in d})),
            "deontic": r["deontic"],
            "note": "; ".join(catatan),
        })
        # peringatan ayat: SELECTED vs label/pesan shapes
        a_sel = ayat_dari(r["label_id"].replace("Ps.", "Pasal"), n)
        teks_shape = " ".join([label_ns[s] for s in ns] + [pesan[x["id"]] for x in d])
        a_shp = ayat_dari(teks_shape, n)
        if a_sel and a_shp and a_sel != a_shp:
            log(f"PERINGATAN ayat Pasal {n}: SELECTED_CLAUSES {sorted(a_sel)} vs shapes_pdp.ttl {sorted(a_shp)}")

    ns_semua = {ae.local(x) for x in g.subjects(RDF.type, SH.NodeShape)}
    ns_dipakai = {s for k in keluar for s in k["node_shapes"].split("; ") if s}
    unit_dipakai = {u for k in keluar for u in k["constraint_units"].split("; ") if u}
    cek(ns_dipakai == ns_semua, f"4a. setiap NodeShape muncul ({len(ns_dipakai)}/{len(ns_semua)})")
    cek(unit_dipakai == {d["id"] for d in units.values()}, f"4b. setiap unit muncul ({len(unit_dipakai)}/{len(units)})")
    cek(all(k["official_text_id"] for k in keluar), "5a. setiap klausul memiliki kutipan resmi")

    with open(os.path.join(OUT, "traceability.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(keluar[0].keys()))
        w.writeheader()
        w.writerows(keluar)

    for nama in ("operability_screening.csv", "traceability.csv"):
        isi = open(os.path.join(OUT, nama), encoding="utf-8").read()
        temu = [s for s in TERLARANG if s in isi]
        cek(not temu, f"5b. {nama} tidak merujuk berkas/tahap internal ({temu or '-'})")

    log(f"Ditulis: traceability/operability_screening.csv ({len(mat)} baris), traceability/traceability.csv "
        f"({len(keluar)} baris)")
    with open(os.path.join(OUT, "log_keterlacakan.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
    if GAGAL:
        sys.exit(1)


if __name__ == "__main__":
    main()
