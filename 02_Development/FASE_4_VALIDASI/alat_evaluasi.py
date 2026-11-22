"""
Fungsi bersama untuk evaluasi validasi pySHACL per focus node.

Dipakai oleh run_validation.py, evaluasi_per_entitas.py, dan ukur_performa.py.
Konvensi identitas unit constraint:
  - property shape bernama (IRI)  -> nama lokal IRI, mis. "DataUpdateHours_WithinLimit"
  - property shape anonim (bnode) -> "<NodeShape>:<path>", mis. "SecurityMeasuresShape:hasEncryption"
  - constraint tingkat node (sh:or/sh:and/sh:not/sh:xone langsung pada NodeShape) -> nama NodeShape,
    mis. "InternationalTransferShape" (hasil tanpa sh:resultPath)
"""

import csv
import os
from collections import defaultdict

import pyshacl
import rdflib
from rdflib import BNode, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF, RDFS, SH

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEV_DIR = os.path.dirname(BASE_DIR)
DATASET_DIR = os.path.join(DEV_DIR, "FASE_3_DATASET_SEMANTIK")
OUTPUT_DIR = os.path.join(BASE_DIR, "validation_results")

ONTOLOGY_PATH = os.path.join(DATASET_DIR, "ontology_pdp.ttl")
SHAPES_PATH = os.path.join(DATASET_DIR, "shapes_pdp.ttl")
COMPLIANT_PATH = os.path.join(DATASET_DIR, "data_pse_compliant.ttl")
VIOLATION_PATH = os.path.join(DATASET_DIR, "data_pse_violation.ttl")
BVA_PATH = os.path.join(DATASET_DIR, "data_uji_batas_bva.ttl")
KEY_ECP_PATH = os.path.join(BASE_DIR, "kunci_jawaban_ecp.csv")
KEY_BVA_PATH = os.path.join(BASE_DIR, "kunci_jawaban_bva.csv")

PDP = "http://example.org/pdp#"
SEVERITIES = ("Violation", "Warning", "Info")
NODE_LEVEL = (SH["or"], SH["and"], SH["not"], SH.xone)
# Kelas peristiwa pemicu (beserta subkelasnya) dan properti tautannya ke Pengendali.
EVENT_CLASSES = ("DataRequest", "BreachIncident", "CrossBorderTransfer", "CorporateAction", "ProcessingTerminationGround",
                 "ErasureGround")
# Pemicu Pasal 53 ayat (1) (Pengendali dan Prosesor): superkelas target dan subkelas huruf b/c yang juga
# berarti pemrosesan berisiko tinggi bagi Pengendali (aturan integritas (f3)).
DPO_TRIGGER = "DPORequiredActor"
DPO_HIGH_RISK = ("LargeScaleMonitoringActor", "LargeScaleSpecificDataActor")
LINK = rdflib.URIRef(PDP + "responsibleController")
PROCESSES = rdflib.URIRef(PDP + "processesPersonalData")
# Atribut yang tidak termasuk pola constraint (definisi kelas batasan).
NON_CONSTRAINT = (SH.path, SH.name, SH.message, SH.description, SH.order, SH.group, RDFS.label, RDFS.comment)


def local(term):
    return str(term).split("#")[-1]


def load_graph(path):
    # Dibaca lewat open(): rdflib memperlakukan path Windows yang panjang (> MAX_PATH) sebagai URL.
    with open(path, "rb") as f:
        return rdflib.Graph().parse(file=f, format="turtle")


def validate(data_graph, shapes_graph, ont_graph):
    """Validasi standar penelitian: inferensi RDFS, tanpa OWL, allow_warnings=True.

    allow_warnings=True: menurut spesifikasi SHACL, Conforms bernilai False bila ada hasil apa pun.
    Vonis hukum ditentukan oleh sh:Violation, sehingga sh:Warning tidak boleh menggagalkan Conforms.
    Hasil sh:Warning tetap tercatat di report graph.
    """
    conforms, report_graph, report_text = pyshacl.validate(
        data_graph, shacl_graph=shapes_graph, ont_graph=ont_graph, inference="rdfs",
        allow_warnings=True, abort_on_first=False, meta_shacl=False, advanced=True, debug=False)
    return conforms, report_graph, report_text


