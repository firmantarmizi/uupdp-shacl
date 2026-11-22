"""
Membuat legal_alignment/kartu_vs_shape.csv: untuk 33 butir Kelompok A, kartu bahasa awam yang dinilai penilai
(PERBAIKAN/instrumen_kappa/klausul_instrumen.csv, redaksi 2026-10-16) berdampingan dengan unit constraint
shapes_pdp.ttl final (2026-11-12; RENCANA_REVISI R6/K7).

- Kartu disalin apa adanya; kartu yang dinilai tidak diubah.
- Kolom shape dihitung dari shapes_pdp.ttl yang ada sekarang, memakai shacl_details() yang disalin dari
  PERBAIKAN/instrumen_kappa/buat_instrumen.py (baris 212-245, 2026-11-12) agar repositori mandiri.
- FO-16 (Pasal 35) dan FO-30 (Pasal 52) ditandai "berubah pasca-deliberasi": kartu menggambarkan aturan v2.3 yang
  dinilai pada penilaian pertama, sedangkan shape final v2.4 (CHANGELOG 2026-10-28 §14). Kartu penilaian ulang
  untuk v2.4 tidak dimuat di sini (lihat penilaian_ulang.csv).
- Pemetaan kartu -> NodeShape memakai kolom node_shapes pada CSV instrumen.

Jalankan dari root proyek: .venv\\Scripts\\python.exe -I 03_Publikasi\\repositori\\buat_kartu_shape.py
"""

import csv
import os
import sys

import rdflib
import rdflib.collection
from rdflib.namespace import SH

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
if os.name == "nt" and not HERE.startswith("\\\\?\\"):
    HERE = "\\\\?\\" + HERE
ROOT = os.path.dirname(os.path.dirname(HERE))
KARTU = os.path.join(ROOT, "PERBAIKAN", "instrumen_kappa", "klausul_instrumen.csv")
SHAPES = os.path.join(ROOT, "02_Development", "FASE_3_DATASET_SEMANTIK", "shapes_pdp.ttl")
KELUARAN = os.path.join(HERE, "legal_alignment", "kartu_vs_shape.csv")
PDPS = "http://example.org/pdp/shapes#"
BERUBAH = {"FO-16": "shape diubah pasca-deliberasi (v2.3 -> v2.4); kartu = versi yang dinilai pertama",
           "FO-30": "shape diubah pasca-deliberasi (v2.3 -> v2.4); kartu = versi yang dinilai pertama"}
KOLOM_KARTU = ["id", "pasal_ayat", "berlaku_untuk", "yang_diperiksa", "patuh_bila", "melanggar_bila", "peringatan",
               "tidak_diperiksa", "catatan_peneliti", "node_shapes"]


def short(x):
    s = str(x)
    for pre, rep in ((PDPS, ""), ("http://example.org/pdp#", "pdp:"), (str(SH), "sh:"),
                     ("http://www.w3.org/2001/XMLSchema#", "xsd:")):
        s = s.replace(pre, rep)
    return s


def shacl_details(g):
    """Disalin dari PERBAIKAN/instrumen_kappa/buat_instrumen.py. Satu baris per unit constraint per NodeShape."""
    out = []
    params = [SH.minCount, SH.maxCount, SH.datatype, SH.hasValue, SH.minExclusive, SH.maxInclusive, SH["in"]]
    for ns in sorted(g.subjects(rdflib.RDF.type, SH.NodeShape), key=str):
        targets = ", ".join(sorted(short(t) for t in g.objects(ns, SH.targetClass)))
        for ps in g.objects(ns, SH.property):
            comps = []
            for p in params:
                for v in g.objects(ps, p):
                    if p == SH["in"]:
                        v = "(" + " ".join(f'"{x}"' for x in rdflib.collection.Collection(g, v)) + ")"
                    comps.append(f"{short(p)} {short(v) if p != SH['in'] else v}")
            out.append({"node_shape": short(ns), "target": targets,
                        "unit": short(ps) if isinstance(ps, rdflib.URIRef) else f"{short(ns)}:{short(g.value(ps, SH.path))}",
                        "path": short(g.value(ps, SH.path)), "komponen": "; ".join(comps),
                        "severity": short(g.value(ps, SH.severity))})
        for lst in g.objects(ns, SH["or"]):
            alts = []
            for m in rdflib.collection.Collection(g, lst):
                alts.append(f"{short(g.value(m, SH.path))} sh:hasValue {g.value(m, SH.hasValue)}")
            out.append({"node_shape": short(ns), "target": targets, "unit": f"{short(ns)} (tingkat node)",
                        "path": "—", "komponen": "sh:or ( " + " | ".join(alts) + " )",
                        "severity": short(g.value(ns, SH.severity))})
    return out


def main():
    g = rdflib.Graph().parse(data=open(SHAPES, encoding="utf-8").read(), format="turtle")
    detail = shacl_details(g)
    per_ns = {}
    for d in detail:
        per_ns.setdefault(d["node_shape"], []).append(d)
    kartu = [r for r in csv.DictReader(open(KARTU, encoding="utf-8-sig", newline="")) if r["id"].startswith("FO-")]
    galat = []
    if len(kartu) != 33:
        galat.append(f"jumlah kartu Kelompok A {len(kartu)}, seharusnya 33")
    keluar = []
    for k in kartu:
        nss = [x.strip() for x in k["node_shapes"].replace(";", ",").split(",") if x.strip()]
        unit = [d for ns in nss for d in per_ns.get(ns, [])]
        if not unit:
            galat.append(f"{k['id']}: node shape {nss} tidak ditemukan di shapes_pdp.ttl")
        row = {c: k.get(c, "") for c in KOLOM_KARTU}
        row["target_shape"] = " | ".join(sorted({d["target"] for d in unit}))
        row["unit_shape_final"] = " | ".join(f"{d['unit']} [{d['komponen']}; {d['severity']}]" for d in unit)
        row["n_unit"] = len(unit)
        row["status"] = BERUBAH.get(k["id"], "shape final sama dengan aturan yang dinilai")
        keluar.append(row)
    os.makedirs(os.path.dirname(KELUARAN), exist_ok=True)
    with open(KELUARAN, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM_KARTU + ["target_shape", "unit_shape_final", "n_unit", "status"])
        w.writeheader()
        w.writerows(keluar)
    print(f"{len(keluar)} kartu ditulis; unit shape total {sum(r['n_unit'] for r in keluar)}")
    for e in galat:
        print("GALAT:", e)
    sys.exit(1 if galat else 0)


if __name__ == "__main__":
    main()
