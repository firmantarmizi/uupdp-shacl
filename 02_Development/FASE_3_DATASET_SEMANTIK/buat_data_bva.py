"""
Generator graf uji batas (Boundary Value Analysis) untuk kewajiban bertenggat 3 x 24 jam.

Kewajiban bertenggat melekat pada entitas peristiwa pemicu (Bagian B). Untuk setiap kewajiban
(Ps. 30 ayat (1), 32 ayat (2), 40 ayat (2), 41 ayat (1), 46 ayat (1)) dibuat lima entitas peristiwa dengan
nilai 48, 49, 72, 73 jam, dan kosong. Semua peristiwa ditautkan (pdp:responsibleController) ke satu
Pengendali BVA_Pengendali yang tipe dan propertinya disalin dari PSE_Simulasi_FIN_Compliant (patuh penuh,
termasuk ConsentBasedController yang disyaratkan untuk permintaan penarikan persetujuan). Peristiwa insiden
juga diberi isi pemberitahuan lengkap (Ps. 46 ayat (2)) agar hanya satu variabel yang diuji per entitas.

Kunci jawaban diturunkan dari aturan, bukan dari keluaran validator:
  - batas hukum 72 jam (3 x 24 jam): nilai > 72 -> Violation (<X>_WithinLimit)
  - ambang peringatan dini 48 jam (rancangan penelitian): nilai > 48 -> Warning (<X>_EarlyWarning)
  - nilai kosong -> Violation (<X>_Recorded) karena sh:minCount 1 (Closed-World Assumption)
  - BVA_Pengendali -> Compliant tanpa hasil

Keluaran:
  FASE_3_DATASET_SEMANTIK/data_uji_batas_bva.ttl
  FASE_4_VALIDASI/kunci_jawaban_bva.csv
"""

import csv
import os

import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "data_pse_compliant.ttl")
OUT_TTL = os.path.join(HERE, "data_uji_batas_bva.ttl")
OUT_KEY = os.path.join(os.path.dirname(HERE), "FASE_4_VALIDASI", "kunci_jawaban_bva.csv")

P = "http://example.org/pdp#"
BASE_ENTITY = URIRef(P + "PSE_Simulasi_FIN_Compliant")
CONTROLLER = URIRef(P + "BVA_Pengendali")

# (kode, pasal, kelas peristiwa, properti, prefiks property shape)
DEADLINES = [
    ("Ps30", "Pasal 30 ayat (1)", "DataUpdateRequest", "dataUpdateResponseHours", "DataUpdateHours"),
    ("Ps32", "Pasal 32 ayat (2)", "DataAccessRequest", "dataAccessResponseHours", "DataAccessHours"),
    ("Ps40", "Pasal 40 ayat (2)", "ConsentWithdrawalRequest", "processingCessationHours", "ProcessingCessationHours"),
    ("Ps41", "Pasal 41 ayat (1)", "ProcessingRestrictionRequest", "processingRestrictionHours", "ProcessingRestrictionHours"),
    ("Ps46", "Pasal 46 ayat (1)", "BreachIncident", "breachNotificationHours", "BreachNotificationHours"),
]
VALUES = [48, 49, 72, 73, None]  # None = data tidak diisi
LIMIT, WARN = 72, 48

HEADER = """#################################################################
#  DATA GRAF UJI BATAS (BOUNDARY VALUE ANALYSIS)
#  Dibuat oleh buat_data_bva.py; jangan disunting manual.
#  5 kewajiban bertenggat x 5 nilai (48, 49, 72, 73 jam, kosong) = 25 entitas peristiwa,
#  ditautkan ke BVA_Pengendali (salinan PSE_Simulasi_FIN_Compliant, patuh penuh).
#  Graf ini terpisah dari partisi ECP dan tidak dihitung sebagai partisi.
#  Disclaimer: data artifisial murni untuk pengujian.
#################################################################

"""


def expected(prefix, value):
    if value is None:
        return "Violation", [f"{prefix}_Recorded"], []
    viol = [f"{prefix}_WithinLimit"] if value > LIMIT else []
    warn = [f"{prefix}_EarlyWarning"] if value > WARN else []
    return ("Violation" if viol else "Compliant"), viol, warn


def main():
    src = rdflib.Graph().parse(SRC, format="turtle")
    g = rdflib.Graph()
    g.bind("pdp", P)
    g.bind("rdfs", str(RDFS))
    for p, o in src.predicate_objects(BASE_ENTITY):
        if p != RDFS.label:
            g.add((CONTROLLER, p, o))
    g.add((CONTROLLER, RDFS.label, Literal("Pengendali uji batas (salinan PSE FIN, patuh penuh)", lang="id")))
    key = [{"kasus": "BVA-Pengendali", "entitas": "BVA_Pengendali", "berkas": "data_uji_batas_bva.ttl",
            "pasal": "-", "properti": "-", "nilai": "-", "vonis_harapan": "Compliant",
            "shape_violation_harapan": "", "shape_warning_harapan": ""}]
    for code, pasal, cls, prop, prefix in DEADLINES:
        for v in VALUES:
            tag = "kosong" if v is None else f"{v:03d}"
            ent = URIRef(f"{P}BVA_{code}_{tag}")
            g.add((ent, RDF.type, URIRef(P + cls)))
            g.add((ent, URIRef(P + "responsibleController"), CONTROLLER))
            if cls == "BreachIncident":
                g.add((ent, URIRef(P + "breachNotificationContainsRequiredElements"), Literal(True)))
            if v is not None:
                g.add((ent, URIRef(P + prop), Literal(v, datatype=XSD.integer)))
            label = f"Uji batas {pasal}: {'tidak diisi' if v is None else f'{v} jam'}"
            g.add((ent, RDFS.label, Literal(label, lang="id")))
            verdict, viol, warn = expected(prefix, v)
            key.append({"kasus": f"BVA-{code}-{tag}", "entitas": f"BVA_{code}_{tag}",
                        "berkas": "data_uji_batas_bva.ttl", "pasal": pasal, "properti": prop,
                        "nilai": "kosong" if v is None else v, "vonis_harapan": verdict,
                        "shape_violation_harapan": ";".join(viol), "shape_warning_harapan": ";".join(warn)})
    with open(OUT_TTL, "w", encoding="utf-8") as f:
        f.write(HEADER)
        f.write(g.serialize(format="turtle"))
    with open(OUT_KEY, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(key[0].keys()))
        w.writeheader()
        w.writerows(key)
    print(f"{len(key)} entitas -> {OUT_TTL}")
    print(f"kunci jawaban -> {OUT_KEY}")


if __name__ == "__main__":
    main()
