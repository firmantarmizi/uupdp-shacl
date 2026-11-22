"""
Uji mutasi evaluator: membuktikan bahwa run_validation/alat_evaluasi mampu mendeteksi FP, FN,
dan ketidaksesuaian shape, bukan sekadar meloloskan semua kasus.

Setiap mutan mengubah SATU hal di memori (berkas .ttl dan kunci jawaban tidak diubah):
  - mutan data  : mengubah nilai pada graf data, kunci jawaban tetap -> evaluator harus melaporkan FP/FN/shape;
  - mutan shape : mengubah shapes graph, data dan kunci tetap         -> evaluator harus melaporkan FN/shape;
  - mutan kunci : mengubah kunci jawaban, data dan shape tetap        -> evaluator harus melaporkan FP/FN.
Mutan dinyatakan "terdeteksi" bila evaluator melaporkan jenis temuan yang diharapkan pada entitas yang dimutasi.
Baseline (tanpa mutasi) harus tanpa temuan.

Jalankan: ..\\..\\.venv\\Scripts\\python.exe uji_mutasi.py
Keluaran: validation_results/uji_mutasi.csv
"""

import copy
import os
import sys

import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, SH, XSD

import alat_evaluasi as ae

P = "http://example.org/pdp#"
PDPS = "http://example.org/pdp/shapes#"


def u(name, ns=P):
    return URIRef(ns + name)


def set_value(g, ent, prop, value):
    g.remove((u(ent), u(prop), None))
    if value is not None:
        g.add((u(ent), u(prop), value))


def evaluate(data, shapes, ont, key):
    ps_index = ae.property_shapes(shapes)
    _, report, _ = ae.validate(data, shapes, ont)
    rows = ae.evaluate_entities(key, ae.results_by_entity(report, ps_index))
    return {r["entitas"]: r for r in rows}


def findings(rows):
    """Temuan per entitas: 'FP', 'FN', atau 'SHAPE' (vonis benar tetapi shape tidak sesuai kunci)."""
    out = {}
    for ent, r in rows.items():
        if r["hasil"] in ("FP", "FN"):
            out[ent] = r["hasil"]
        elif not r["shape_sesuai_kunci"]:
            out[ent] = "SHAPE"
    return out


def drop_or_member(shapes, node_shape, index):
    """Menghapus satu anggota daftar sh:or pada NodeShape (mis. cabang sh:not pada implikasi Pasal 45)."""
    from rdflib.collection import Collection
    lst = shapes.value(u(node_shape, PDPS), SH["or"])
    col = Collection(shapes, lst)
    del col[index]


def remove_property_shape(shapes, node_shape, path):
    ns = u(node_shape, PDPS)
    for ps in list(shapes.objects(ns, SH.property)):
        if shapes.value(ps, SH.path) == u(path):
            shapes.remove((ns, SH.property, ps))
            for t in list(shapes.triples((ps, None, None))):
                shapes.remove(t)