def property_shapes(shapes_graph):
    """Daftar unit constraint: {node: dict(id, kind, node_shape, path, severity, targets)}.

    kind = "property" untuk property shape (sh:property) dan "node" untuk constraint logis yang
    melekat langsung pada NodeShape (mis. sh:or berjenjang Ps. 56 ayat (2)-(4)).
    """
    out = {}
    for ns in shapes_graph.subjects(RDF.type, SH.NodeShape):
        targets = [local(t) for t in shapes_graph.objects(ns, SH.targetClass)]
        for ps in shapes_graph.objects(ns, SH.property):
            path = local(shapes_graph.value(ps, SH.path))
            pid = local(ps) if isinstance(ps, URIRef) else f"{local(ns)}:{path}"
            out[ps] = {"id": pid, "kind": "property", "node_shape": local(ns), "path": path,
                       "severity": local(shapes_graph.value(ps, SH.severity)), "targets": targets}
        if any((ns, p, None) in shapes_graph for p in NODE_LEVEL):
            sev = shapes_graph.value(ns, SH.severity)
            out[ns] = {"id": local(ns), "kind": "node", "node_shape": local(ns), "path": "-",
                       "severity": local(sev) if sev is not None else "Violation", "targets": targets}
    return out


def shape_id_of(report_graph, result, ps_index):
    """Identitas property shape sumber suatu hasil. Bnode di report graph dicocokkan lewat path + severity + focus."""
    src = report_graph.value(result, SH.sourceShape)
    if src in ps_index:
        return ps_index[src]["id"]
    path = local(report_graph.value(result, SH.resultPath))
    sev = local(report_graph.value(result, SH.resultSeverity))
    cands = sorted({v["id"] for v in ps_index.values() if v["path"] == path and v["severity"] == sev})
    if len(cands) != 1:
        raise ValueError(f"Property shape sumber ambigu untuk path={path}, severity={sev}: {cands}")
    return cands[0]


def results_by_entity(report_graph, ps_index):
    """{entitas: {"Violation": [id, ...], "Warning": [...], "Info": [...]}} dari report graph."""
    res = defaultdict(lambda: {s: [] for s in SEVERITIES})
    for r in report_graph.subjects(RDF.type, SH.ValidationResult):
        ent = local(report_graph.value(r, SH.focusNode))
        sev = local(report_graph.value(r, SH.resultSeverity))
        res[ent][sev].append(shape_id_of(report_graph, r, ps_index))
    return res


def severity_counts(report_graph):
    counts = {s: 0 for s in SEVERITIES}
    for r in report_graph.subjects(RDF.type, SH.ValidationResult):
        counts[local(report_graph.value(r, SH.resultSeverity))] += 1
    return counts


def read_key(path):
    """Kunci jawaban CSV (UTF-8). Kolom daftar shape dipisah ';'."""
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            for col in ("shape_violation_harapan", "shape_warning_harapan"):
                row[col] = sorted(x.strip() for x in row[col].split(";") if x.strip())
            rows.append(row)
    return rows


def evaluate_entities(key_rows, results):
    """Bandingkan kunci jawaban dengan hasil per entitas. Vonis: Violation bila ada >= 1 sh:Violation."""
    rows = []
    for k in key_rows:
        got = results.get(k["entitas"], {s: [] for s in SEVERITIES})
        predicted = "Violation" if got["Violation"] else "Compliant"
        expected = k["vonis_harapan"]
        if expected == "Violation":
            outcome = "TP" if predicted == "Violation" else "FN"
        else:
            outcome = "TN" if predicted == "Compliant" else "FP"
        rows.append({
            **k,
            "vonis_prediksi": predicted,
            "hasil": outcome,
            "n_violation": len(got["Violation"]),
            "n_warning": len(got["Warning"]),
            "n_info": len(got["Info"]),
            "shape_violation_aktual": sorted(got["Violation"]),
            "shape_warning_aktual": sorted(got["Warning"]),
            "shape_sesuai_kunci": (sorted(got["Violation"]) == k["shape_violation_harapan"]
                                   and sorted(got["Warning"]) == k["shape_warning_harapan"]
                                   and not got["Info"]),
        })
    return rows


def confusion(rows):
    c = {o: sum(r["hasil"] == o for r in rows) for o in ("TP", "TN", "FP", "FN")}
    tp, tn, fp, fn = c["TP"], c["TN"], c["FP"], c["FN"]
    n = tp + tn + fp + fn
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    return {**c, "N": n, "accuracy": (tp + tn) / n if n else None,
            "precision": precision, "recall": recall, "f1": f1}


