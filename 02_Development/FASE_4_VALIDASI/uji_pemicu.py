"""
Uji pemicu kewajiban bersyarat (Bagian B), seluruhnya di memori.

K00 adalah Pengendali tanpa pemicu: hanya memiliki properti kewajiban yang berlaku umum, tanpa kelas pemicu,
tanpa permintaan, tanpa insiden, tanpa transfer ke luar wilayah hukum RI, dan tanpa Prosesor.
Kasus K01-K22 menambahkan SATU pemicu pada K00 TANPA properti kewajibannya. Harapan (rancangan bersyarat):
  - K00 tidak menghasilkan hasil apa pun;
  - setiap kasus pemicu menghasilkan tepat shape kewajiban yang terkait dengan pemicu itu.

Skrip yang sama dijalankan terhadap shapes/ontologi lama (sebelum Bagian B) untuk analisis desain
"pemodelan tanpa kondisi vs dengan kondisi"; format CSV kedua run identik.

Contoh:
  ..\\..\\.venv\\Scripts\\python.exe uji_pemicu.py
  ..\\..\\.venv\\Scripts\\python.exe uji_pemicu.py --shapes <shapes lama> --ontologi <ontologi lama>
      --keluaran validation_results\\uji_pemicu_sebelum.csv --label "sebelum Bagian B"
Kode keluar 1 bila ada kasus yang tidak sesuai harapan atau pemeriksaan integritas gagal.
"""

import argparse
import os
import sys

import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, XSD

import alat_evaluasi as ae

P = ae.PDP
T = Literal(True)

# Properti kewajiban yang berlaku umum bagi Pengendali (tanpa syarat). hasEncryption tidak termasuk sejak
# 2026-10-28 (konsensus validator FO-16/FO-30: enkripsi bukan syarat wajib Pasal 35).
K0_PROPS = [
    ("hasAccessControl", T), ("hasSecurityMeasures", T),
    ("hasConfidentialityMeasures", T), ("hasSupervisionMechanism", T), ("hasElectronicSecuritySystem", T),
    ("hasProcessingAuditLog", T), ("hasLegalBasis", Literal("contract")), ("hasDataMinimization", T),
    ("hasDataAccuracyVerification", T), ("hasRetentionPeriod", Literal(365, datatype=XSD.integer)),
    ("hasUnauthorizedProcessing", Literal(False)),
]
K0 = "UjiPemicu_Pengendali"


def u(name):
    return URIRef(P + name)


def base_graph():
    g = rdflib.Graph()
    g.add((u(K0), RDF.type, u("DataController")))
    g.add((u(K0), RDF.type, u("PSE")))
    for p, o in K0_PROPS:
        g.add((u(K0), u(p), o))
    return g


def add_class(cls, legal_basis=None):
    def f(g):
        g.add((u(K0), RDF.type, u(cls)))
        if legal_basis:
            g.set((u(K0), u("hasLegalBasis"), Literal(legal_basis)))
    return f


def add_event(cls, name):
    def f(g):
        g.add((u(name), RDF.type, u(cls)))
        g.add((u(name), u("responsibleController"), u(K0)))
    return f


def add_withdrawal(g):
    """Penarikan kembali persetujuan mengandaikan dasar persetujuan (Pasal 40 ayat (1)), sehingga K0 dijadikan
    ConsentBasedController dengan kewajiban Pasal 21 ayat (1) dan Pasal 24 terpenuhi; yang diuji hanya tenggat."""
    add_class("ConsentBasedController", "consent")(g)
    g.add((u(K0), u("hasConsentEvidence"), T))
    g.add((u(K0), u("hasProcessingNotice"), T))
    add_event("ConsentWithdrawalRequest", "UjiPemicu_PenarikanPersetujuan")(g)


def add_child(g):
    """Data anak adalah Data Pribadi spesifik (Pasal 4 ayat (2) huruf e), sehingga pemrosesannya berisiko tinggi
    (Pasal 34 ayat (2) huruf b; aturan integritas (f2)). K0 dijadikan HighRiskProcessingController dengan
    penilaian dampak terpenuhi; yang diuji hanya kewajiban Pasal 25 ayat (2)."""
    add_class("ChildDataController")(g)
    add_class("HighRiskProcessingController")(g)
    g.add((u(K0), u("hasDPIA"), T))


def add_processor(g):
    ent = u("UjiPemicu_Prosesor")
    g.add((ent, RDF.type, u("DataProcessor")))
    g.add((ent, RDF.type, u("PSE")))
    g.add((ent, u("hasUnauthorizedProcessing"), Literal(False)))


def add_dpo(cls, high_risk=False):
    """Satu huruf pemicu Pasal 53 ayat (1) saja (huruf a/b/c alternatif, Putusan MK 151/PUU-XXII/2024).
    Untuk huruf b dan c, K0 juga HighRiskProcessingController dengan penilaian dampak terpenuhi (aturan (f3))."""
    def f(g):
        add_class(cls)(g)
        if high_risk:
            add_class("HighRiskProcessingController")(g)
            g.add((u(K0), u("hasDPIA"), T))
    return f