def main():
    shapes0, ont = ae.load_graph(ae.SHAPES_PATH), ae.load_graph(ae.ONTOLOGY_PATH)
    data0 = ae.load_graph(ae.COMPLIANT_PATH) + ae.load_graph(ae.VIOLATION_PATH)
    key0 = ae.read_key(ae.KEY_ECP_PATH)

    T, F = Literal(True), Literal(False)
    H = lambda n: Literal(n, datatype=XSD.integer)  # noqa: E731

    # (id, jenis, deskripsi, entitas sasaran, temuan yang diharapkan, fungsi mutasi(data, shapes, key))
    mutants = [
        # MD-01 dan MD-10 diganti 2026-10-28 (semula hasEncryption true -> false; enkripsi tidak lagi diperiksa).
        ("MD-01", "data", "FIN_Compliant: hasSecurityMeasures true -> false (Ps. 35 huruf a, 38)", "PSE_Simulasi_FIN_Compliant", "FP",
         lambda d, s, k: set_value(d, "PSE_Simulasi_FIN_Compliant", "hasSecurityMeasures", F)),
        ("MD-02", "data", "Insiden_FIN: breachNotificationHours dihapus (data kosong)", "Insiden_FIN", "FP",
         lambda d, s, k: set_value(d, "Insiden_FIN", "breachNotificationHours", None)),
        ("MD-03", "data", "Insiden_ECM: breachNotificationHours 58 -> 73", "Insiden_ECM", "FP",
         lambda d, s, k: set_value(d, "Insiden_ECM", "breachNotificationHours", H(73))),
        ("MD-04", "data", "CLD_Compliant: processesOnlyUnderInstruction true -> false", "Prosesor_Simulasi_CLD_Compliant", "FP",
         lambda d, s, k: set_value(d, "Prosesor_Simulasi_CLD_Compliant", "processesOnlyUnderInstruction", F)),
        ("MD-05", "data", "Insiden_ECP07_Lewat: breachNotificationHours 144 -> 24", "Insiden_ECP07_Lewat", "FN",
         lambda d, s, k: set_value(d, "Insiden_ECP07_Lewat", "breachNotificationHours", H(24))),
        ("MD-06", "data", "ILLEGAL_Violation: hasUnauthorizedProcessing true -> false", "PSE_Simulasi_ILLEGAL_Violation", "FN",
         lambda d, s, k: set_value(d, "PSE_Simulasi_ILLEGAL_Violation", "hasUnauthorizedProcessing", F)),
        ("MD-07", "data", "CNS_Violation: hasConsentEvidence false -> true (vonis tetap Violation)", "PSE_Simulasi_CNS_Violation", "SHAPE",
         lambda d, s, k: set_value(d, "PSE_Simulasi_CNS_Violation", "hasConsentEvidence", T)),
        ("MD-08", "data", "ANK_Violation: kelas pemicu ChildDataController dihapus", "PSE_Simulasi_ANK_Violation", "FN",
         lambda d, s, k: d.remove((u("PSE_Simulasi_ANK_Violation"), RDF.type, u("ChildDataController")))),
        ("MD-09", "data", "Transfer_ECP18: entitas peristiwa transfer dihapus", "Transfer_ECP18", "FN",
         lambda d, s, k: d.remove((u("Transfer_ECP18"), None, None))),
        ("MD-10", "data", "CLD_Compliant: hasAccessControl true -> false (Ps. 39 ayat (1) jo. 52)", "Prosesor_Simulasi_CLD_Compliant", "FP",
         lambda d, s, k: set_value(d, "Prosesor_Simulasi_CLD_Compliant", "hasAccessControl", F)),
        ("MD-11", "data", "CLD_Violation: processesOnlyUnderInstruction false -> true", "Prosesor_Simulasi_CLD_Violation", "FN",
         lambda d, s, k: set_value(d, "Prosesor_Simulasi_CLD_Violation", "processesOnlyUnderInstruction", T)),
        ("MD-12", "data", "AksiKorporasi_FIN: transferNoticeAfterAction true -> false", "AksiKorporasi_FIN", "FP",
         lambda d, s, k: set_value(d, "AksiKorporasi_FIN", "transferNoticeAfterAction", F)),
        ("MD-13", "data", "DPO_Violation: pemicu LargeScaleMonitoringActor (huruf b) dihapus", "PSE_Simulasi_DPO_Violation", "FN",
         lambda d, s, k: d.remove((u("PSE_Simulasi_DPO_Violation"), RDF.type, u("LargeScaleMonitoringActor")))),
        ("MD-14", "data", "Penghapusan_FIN: erasureCarriedOut true -> false", "Penghapusan_FIN", "FP",
         lambda d, s, k: set_value(d, "Penghapusan_FIN", "erasureCarriedOut", F)),
        ("MD-15", "data", "Pengakhiran_ECP16: processingTerminated false -> true", "Pengakhiran_ECP16", "FN",
         lambda d, s, k: set_value(d, "Pengakhiran_ECP16", "processingTerminated", T)),
        ("MD-16", "data", "FIN_Compliant: hasSecurityMeasures dihapus (catatan tidak tersedia)", "PSE_Simulasi_FIN_Compliant", "FP",
         lambda d, s, k: set_value(d, "PSE_Simulasi_FIN_Compliant", "hasSecurityMeasures", None)),
        ("MS-01", "shape", "BreachNotificationHours_WithinLimit: maxInclusive 72 -> 200", "Insiden_ECP07_Lewat", "FN",
         lambda d, s, k: (s.remove((u("BreachNotificationHours_WithinLimit", PDPS), SH.maxInclusive, None)),
                          s.add((u("BreachNotificationHours_WithinLimit", PDPS), SH.maxInclusive, H(200))))),
        ("MS-02", "shape", "DPIAShape: severity Violation -> Warning", "PSE_Simulasi_HLT_Violation", "FN",
         lambda d, s, k: [(s.remove((ps, SH.severity, None)), s.add((ps, SH.severity, SH.Warning)))
                          for ps in list(s.objects(u("DPIAShape", PDPS), SH.property))]),
        ("MS-03", "shape", "UnauthorizedProcessingShape: property shape dihapus", "PSE_Simulasi_ILLEGAL_Violation", "FN",
         lambda d, s, k: remove_property_shape(s, "UnauthorizedProcessingShape", "hasUnauthorizedProcessing")),
        ("MS-04", "shape", "DataUpdateHours_EarlyWarning: maxInclusive 48 -> 60", "Permintaan_Pembaruan_ECM", "SHAPE",
         lambda d, s, k: (s.remove((u("DataUpdateHours_EarlyWarning", PDPS), SH.maxInclusive, None)),
                          s.add((u("DataUpdateHours_EarlyWarning", PDPS), SH.maxInclusive, H(60))))),
        ("MS-05", "shape", "SecurityMeasuresShape: target pdp:DataProcessor dihapus", "Prosesor_Simulasi_SEC_Violation", "SHAPE",
         lambda d, s, k: s.remove((u("SecurityMeasuresShape", PDPS), SH.targetClass, u("DataProcessor")))),
        ("MS-06", "shape", "DataProtectionOfficerShape: target dipersempit ke huruf a saja", "PSE_Simulasi_DPO_Violation", "FN",
         lambda d, s, k: (s.remove((u("DataProtectionOfficerShape", PDPS), SH.targetClass, None)),
                          s.add((u("DataProtectionOfficerShape", PDPS), SH.targetClass, u("PublicServiceProcessingActor"))))),
        ("MS-07", "shape", "DeletionNoticeShape: cabang sh:not dihapus (pemberitahuan selalu wajib)", "Penghapusan_ECP24", "SHAPE",
         lambda d, s, k: drop_or_member(s, "DeletionNoticeShape", 0)),
        ("MK-01", "kunci", "Kunci ECP-09 HLT: vonis Violation -> Compliant", "PSE_Simulasi_HLT_Violation", "FP",
         lambda d, s, k: next(r for r in k if r["entitas"] == "PSE_Simulasi_HLT_Violation").update(vonis_harapan="Compliant")),
        ("MK-02", "kunci", "Kunci ECP-01 FIN: vonis Compliant -> Violation", "PSE_Simulasi_FIN_Compliant", "FN",
         lambda d, s, k: next(r for r in k if r["entitas"] == "PSE_Simulasi_FIN_Compliant").update(vonis_harapan="Violation")),
    ]

    base = findings(evaluate(data0, shapes0, ont, key0))
    print(f"Baseline (tanpa mutasi): {'tanpa temuan' if not base else base}")
    if base:
        sys.exit("Baseline tidak bersih; uji mutasi tidak valid.")

    rows = []
    for mid, kind, desc, target, expected, mutate in mutants:
        d, s, k = copy.deepcopy(data0), copy.deepcopy(shapes0), copy.deepcopy(key0)
        mutate(d, s, k)
        got = findings(evaluate(d, s, ont, k))
        detected = got.get(target) == expected
        others = {e: v for e, v in got.items() if e != target}
        rows.append({"mutan": mid, "jenis": kind, "deskripsi": desc, "entitas_sasaran": target,
                     "temuan_diharapkan": expected, "temuan_aktual": got.get(target, "-"),
                     "terdeteksi": detected, "temuan_lain": ";".join(f"{e}={v}" for e, v in others.items())})
        print(f"{mid:<6}{kind:<6}{desc:<72} harap {expected:<5} aktual {got.get(target, '-'):<5} "
              f"{'TERDETEKSI' if detected else 'LOLOS'}{'  lain: ' + str(others) if others else ''}")

    killed = sum(r["terdeteksi"] for r in rows)
    print(f"\nSkor mutasi: {killed}/{len(rows)} mutan terdeteksi")
    ae.write_csv(os.path.join(ae.OUTPUT_DIR, "uji_mutasi.csv"), rows, list(rows[0].keys()))
    print(f"Tersimpan di {os.path.join(ae.OUTPUT_DIR, 'uji_mutasi.csv')}")
    return 0 if killed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