def class_closure(ont_graph):
    """Fungsi cls -> {cls dan semua superkelasnya} menurut rdfs:subClassOf di ontologi."""
    sub = defaultdict(set)
    for c, p in ont_graph.subject_objects(RDFS.subClassOf):
        sub[local(c)].add(local(p))

    def closure(cls):
        seen, stack = set(), [cls]
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(sub.get(x, ()))
        return seen
    return closure


def entity_types(data_graph, ont_graph):
    """Tipe entitas yang ditulis eksplisit (rdf:type) setelah penutupan rdfs:subClassOf.

    Tipe dari rdfs:domain/rdfs:range sengaja tidak dihitung; integrity_check() memastikan
    inferensi tersebut tidak menambah tipe baru, sehingga hasilnya setara inferensi RDFS pySHACL.
    """
    closure = class_closure(ont_graph)
    types = defaultdict(set)
    for s, o in data_graph.subject_objects(RDF.type):
        types[local(s)] |= closure(local(o))
    return types


def integrity_check(data_graph, ont_graph):
    """Pemeriksaan struktur data uji (bukan vonis hukum). Mengembalikan daftar masalah (kosong = lolos).

    (a) setiap entitas peristiwa memiliki tepat satu pdp:responsibleController yang bertipe DataController;
    (b) pdp:ConsentBasedController <=> pdp:hasLegalBasis memuat "consent" (dua arah, sebagaimana lapisan
        ingesti menetapkan kelas ini dari dasar pemrosesan);
    (c) tidak ada pengetikan tak diinginkan: tipe yang diturunkan dari rdfs:domain/rdfs:range harus sudah
        tercakup tipe eksplisit entitas (beserta superkelasnya);
    (d) tidak ada rdfs:domain/rdfs:range di ontologi yang menunjuk kelas pemicu karakteristik
        (subkelas pdp:DataController), karena pemicu harus ditulis eksplisit lewat rdf:type;
    (e) pdp:ConsentWithdrawalRequest hanya ditautkan ke pdp:ConsentBasedController (penarikan kembali
        persetujuan mengandaikan pemrosesan berdasarkan persetujuan, Pasal 40 ayat (1));
    (f1) Pengendali yang pdp:processesPersonalData ke entitas pdp:SpecificPersonalData wajib bertipe
        pdp:HighRiskProcessingController ("pemrosesan atas Data Pribadi yang bersifat spesifik",
        Pasal 34 ayat (2) huruf b);
    (f2) pdp:ChildDataController wajib bertipe pdp:HighRiskProcessingController ("data anak" adalah
        Data Pribadi yang bersifat spesifik, Pasal 4 ayat (2) huruf e jo. Pasal 34 ayat (2) huruf b);
    (f3) Pengendali bertipe pdp:LargeScaleMonitoringActor atau pdp:LargeScaleSpecificDataActor (Pasal 53 ayat (1)
        huruf b/c) wajib bertipe pdp:HighRiskProcessingController (Pasal 34 ayat (2) huruf b, c, d);
    (g) entitas pdp:DPORequiredActor wajib bertipe pdp:DataController atau pdp:DataProcessor ("Pengendali Data
        Pribadi dan Prosesor Data Pribadi", Pasal 53 ayat (1)).
    Pada (d), kelas pemicu = subkelas pdp:DataController serta pdp:DPORequiredActor beserta subkelasnya.
    """
    closure = class_closure(ont_graph)
    types = entity_types(data_graph, ont_graph)
    problems = []

    events = [e for e, t in types.items() if t & set(EVENT_CLASSES)]
    for e in sorted(events):
        ctrls = list(data_graph.objects(rdflib.URIRef(PDP + e), LINK))
        if len(ctrls) != 1:
            problems.append(f"(a) {e}: {len(ctrls)} responsibleController (harus 1)")
        elif "DataController" not in types.get(local(ctrls[0]), set()):
            problems.append(f"(a) {e}: responsibleController {local(ctrls[0])} tidak bertipe DataController")

        elif "ConsentWithdrawalRequest" in types[e] and \
                "ConsentBasedController" not in types.get(local(ctrls[0]), set()):
            problems.append(f"(e) {e}: penarikan persetujuan pada Pengendali yang bukan ConsentBasedController")

    for e, t in sorted(types.items()):
        bases = {str(o) for o in data_graph.objects(rdflib.URIRef(PDP + e), rdflib.URIRef(PDP + "hasLegalBasis"))}
        if ("ConsentBasedController" in t) != ("consent" in bases):
            problems.append(f"(b) {e}: kelas ConsentBasedController tidak sejalan dengan hasLegalBasis {sorted(bases)}")

    domain = {p: local(c) for p, c in ont_graph.subject_objects(RDFS.domain)}
    rng = {p: local(c) for p, c in ont_graph.subject_objects(RDFS.range) if str(c).startswith(PDP)}
    for s, p, o in data_graph:
        if p in domain and domain[p] not in types.get(local(s), set()):
            problems.append(f"(c) {local(s)}: rdfs:domain {local(p)} menurunkan tipe {domain[p]} yang tidak eksplisit")
        if p in rng and isinstance(o, URIRef) and rng[p] not in types.get(local(o), set()):
            problems.append(f"(c) {local(o)}: rdfs:range {local(p)} menurunkan tipe {rng[p]} yang tidak eksplisit")

    triggers = {local(c) for c in ont_graph.subjects(RDFS.subClassOf, None)
                if ("DataController" in closure(local(c)) and local(c) != "DataController")
                or DPO_TRIGGER in closure(local(c))}
    for p, c in list(domain.items()) + list(rng.items()):
        if c in triggers:
            problems.append(f"(d) ontologi: {local(p)} ber-domain/range kelas pemicu {c}")

    for e, t in sorted(types.items()):
        if DPO_TRIGGER in t and not t & {"DataController", "DataProcessor"}:
            problems.append(f"(g) {e}: pemicu Pasal 53 ayat (1) pada entitas yang bukan Pengendali atau Prosesor")
        if "DataController" not in t or "HighRiskProcessingController" in t:
            continue
        dpo_hr = sorted(t & set(DPO_HIGH_RISK))
        if dpo_hr:
            problems.append(f"(f3) {e}: pemicu Pasal 53 ayat (1) {dpo_hr} tetapi bukan HighRiskProcessingController")
        specific = [local(d) for d in data_graph.objects(rdflib.URIRef(PDP + e), PROCESSES)
                    if "SpecificPersonalData" in types.get(local(d), set())]
        if specific:
            problems.append(f"(f1) {e}: memproses Data Pribadi spesifik {specific} tetapi bukan HighRiskProcessingController")
        if "ChildDataController" in t:
            problems.append(f"(f2) {e}: ChildDataController (data anak = Data Pribadi spesifik) bukan HighRiskProcessingController")
    return problems


