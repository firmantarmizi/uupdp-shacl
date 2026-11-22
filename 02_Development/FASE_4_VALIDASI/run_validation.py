"""
Validasi kepatuhan semantik UU No. 27 Tahun 2022 (UU PDP) dengan pySHACL.

1. Statistik artefak (NodeShape, property shape dan constraint tingkat node per severity, triple per berkas),
   dihitung dari berkas.
2. Pemeriksaan integritas data uji (alat_evaluasi.integrity_check; bukan vonis hukum) dan pemeriksaan desain
   partisi ECP terhadap kelas batasan (alat_evaluasi.check_partitions).
3. Validasi graf ECP (data_pse_compliant.ttl, data_pse_violation.ttl): ringkasan severity per graf dan tiga
   besaran (hasil validasi, pasangan (focus node, unit) terpicu, focus node terpicu).
4. Evaluasi per focus node terhadap kunci_jawaban_ecp.csv:
   - metrik utama tingkat entitas (vonis Violation bila ada >= 1 sh:Violation): TP/TN/FP/FN, precision, recall, F1;
   - tabel pendukung vonis per pelaku (Pengendali beserta entitas peristiwanya), bukan metrik;
   - bukti cakupan tingkat shape (bukan metrik akurasi utama).
5. Uji batas (Boundary Value Analysis) pada data_uji_batas_bva.ttl terhadap kunci_jawaban_bva.csv,
   dilaporkan terpisah dari ECP.

Pengukuran waktu dan memori ada di ukur_performa.py.
Keluaran: validation_results/ (laporan teks per graf dan CSV).
"""

import os
import sys

import alat_evaluasi as ae

SEP = "=" * 78


def fmt(x):
    return "n/a" if x is None else f"{x * 100:.2f}%"


def validate_file(path, label, shapes, ont, ps_index):
    data = ae.load_graph(path)
    conforms, report, text = ae.validate(data, shapes, ont)
    counts = ae.severity_counts(report)
    results = ae.results_by_entity(report, ps_index)
    mag = ae.three_magnitudes(report, results)
    verdict = "MELANGGAR" if counts["Violation"] else "PATUH"
    print(f"\n{SEP}\n Validasi pySHACL: {label} ({os.path.basename(path)}, {len(data)} triple)\n{SEP}")
    print(f"Conforms (allow_warnings=True) : {conforms}")
    print(f"Vonis hukum graf (ada sh:Violation?) : {verdict}")
    print(f"Ringkasan severity : {counts['Violation']} Violation | {counts['Warning']} Warning | {counts['Info']} Info")
    print("Tiga besaran (Violation / Warning):")
    for k, name in (("hasil_validasi", "hasil validasi (sh:ValidationResult)"),
                    ("pasangan_terpicu", "pasangan (focus node, unit) terpicu"),
                    ("entitas", "focus node terpicu")):
        print(f"  {name:<40}: {mag['Violation'][k]} / {mag['Warning'][k]}")
    out = os.path.join(ae.OUTPUT_DIR, f"report_{label.lower().replace(' ', '_')}.txt")
    os.makedirs(ae.OUTPUT_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"=== LAPORAN HASIL VALIDASI PYSHACL: {label} ===\n")
        f.write(f"File Data: {os.path.basename(path)} ({len(data)} triple)\n")
        f.write(f"Conforms (allow_warnings=True): {conforms}\n")
        f.write(f"Vonis hukum graf (ada sh:Violation?): {verdict}\n")
        f.write(f"Counts: Violation={counts['Violation']}, Warning={counts['Warning']}, Info={counts['Info']}\n\n")
        f.write("--- DETAIL LAPORAN FORMAL SHACL ---\n")
        f.write(text)
    print(f"Laporan tersimpan di : {out}")
    return data, results, counts


def print_entity_table(rows, id_col):
    print(f"{id_col:<17}{'Entitas':<34}{'V':>3}{'W':>3}{'I':>3}  {'Harapan':<10}{'Prediksi':<10}{'Hasil':<6}Shape sesuai kunci")
    for r in rows:
        print(f"{r[id_col]:<17}{r['entitas']:<34}{r['n_violation']:>3}{r['n_warning']:>3}{r['n_info']:>3}  "
              f"{r['vonis_harapan']:<10}{r['vonis_prediksi']:<10}{r['hasil']:<6}{'ya' if r['shape_sesuai_kunci'] else 'TIDAK'}")