def add_erasure_done(g):
    """Penghapusan telah dilakukan (Pasal 43 ayat (1) dipenuhi) tanpa pemberitahuan; yang diuji hanya Pasal 45."""
    add_event("DeletionGround", "UjiPemicu_PenghapusanDilakukan")(g)
    g.add((u("UjiPemicu_PenghapusanDilakukan"), u("erasureCarriedOut"), T))


def add_processor_dpo(g):
    """Prosesor yang memenuhi seluruh kewajiban Prosesor (Ps. 51 ayat (1), grup Ps. 52) dan memenuhi huruf a."""
    ent = u("UjiPemicu_ProsesorPelayananPublik")
    for cls in ("DataProcessor", "PSE", "PublicServiceProcessingActor"):
        g.add((ent, RDF.type, u(cls)))
    for p in ("processesOnlyUnderInstruction", "hasAccessControl", "hasSecurityMeasures",
              "hasConfidentialityMeasures", "hasSupervisionMechanism", "hasElectronicSecuritySystem",
              "hasProcessingAuditLog", "hasDataAccuracyVerification"):
        g.add((ent, u(p), T))
    g.add((ent, u("hasUnauthorizedProcessing"), Literal(False)))


# Prosesor tanpa properti kewajiban: tujuh catatan grup Ps. 52 tidak tersedia (pola catatan wajib, 2026-10-28).
P52 = ["SecurityMeasures_Recorded", "AccessControl_Recorded", "ConfidentialityMeasures_Recorded",
       "SupervisionMechanism_Recorded", "ElectronicSecuritySystem_Recorded", "ProcessingAuditLog_Recorded",
       "DataAccuracyVerification_Recorded"]

