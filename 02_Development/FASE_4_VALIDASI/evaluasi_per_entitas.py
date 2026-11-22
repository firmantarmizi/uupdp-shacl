"""
Tabel vonis per entitas (focus node) untuk partisi ECP, tanpa laporan lengkap.

Logika evaluasi ada di alat_evaluasi.py (dipakai bersama run_validation.py).
Pengukuran waktu, memori, dan skalabilitas dipindahkan ke ukur_performa.py.
Jalankan: ..\\..\\.venv\\Scripts\\python.exe evaluasi_per_entitas.py
"""

import alat_evaluasi as ae


def main():
    shapes, ont = ae.load_graph(ae.SHAPES_PATH), ae.load_graph(ae.ONTOLOGY_PATH)
    ps_index = ae.property_shapes(shapes)
    results = {}
    for path in (ae.COMPLIANT_PATH, ae.VIOLATION_PATH):
        _, report, _ = ae.validate(ae.load_graph(path), shapes, ont)
        results.update(ae.results_by_entity(report, ps_index))
    rows = ae.evaluate_entities(ae.read_key(ae.KEY_ECP_PATH), results)
    print(f"{'ECP':<8}{'Entitas':<34}{'V':>3}{'W':>3}{'I':>3}  Harapan    Prediksi   Hasil")
    for r in rows:
        print(f"{r['ecp']:<8}{r['entitas']:<34}{r['n_violation']:>3}{r['n_warning']:>3}{r['n_info']:>3}  "
              f"{r['vonis_harapan']:<10} {r['vonis_prediksi']:<10} {r['hasil']}")
    cm = ae.confusion(rows)
    print(f"\nN={cm['N']} TP={cm['TP']} TN={cm['TN']} FP={cm['FP']} FN={cm['FN']}")


if __name__ == "__main__":
    main()