def aggregate_by_actor(data_graph, ont_graph, entity_rows):
    """Tabel pendukung (bukan metrik): vonis per pelaku (PSE/Pengendali/Prosesor) beserta peristiwanya.

    Peristiwa digabungkan ke Pengendali lewat pdp:responsibleController. Vonis agregat = Violation bila
    entitas pelaku atau salah satu peristiwanya memiliki >= 1 sh:Violation.
    """
    types = entity_types(data_graph, ont_graph)
    owner = {}
    for e, t in types.items():
        if t & set(EVENT_CLASSES):
            ctrl = data_graph.value(rdflib.URIRef(PDP + e), LINK)
            owner[e] = local(ctrl) if ctrl is not None else e
    groups = defaultdict(list)
    for r in entity_rows:
        groups[owner.get(r["entitas"], r["entitas"])].append(r)
    out = []
    for actor, rs in groups.items():
        exp = "Violation" if any(r["vonis_harapan"] == "Violation" for r in rs) else "Compliant"
        got = "Violation" if any(r["vonis_prediksi"] == "Violation" for r in rs) else "Compliant"
        out.append({"pelaku": actor, "ecp": rs[0].get("ecp", ""),
                    "entitas_terkait": sorted(r["entitas"] for r in rs if r["entitas"] != actor),
                    "n_violation": sum(r["n_violation"] for r in rs), "n_warning": sum(r["n_warning"] for r in rs),
                    "vonis_harapan": exp, "vonis_agregat": got, "sesuai": exp == got})
    return sorted(out, key=lambda r: (r["ecp"], r["pelaku"]))


