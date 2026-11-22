"""
Penghitung kelas batasan ECP (N_constraint pada rumus 4.2) dari shapes_pdp.ttl.

Definisi (lihat alat_evaluasi.constraint_classes):
  Kelas batasan = himpunan NodeShape dengan target sama (himpunan sh:targetClass identik) dan pola
  constraint sama (HIMPUNAN tanda tangan property shape identik, ditambah constraint tingkat node bila ada).
  Tanda tangan property shape = pasangan (parameter, nilai) seluruh constraint component beserta sh:severity,
  tanpa sh:path, sh:name, sh:message, dan rdfs:*.

Jumlah partisi: N_partisi = N_valid + N_constraint, dengan N_valid = 2 (patuh penuh; peringatan dini 48 < x <= 72 jam).
Keluaran: validation_results/kelas_batasan.csv
"""

import os
import re

import alat_evaluasi as ae

N_VALID = 2


def pasal(label):
    m = re.search(r"\((Pasal .*)\)", label)
    return m.group(1) if m else label


def main():
    shapes = ae.load_graph(ae.SHAPES_PATH)
    classes, n_multiset = ae.constraint_classes(shapes)
    print("Definisi: NodeShape dengan himpunan sh:targetClass sama dan himpunan tanda tangan property shape sama.")
    for c in classes:
        print(f"{c['kelas']}  target={'/'.join(c['target']):<45} NodeShape={', '.join(c['node_shape'])}")
        print(f"      unit V={len(c['unit_violation'])} W={len(c['unit_warning'])}  komponen={', '.join(c['komponen'])}")
    n = len(classes)
    print(f"\nN_constraint = {n} (bila pola dibaca sebagai multiset: {n_multiset})")
    print(f"N_partisi = N_valid + N_constraint = {N_VALID} + {n} = {N_VALID + n}")
    rows = [{**c, "pasal": [pasal(l) for l in c["label"]], "n_unit_violation": len(c["unit_violation"]),
             "n_unit_warning": len(c["unit_warning"])} for c in classes]
    out = os.path.join(ae.OUTPUT_DIR, "kelas_batasan.csv")
    ae.write_csv(out, rows, ["kelas", "target", "node_shape", "pasal", "komponen", "n_unit_violation",
                             "n_unit_warning", "unit"])
    print(f"CSV tersimpan di {out}")


if __name__ == "__main__":
    main()