def main():
    shapes, ont = ae.load_graph(ae.SHAPES_PATH), ae.load_graph(ae.ONTOLOGY_PATH)
    ps_index = ae.property_shapes(shapes)

    stats = ae.artifact_stats()
    print(f"{SEP}\n STATISTIK ARTEFAK (dihitung dari berkas)\n{SEP}")
    print(f"NodeShape: {stats['node_shape']} | property shape: {stats['property_shape']} "
          f"{stats['property_shape_per_severity']} | constraint tingkat node: {stats['node_constraint']} "
          f"{stats['node_constraint_per_severity']}")
    for f, n in stats["triple"].items():
        print(f"  {f:<28}{n:>5} triple")

    # --- Integritas data uji ---
    print(f"\n{SEP}\n PEMERIKSAAN INTEGRITAS DATA UJI (bukan vonis hukum)\n{SEP}")
    problems = []
    for group in ((ae.COMPLIANT_PATH, ae.VIOLATION_PATH), (ae.BVA_PATH,)):
        paths = [p for p in group if os.path.exists(p)]
        if not paths:
            continue
        g = ae.load_graph(paths[0])
        for p in paths[1:]:
            g += ae.load_graph(p)
        found = ae.integrity_check(g, ont)
        print(f"{' + '.join(os.path.basename(p) for p in paths)}: {'OK' if not found else f'{len(found)} masalah'}")
        for x in found:
            print(f"  {x}")
        problems += found
    if problems:
        sys.exit(1)

    # --- Desain partisi ECP terhadap kelas batasan ---
    classes, n_multiset = ae.constraint_classes(shapes)
    key = ae.read_key(ae.KEY_ECP_PATH)
    print(f"\n{SEP}\n PEMERIKSAAN PARTISI ECP TERHADAP KELAS BATASAN\n{SEP}")
    print(f"N_constraint = {len(classes)} (multiset: {n_multiset}); "
          f"partisi pada kunci = {len({r['ecp'] for r in key})}")
    part_problems = ae.check_partitions(key, classes)
    print("OK" if not part_problems else f"{len(part_problems)} masalah")
    for x in part_problems:
        print(f"  {x}")
    if part_problems:
        sys.exit(1)

    # --- ECP ---
    results, datas = {}, []
    for path, label in ((ae.COMPLIANT_PATH, "Graf Compliant Arketipe"), (ae.VIOLATION_PATH, "Graf Violation Arketipe")):
        data, res, _ = validate_file(path, label, shapes, ont, ps_index)
        overlap = set(results) & set(res)
        if overlap:
            sys.exit(f"Entitas ganda di beberapa graf: {overlap}")
        results.update(res)
        datas.append(data)

    rows = ae.evaluate_entities(key, results)
    unkeyed = sorted(set(results) - {r["entitas"] for r in rows})
    print(f"\n{SEP}\n EVALUASI PER ENTITAS (FOCUS NODE) — PARTISI ECP\n{SEP}")
    print_entity_table(rows, "ecp")
    if unkeyed:
        print(f"PERINGATAN: entitas dengan hasil validasi tetapi tidak ada di kunci jawaban: {unkeyed}")

    cm = ae.confusion(rows)
    print(f"\n{SEP}\n CONFUSION MATRIX TINGKAT ENTITAS (metrik utama)\n{SEP}")
    print(f"N = {cm['N']} entitas | TP = {cm['TP']} | TN = {cm['TN']} | FP = {cm['FP']} | FN = {cm['FN']}")
    print(f"Akurasi {fmt(cm['accuracy'])} | Presisi {fmt(cm['precision'])} | Recall {fmt(cm['recall'])} | F1 {fmt(cm['f1'])}")

    merged = datas[0] + datas[1]
    agg = ae.aggregate_by_actor(merged, ont, rows)
    print(f"\n{SEP}\n VONIS PER PELAKU (Pengendali/Prosesor/PSE beserta peristiwanya) — tabel pendukung, bukan metrik\n{SEP}")
    print(f"{'ECP':<8}{'Pelaku':<34}{'Peristiwa':>10}{'V':>4}{'W':>4}  {'Harapan':<10}{'Agregat':<10}Sesuai")
    for a in agg:
        print(f"{a['ecp']:<8}{a['pelaku']:<34}{len(a['entitas_terkait']):>10}{a['n_violation']:>4}{a['n_warning']:>4}  "
              f"{a['vonis_harapan']:<10}{a['vonis_agregat']:<10}{'ya' if a['sesuai'] else 'TIDAK'}")

    cov = ae.shape_coverage(ps_index, rows, ae.entity_types(merged, ont))
    print(f"\n{SEP}\n BUKTI CAKUPAN TINGKAT SHAPE (bukan metrik akurasi utama)\n{SEP}")
    print(f"{'Property shape':<76}{'Sev':<10}{'Target':>7}{'Harap':>6}{'Aktual':>7}  Sesuai")
    for c in cov:
        print(f"{c['shape']:<76}{c['severity']:<10}{c['entitas_target']:>7}{c['diharapkan_terpicu']:>6}"
              f"{c['aktual_terpicu']:>7}  {'ya' if c['sesuai_kunci'] else 'TIDAK'}")
    never = [c["shape"] for c in cov if c["aktual_terpicu"] == 0]
    print(f"Property shape yang tidak terpicu oleh entitas ECP mana pun ({len(never)}): {', '.join(never) or '-'}")

    triggered = {c["shape"] for c in cov if c["aktual_terpicu"] > 0}
    print(f"\n{SEP}\n CAKUPAN PER KELAS BATASAN\n{SEP}")
    print(f"{'Kelas':<7}{'ECP':<8}{'Unit':>5}{'Terpicu':>9}  NodeShape")
    for c in classes:
        ecp = sorted({r['ecp'] for r in rows if r.get('kelas_batasan') == c['kelas']})
        print(f"{c['kelas']:<7}{','.join(ecp):<8}{len(c['unit']):>5}{len(set(c['unit']) & triggered):>9}  "
              f"{', '.join(c['node_shape'])}")

    # --- BVA ---
    bva_rows = []
    if os.path.exists(ae.BVA_PATH):
        _, bva_res, _ = validate_file(ae.BVA_PATH, "Graf Uji Batas BVA", shapes, ont, ps_index)
        bva_rows = ae.evaluate_entities(ae.read_key(ae.KEY_BVA_PATH), bva_res)
        print(f"\n{SEP}\n UJI BATAS (BOUNDARY VALUE ANALYSIS) — terpisah dari ECP\n{SEP}")
        print_entity_table(bva_rows, "kasus")
        ok = sum(r["shape_sesuai_kunci"] and r["hasil"] in ("TP", "TN") for r in bva_rows)
        print(f"Kasus sesuai kunci (vonis dan shape): {ok}/{len(bva_rows)}")
    else:
        print(f"\nGraf BVA tidak ditemukan ({ae.BVA_PATH}); jalankan FASE_3_DATASET_SEMANTIK/buat_data_bva.py.")

    # --- Simpan CSV ---
    fields = ["ecp", "kelas_batasan", "peran", "entitas", "berkas", "vonis_harapan", "vonis_prediksi", "hasil", "n_violation", "n_warning",
              "n_info", "shape_sesuai_kunci", "shape_violation_harapan", "shape_violation_aktual",
              "shape_warning_harapan", "shape_warning_aktual"]
    ae.write_csv(os.path.join(ae.OUTPUT_DIR, "vonis_per_entitas_ecp.csv"), rows, fields)
    ae.write_csv(os.path.join(ae.OUTPUT_DIR, "vonis_per_pelaku_ecp.csv"), agg,
                 ["ecp", "pelaku", "entitas_terkait", "n_violation", "n_warning", "vonis_harapan", "vonis_agregat",
                  "sesuai"])
    ae.write_csv(os.path.join(ae.OUTPUT_DIR, "cakupan_shape_ecp.csv"), cov,
                 ["shape", "severity", "node_shape", "entitas_target", "diharapkan_terpicu", "aktual_terpicu",
                  "entitas_terpicu", "sesuai_kunci"])
    if bva_rows:
        ae.write_csv(os.path.join(ae.OUTPUT_DIR, "hasil_uji_batas_bva.csv"), bva_rows,
                     ["kasus"] + [f for f in fields if f != "ecp"])
    print(f"\nCSV tersimpan di {ae.OUTPUT_DIR}")

    mismatch = ([r["entitas"] for r in rows if not r["shape_sesuai_kunci"] or r["hasil"] in ("FP", "FN")]
                + [a["pelaku"] for a in agg if not a["sesuai"]]
                + [r["entitas"] for r in bva_rows if not r["shape_sesuai_kunci"] or r["hasil"] in ("FP", "FN")]
                + unkeyed)
    print(f"\n{SEP}")
    print("SEMUA HASIL SESUAI KUNCI JAWABAN" if not mismatch else f"TIDAK SESUAI KUNCI: {mismatch}")
    print(SEP)
    return 0 if not mismatch else 1


if __name__ == "__main__":
    sys.exit(main())