def shape_coverage(ps_index, entity_rows, types):
    """Bukti cakupan tingkat shape (bukan metrik akurasi utama).

    Untuk setiap property shape: jumlah entitas yang menjadi target, jumlah yang diharapkan memicu,
    jumlah yang aktual memicu, dan pasangan (entitas, shape) yang tidak sesuai kunci.
    """
    cov = []
    for info in sorted(ps_index.values(), key=lambda v: (v["severity"], v["id"])):
        sid, sev = info["id"], info["severity"]
        col_exp = "shape_violation_harapan" if sev == "Violation" else "shape_warning_harapan"
        col_act = "shape_violation_aktual" if sev == "Violation" else "shape_warning_aktual"
        applicable = [r for r in entity_rows if set(info["targets"]) & types.get(r["entitas"], set())]
        exp = [r["entitas"] for r in applicable if sid in r[col_exp]]
        act = [r["entitas"] for r in applicable if sid in r[col_act]]
        cov.append({"shape": sid, "severity": sev, "node_shape": info["node_shape"],
                    "entitas_target": len(applicable), "diharapkan_terpicu": len(exp),
                    "aktual_terpicu": len(act), "entitas_terpicu": ";".join(act),
                    "sesuai_kunci": sorted(exp) == sorted(act)})
    return cov


def _term_sig(g, o):
    """Tanda tangan nilai parameter: daftar RDF (mis. sh:in, sh:or) sebagai tuple berurutan, bnode secara rekursif."""
    if (o, RDF.first, None) in g:
        return tuple(_term_sig(g, x) for x in Collection(g, o))
    if isinstance(o, BNode):
        return _node_sig(g, o)
    if isinstance(o, Literal):
        return (str(o), local(o.datatype) if o.datatype else "")
    return local(o)


def _node_sig(g, node):
    """Pasangan (parameter, nilai) seluruh constraint component dan sh:severity, tanpa NON_CONSTRAINT."""
    return tuple(sorted((local(p), _term_sig(g, o)) for p, o in g.predicate_objects(node)
                        if p not in NON_CONSTRAINT))


def constraint_classes(shapes_graph, shapes_path=SHAPES_PATH):
    """Kelas batasan (rumus 4.2): NodeShape dengan target dan pola constraint yang sama.

    - target   : himpunan sh:targetClass;
    - pola     : HIMPUNAN tanda tangan property shape (parameter + nilai constraint component + sh:severity;
                 tanpa sh:path, sh:name, sh:message, rdfs:*), ditambah constraint tingkat node bila ada.
    Penomoran K01.. mengikuti urutan kemunculan NodeShape pertama di berkas shapes.
    Mengembalikan (daftar kelas, jumlah kelas bila pola dibaca sebagai multiset).
    """
    with open(shapes_path, encoding="utf-8") as f:
        text = f.read()
    units = property_shapes(shapes_graph)
    groups, multiset = defaultdict(list), set()
    for ns in shapes_graph.subjects(RDF.type, SH.NodeShape):
        targets = tuple(sorted(local(t) for t in shapes_graph.objects(ns, SH.targetClass)))
        ps = [_node_sig(shapes_graph, p) for p in shapes_graph.objects(ns, SH.property)]
        node = tuple(sorted((local(p), _term_sig(shapes_graph, o)) for p, o in shapes_graph.predicate_objects(ns)
                            if p in NODE_LEVEL)) if any((ns, p, None) in shapes_graph for p in NODE_LEVEL) else ()
        if node:
            sev = shapes_graph.value(ns, SH.severity)
            node += (("severity", local(sev) if sev is not None else "Violation"),)
        groups[(targets, tuple(sorted(set(ps))), node)].append(ns)
        multiset.add((targets, tuple(sorted(ps)), node))

    def pos(ns):
        i = text.find(f"pdps:{local(ns)}\n")
        return i if i >= 0 else len(text)

    classes = []
    for (targets, _, node), members in sorted(groups.items(), key=lambda kv: min(pos(n) for n in kv[1])):
        members = sorted(members, key=pos)
        names = [local(n) for n in members]
        us = [u for u in units.values() if u["node_shape"] in names]
        comps = set()
        for node_, u in units.items():
            if u["node_shape"] not in names:
                continue
            if u["kind"] == "property":
                comps |= {k for k, _ in _node_sig(shapes_graph, node_) if k != "severity"}
            else:
                comps |= {local(p) for p in NODE_LEVEL if (node_, p, None) in shapes_graph}
        classes.append({
            "kelas": f"K{len(classes) + 1:02d}", "target": list(targets), "node_shape": names,
            "unit": [u["id"] for u in sorted(us, key=lambda u: (names.index(u["node_shape"]), u["id"]))],
            "unit_violation": sorted(u["id"] for u in us if u["severity"] == "Violation"),
            "unit_warning": sorted(u["id"] for u in us if u["severity"] == "Warning"),
            "label": [str(shapes_graph.value(n, RDFS.label)) for n in members],
            "komponen": sorted(comps),
        })
    return classes, len(multiset)