# (kasus, deskripsi, pemicu, fungsi penambah, shape Violation yang diharapkan pada rancangan bersyarat)
CASES = [
    ("K00", "Pengendali tanpa pemicu", "-", lambda g: None, []),
    ("K01", "Pemrosesan oleh 2 atau lebih Pengendali", "Ps. 18 ayat (2)",
     add_class("JointController"), ["JointControllerShape:hasJointControllerAgreement"]),
    ("K02", "Dasar pemrosesan persetujuan", "Ps. 21 ayat (1); Ps. 24 (interpretasi peneliti)",
     add_class("ConsentBasedController", "consent"),
     ["ConsentEvidenceShape:hasConsentEvidence", "ProcessingNoticeShape:hasProcessingNotice"]),
    ("K03", "Pemrosesan data pribadi anak", "Ps. 25 ayat (2)",
     add_child, ["ChildConsentShape:hasParentalConsentForChild"]),
    ("K04", "Pemrosesan data pribadi penyandang disabilitas", "Ps. 26 ayat (3)",
     add_class("DisabilityDataController"), ["DisabilityConsentShape:hasSpecialConsentForDisability"]),
    ("K05", "Pemrosesan berpotensi risiko tinggi", "Ps. 34 ayat (1)",
     add_class("HighRiskProcessingController"), ["DPIAShape:hasDPIA"]),
    ("K06", "Permintaan pembaruan/perbaikan diterima", "Ps. 30 ayat (1)",
     add_event("DataUpdateRequest", "UjiPemicu_PermintaanPembaruan"), ["DataUpdateHours_Recorded"]),
    ("K07", "Permintaan akses diterima", "Ps. 32 ayat (2)",
     add_event("DataAccessRequest", "UjiPemicu_PermintaanAkses"), ["DataAccessHours_Recorded"]),
    ("K08", "Permintaan penarikan kembali persetujuan diterima", "Ps. 40 ayat (2)",
     add_withdrawal, ["ProcessingCessationHours_Recorded"]),
    ("K09", "Permintaan penundaan dan pembatasan diterima", "Ps. 41 ayat (1)",
     add_event("ProcessingRestrictionRequest", "UjiPemicu_PermintaanPembatasan"),
     ["ProcessingRestrictionHours_Recorded"]),
    ("K10", "Terjadi kegagalan Pelindungan Data Pribadi", "Ps. 46 ayat (1)-(2)",
     add_event("BreachIncident", "UjiPemicu_Insiden"),
     ["BreachNotificationContentShape:breachNotificationContainsRequiredElements", "BreachNotificationHours_Recorded"]),
    ("K11", "Transfer ke luar wilayah hukum RI", "Ps. 56 ayat (2)-(4)",
     add_event("CrossBorderTransfer", "UjiPemicu_Transfer"), ["InternationalTransferShape"]),
    ("K12", "Pengendali menunjuk Prosesor (Prosesor tanpa properti kewajiban)", "Ps. 51 ayat (1); Ps. 52",
     add_processor, sorted(["ProcessorInstructionShape:processesOnlyUnderInstruction"] + P52)),
    ("K13", "Aksi korporasi badan hukum Pengendali (selesai)", "Ps. 48 ayat (1)-(2)",
     add_event("CorporateAction", "UjiPemicu_AksiKorporasi"),
     ["CorporateActionNoticeShape:transferNoticeAfterAction", "CorporateActionNoticeShape:transferNoticeBeforeAction"]),
    ("K14", "Pemrosesan untuk kepentingan pelayanan publik (huruf a saja)", "Ps. 53 ayat (1) huruf a",
     add_dpo("PublicServiceProcessingActor"), ["DataProtectionOfficerShape:hasDataProtectionOfficer"]),
    ("K15", "Pemantauan teratur dan sistematis skala besar (huruf b saja)", "Ps. 53 ayat (1) huruf b",
     add_dpo("LargeScaleMonitoringActor", high_risk=True), ["DataProtectionOfficerShape:hasDataProtectionOfficer"]),
    ("K16", "Pemrosesan skala besar Data Pribadi spesifik (huruf c saja)", "Ps. 53 ayat (1) huruf c",
     add_dpo("LargeScaleSpecificDataActor", high_risk=True), ["DataProtectionOfficerShape:hasDataProtectionOfficer"]),
    ("K17", "Prosesor patuh dengan pemrosesan pelayanan publik (huruf a)", "Ps. 53 ayat (1) huruf a (Prosesor)",
     add_processor_dpo, ["DataProtectionOfficerShape:hasDataProtectionOfficer"]),
    ("K18", "Permintaan Subjek atas data dalam format terstruktur", "Ps. 13 ayat (1) (interpretasi peneliti)",
     add_event("DataPortabilityRequest", "UjiPemicu_PermintaanPortabilitas"),
     ["DataPortabilityShape:portableFormatProvided"]),
    ("K19", "Kondisi pengakhiran pemrosesan terpenuhi", "Ps. 42 ayat (1)",
     add_event("ProcessingTerminationGround", "UjiPemicu_KondisiPengakhiran"),
     ["ProcessingTerminationShape:processingTerminated"]),
    ("K20", "Kondisi penghapusan terpenuhi (belum dihapus, tanpa pemberitahuan)", "Ps. 43 ayat (1); Ps. 45",
     add_event("DeletionGround", "UjiPemicu_KondisiPenghapusan"), ["DataDeletionShape:erasureCarriedOut"]),
    ("K21", "Kondisi pemusnahan terpenuhi (belum dimusnahkan, tanpa pemberitahuan)", "Ps. 44 ayat (1); Ps. 45",
     add_event("DestructionGround", "UjiPemicu_KondisiPemusnahan"), ["DataDestructionShape:erasureCarriedOut"]),
    ("K22", "Penghapusan dilakukan tanpa pemberitahuan kepada Subjek", "Ps. 45",
     add_erasure_done, ["DeletionNoticeShape"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shapes", default=ae.SHAPES_PATH)
    ap.add_argument("--ontologi", default=ae.ONTOLOGY_PATH)
    ap.add_argument("--keluaran", default=os.path.join(ae.OUTPUT_DIR, "uji_pemicu.csv"))
    ap.add_argument("--label", default="sesudah Bagian B")
    args = ap.parse_args()

    shapes, ont = ae.load_graph(args.shapes), ae.load_graph(args.ontologi)
    ps_index = ae.property_shapes(shapes)
    rows, bad = [], 0
    print(f"Uji pemicu ({args.label}); shapes: {os.path.basename(args.shapes)}")
    for kid, desc, trig, add, expected in CASES:
        g = base_graph()
        add(g)
        problems = ae.integrity_check(g, ont)
        _, report, _ = ae.validate(g, shapes, ont)
        res = ae.results_by_entity(report, ps_index)
        # Satu property shape dapat menghasilkan > 1 hasil (mis. sh:minCount dan sh:hasValue sama-sama gagal
        # bila nilai kosong), sehingga perbandingan memakai himpunan shape unik; jumlah hasil mentah tetap dicatat.
        viol = [s for r in res.values() for s in r["Violation"]]
        warn = [s for r in res.values() for s in r["Warning"]]
        viol_u = sorted(set(viol))
        focus = sorted(e for e, r in res.items() if r["Violation"] or r["Warning"] or r["Info"])
        ok = viol_u == sorted(expected) and not warn and not problems
        bad += not ok
        rows.append({"label": args.label, "kasus": kid, "deskripsi": desc, "pemicu": trig,
                     "n_hasil_violation": len(viol), "n_shape_violation": len(viol_u), "n_hasil_warning": len(warn),
                     "shape_violation_harapan": sorted(expected), "shape_violation_aktual": viol_u,
                     "shape_warning_aktual": sorted(set(warn)), "focus_node_terpicu": focus,
                     "integritas": "; ".join(problems) or "OK", "sesuai_harapan": ok})
        print(f"{kid}  {desc:<66} shape V={len(viol_u):>2} (hasil {len(viol):>2}) W={len(warn):>2}  "
              f"{'sesuai' if ok else 'TIDAK SESUAI'}")
    ae.write_csv(args.keluaran, rows, list(rows[0].keys()))
    print(f"\nKasus sesuai harapan rancangan bersyarat: {len(rows) - bad}/{len(rows)}")
    print(f"Tersimpan di {args.keluaran}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
