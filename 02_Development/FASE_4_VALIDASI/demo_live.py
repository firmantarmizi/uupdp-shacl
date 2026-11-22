"""
Demo langsung untuk bimbingan: ubah SATU nilai pada PSE patuh, lalu lihat vonis pySHACL.
Berkas .ttl asli tidak diubah; perubahan hanya terjadi di memori.

Letakkan di FASE_4_VALIDASI/, lalu contoh:
  python demo_live.py jam 24          -> patuh
  python demo_live.py jam 60          -> patuh + peringatan dini (Warning)
  python demo_live.py jam 96          -> melanggar Pasal 46 ayat (1) (Violation + Warning)
  python demo_live.py jam kosong      -> data tidak diisi -> melanggar Pasal 46 ayat (1) (CWA, pesan "tidak tercatat")
  python demo_live.py keamanan mati   -> melanggar Pasal 35 huruf a dan Pasal 38 (pesan "tercatat belum menerapkan")
  python demo_live.py keamanan kosong -> catatan tidak tersedia -> melanggar (CWA, pesan "catatan ... tidak tersedia")
Skenario enkripsi dihapus 2026-10-28: enkripsi tidak lagi diperiksa (konsensus validator FO-16/FO-30).
"""
import os, sys
import rdflib, pyshacl
from rdflib import Literal, URIRef
from rdflib.namespace import SH, RDF, XSD

BASE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(os.path.dirname(BASE), "FASE_3_DATASET_SEMANTIK")
P = "http://example.org/pdp#"
PSE = URIRef(P + "PSE_Simulasi_FIN_Compliant")
INSIDEN = URIRef(P + "Insiden_FIN")  # kegagalan Pelindungan Data Pribadi milik PSE FIN

if len(sys.argv) < 3:
    print(__doc__); sys.exit(0)
mode, val = sys.argv[1].lower(), sys.argv[2].lower()

g = rdflib.Graph().parse(os.path.join(DS, "data_pse_compliant.ttl"), format="turtle")

if mode == "jam":
    # Tenggat Pasal 46 ayat (1) melekat pada entitas insiden milik PSE (Bagian B).
    prop = URIRef(P + "breachNotificationHours")
    g.remove((INSIDEN, prop, None))
    if val != "kosong":
        g.add((INSIDEN, prop, Literal(int(val), datatype=XSD.integer)))
    print(f"\nSkenario: notifikasi kegagalan Pelindungan Data Pribadi (Pasal 46 ayat (1)) = {val} jam")
elif mode == "keamanan":
    prop = URIRef(P + "hasSecurityMeasures")
    g.remove((PSE, prop, None))
    if val != "kosong":
        g.add((PSE, prop, Literal(val != "mati")))
    status = {"mati": "tidak diterapkan", "kosong": "tidak tercatat"}.get(val, "diterapkan")
    print(f"\nSkenario: langkah teknis operasional keamanan (Pasal 35 huruf a, Pasal 38) = {status}")
else:
    print(__doc__); sys.exit(1)

conforms, rep, _ = pyshacl.validate(
    g, shacl_graph=os.path.join(DS, "shapes_pdp.ttl"), ont_graph=os.path.join(DS, "ontology_pdp.ttl"),
    inference="rdfs", abort_on_first=False, meta_shacl=False, advanced=True)

results = list(rep.subjects(RDF.type, SH.ValidationResult))
n_viol = sum(1 for r in results if rep.value(r, SH.resultSeverity) == SH.Violation)
# Catatan: menurut spesifikasi SHACL, Conforms = False bila ada hasil APA PUN (termasuk Warning).
# Status hukum di bawah hanya digagalkan oleh sh:Violation (setara pyshacl allow_warnings=True).
print("Conforms (standar SHACL) :", conforms)
print("Status kepatuhan hukum   :", "MELANGGAR" if n_viol else "PATUH")
if not results:
    print("Hasil         : tidak ada temuan")
for r in results:
    sev = str(rep.value(r, SH.resultSeverity)).split("#")[-1]
    print(f"[{sev}] {rep.value(r, SH.resultMessage)}")
print()