def check_partitions(key_rows, classes):
    """Pemeriksaan desain partisi ECP terhadap kelas batasan (bukan vonis hukum). Daftar masalah (kosong = lolos).

    (i)   setiap kelas batasan memiliki tepat satu partisi pelanggaran, dan setiap partisi pelanggaran satu kelas;
    (ii)  gabungan unit harapan (Violation dan Warning) entitas wakil dalam partisi = seluruh unit kelasnya;
    (iii) tidak ada unit harapan di luar kelasnya (isolasi partisi);
    (iv)  entitas berperan "valid" atau "pendukung" berharapan Compliant tanpa unit Violation, dan entitas
          "wakil" berharapan Violation.
    """
    by_k = {c["kelas"]: c for c in classes}
    problems, parts = [], defaultdict(set)
    for r in key_rows:
        k, role = r.get("kelas_batasan", ""), r.get("peran", "")
        exp = set(r["shape_violation_harapan"]) | set(r["shape_warning_harapan"])
        if role in ("valid", "pendukung"):
            if r["vonis_harapan"] != "Compliant" or r["shape_violation_harapan"]:
                problems.append(f"(iv) {r['entitas']}: peran {role} harus Compliant tanpa unit Violation")
        elif role == "wakil":
            if r["vonis_harapan"] != "Violation":
                problems.append(f"(iv) {r['entitas']}: entitas wakil harus berharapan Violation")
        else:
            problems.append(f"(iv) {r['entitas']}: peran tidak dikenal '{role}'")
        if k == "valid":
            continue
        if k not in by_k:
            problems.append(f"(i) {r['entitas']}: kelas batasan '{k}' tidak ada")
            continue
        parts[(r["ecp"], k)].add(r["entitas"])
        outside = exp - set(by_k[k]["unit"])
        if outside:
            problems.append(f"(iii) {r['entitas']}: unit di luar {k}: {sorted(outside)}")
    ecp_of = defaultdict(set)
    for ecp, k in parts:
        ecp_of[k].add(ecp)
    for c in classes:
        if len(ecp_of[c["kelas"]]) != 1:
            problems.append(f"(i) {c['kelas']}: {len(ecp_of[c['kelas']])} partisi (harus 1)")
            continue
        ecp = next(iter(ecp_of[c["kelas"]]))
        got = set()
        for r in key_rows:
            if r["ecp"] == ecp and r.get("peran") == "wakil":
                got |= set(r["shape_violation_harapan"]) | set(r["shape_warning_harapan"])
        missing = set(c["unit"]) - got
        if missing:
            problems.append(f"(ii) {c['kelas']} ({ecp}): unit kelas tidak dilanggar wakil: {sorted(missing)}")
    for ecp in {e for e, _ in parts}:
        ks = {k for e, k in parts if e == ecp}
        if len(ks) != 1:
            problems.append(f"(i) {ecp}: memuat lebih dari satu kelas batasan {sorted(ks)}")
    return problems


def three_magnitudes(report_graph, results):
    """Tiga besaran yang harus dibedakan di Bab 4, per severity:
    hasil validasi (sh:ValidationResult), pasangan (focus node, unit constraint) terpicu, dan focus node terpicu."""
    counts = severity_counts(report_graph)
    return {s: {"hasil_validasi": counts[s],
                "pasangan_terpicu": sum(len(set(v[s])) for v in results.values()),
                "entitas": sum(bool(v[s]) for v in results.values())} for s in SEVERITIES}


def artifact_stats():
    """Statistik artefak dihitung dari berkas (bukan dari draf)."""
    shapes = load_graph(SHAPES_PATH)
    units = property_shapes(shapes)
    ps = [v for v in units.values() if v["kind"] == "property"]
    nodes = [v for v in units.values() if v["kind"] == "node"]
    per_sev = {s: sum(v["severity"] == s for v in ps) for s in SEVERITIES}
    triples = {os.path.basename(p): len(load_graph(p))
               for p in (ONTOLOGY_PATH, SHAPES_PATH, COMPLIANT_PATH, VIOLATION_PATH, BVA_PATH)
               if os.path.exists(p)}
    return {"node_shape": len(set(shapes.subjects(RDF.type, SH.NodeShape))),
            "property_shape": len(ps), "property_shape_per_severity": per_sev,
            "node_constraint": len(nodes), "node_constraint_per_severity":
                {s: sum(v["severity"] == s for v in nodes) for s in SEVERITIES},
            "triple": triples}


def write_csv(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (";".join(v) if isinstance(v, list) else v) for k, v in r.items()})
