# PDP Law → SHACL: semantic dataset for compliance checking of Indonesia's Personal Data Protection Law

This repository accompanies the article *"Encoding selected clauses of Indonesia's Personal Data Protection Law as SHACL shapes for deterministic compliance checking"* by Firman Tarmizi and Alva Hendi Muhammad (Postgraduate Program, Universitas Amikom Yogyakarta), submitted to *JUTI: Jurnal Ilmiah Teknologi Informasi*.

It contains an RDFS ontology and SHACL shapes for selected clauses of Law of the Republic of Indonesia No. 27 of 2022 on Personal Data Protection (UU PDP), synthetic test graphs with answer keys, the scripts used for validation, verification, agreement computation, and performance measurement, and the official results reported in the article.

> **Scope.** The shapes encode only the clauses classified as Fully Operable in the article, and some articles only in part (for example, Article 35(b) is not encoded). Exceptions in Articles 15(1), 41(2), and 50(1) are not modeled, so a *Violation* holds only if no exception applies. The test data are synthetic. The verification results show that the rules behave as designed; they do not establish that any real organization complies with the Law, and the output is not legal advice. Comments and messages in the files are written in Indonesian.

## Contents

```
README.md, LICENSE, LICENSE-DATA, CITATION.cff, requirements.txt
hitung_tabel3.py                    recomputes Table 3 of the article from legal_alignment/skor_per_butir.csv
02_Development/
├── FASE_3_DATASET_SEMANTIK/
│   ├── ontology_pdp.ttl            RDFS ontology (347 triples)
│   ├── shapes_pdp.ttl              SHACL shapes (30 node shapes, 49 constraint units; 489 triples)
│   ├── data_pse_compliant.ttl      synthetic graph: compliant partition (ECP-01)
│   ├── data_pse_violation.ttl      synthetic graph: partitions ECP-02 to ECP-26
│   ├── data_uji_batas_bva.ttl      synthetic graph: boundary value analysis
│   └── buat_data_bva.py            generator of the boundary graph and its key
└── FASE_4_VALIDASI/
    ├── kunci_jawaban_ecp.csv       answer key, 64 entities in 26 partitions
    ├── kunci_jawaban_bva.csv       answer key, 26 boundary cases
    ├── alat_evaluasi.py            shared evaluation functions
    ├── run_validation.py           validation, per-entity evaluation, boundary test
    ├── evaluasi_per_entitas.py     per-entity confusion matrix only
    ├── uji_pemicu.py               trigger test (23 cases)
    ├── uji_mutasi.py               mutation test (25 mutants)
    ├── hitung_kelas_batasan.py     computes boundary classes from the shapes
    ├── ukur_performa.py            time, memory, and scalability measurement
    ├── jalankan_pengukuran_ulang.ps1  measurement protocol wrapper used for the official run (see warning below)
    ├── demo_live.py                small interactive demonstration (Article 46(1), Articles 35(a)/38)
    └── validation_results/resmi_v3/   official results used in the article
legal_alignment/
├── klausul_instrumen.csv           the 44 rule cards as rated (before deliberation)
├── skor_per_butir.csv              item-level scores without rater identities
├── kappa_ringkasan.json            contingency table and agreement measures
├── hitung_kappa.py                 formulas for κ and companion measures (self-test: --uji)
├── penilaian_ulang.csv             re-rating of the revised rules for Articles 35 and 52 (scores and categories only)
├── kartu_vs_shape.csv              each rated Group A card next to the constraint units of the final shapes
└── provenance/                     scripts that produced the CSV files above (documentation, see below)
traceability/
├── operability_screening.csv       screening scores (S, A, K, T, D), total, and class for all 76 articles
├── traceability.csv                each Fully Operable clause: official text (Indonesian), node shapes,
│                                   constraint units, target classes, trigger type, severity, deontic type
└── provenance/                     script that derived both files (documentation, see below)
```

## Requirements

Python 3.13.0. The exact package versions used for the official results are pinned in `requirements.txt` (rdflib 7.6.0, pySHACL 0.40.1, owlrl 7.6.2, matplotlib 3.10.0, openpyxl 3.1.5, and their dependencies).

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt     # Windows
# .venv/bin/python -m pip install -r requirements.txt       # Linux/macOS
```

The results were produced on Windows 11. Validation uses `inference="rdfs"` without OWL reasoning and `allow_warnings=True`. The validation verdict on the encoded requirements is *Violation* for an entity if at least one `sh:Violation` result has that entity as focus node; warnings do not change the verdict.

## Reproducing the results

Run from `02_Development/FASE_4_VALIDASI/` with the environment above:

```bash
python run_validation.py        # compliant graph 0 V / 0 W; violation graph 52 V / 10 W;
                                #   64 entities, TP 32, TN 32, FP 0, FN 0; boundary cases 26/26
python uji_pemicu.py            # 23/23 cases; controller without triggers (K00): 0 results
python uji_mutasi.py            # 25/25 mutants detected
python hitung_kelas_batasan.py  # 24 boundary classes, 26 partitions
```

New outputs are written to `validation_results/` next to the official folder. The ten files in `validation_results/resmi_v3/verifikasi/` can be compared byte by byte with the new outputs of the same name; in a clean environment built from `requirements.txt` they were identical.

Table 3 of the article (agreement of the first, independent ratings) is recomputed from the repository root:

```bash
python hitung_tabel3.py         # a 31, b 0, c 5, d 8; p_o 0.8864, p_e 0.6302, kappa 0.6927,
                                #   p_pos 0.9254, p_neg 0.7619, AC1 0.8215, PABAK 0.7727, PI 0.5227, BI -0.1136
python legal_alignment/hitung_kappa.py --uji   # self-test of the formulas
```

Per-group κ is not computed, as specified before the ratings were collected; `hitung_tabel3.py` prints the per-group cross-tabulations.

### Performance measurement

`ukur_performa.py` reproduces the timing protocol (one warm-up run, 10 timed runs, three memory runs, replication factors 1, 10, 50, 100, and 250). Write its output to a new folder, for example:

```bash
python ukur_performa.py --keluaran validation_results/my_run --status "replication"
```

Absolute times depend on the machine. **Warning:** `jalankan_pengukuran_ulang.ps1` is included to document the protocol of the official run (uptime, CPU-load, and power-scheme checks before calling `ukur_performa.py`). Use `ukur_performa.py` directly instead. With its default parameters the wrapper writes into `validation_results/resmi_v3` and would overwrite the official results; with another output folder it stops because it expects the hash manifest in that folder.

## Official results

- The files in `validation_results/resmi_v3/` are published as produced. Several log files contain absolute paths on the authors' machine (for example `D:\Magister PJJ ...`); they have not been edited, so that they remain evidence of the official runs.
- The environment snapshots `lingkungan_awal.txt` and `lingkungan_akhir.txt`, which list the processes running on the measurement machine, are not published. A summary of the environment (software versions, CPU, RAM, power scheme, and start and end times) is in `ringkasan.json`.
- `tabel_bab4/` and `tabel_bab4_20261029/` are summary tables prepared for the authors' thesis. The script that produced them reads internal working documents and is not included.

## Integrity

SHA-256 hashes of the artifacts are listed in `validation_results/resmi_v3/sha256_artefak.txt`. On 2026-10-29, only comments in `shapes_pdp.ttl` and `ontology_pdp.ttl` and one label in a thesis table script were changed; the updated hashes and the evidence that the RDF graphs and all verification outputs are otherwise identical are in `validation_results/resmi_v3/ADENDUM_20261029.md`. On 2026-11-12, a further comment-only change to `shapes_pdp.ttl` (lines 44–45, start of the Article 46(1) period stated as the authors' interpretation) left the graph isomorphic (489 = 489 triples) and the verification outputs byte-identical; the SHA-256 of the published `shapes_pdp.ttl` is therefore `c31c11045e62b518a2b4d8424d84abd67cbe97a94e2e913ae017be8b7ebd9b7a`. All other listed artifacts match the manifest or the addendum; `hitung_tabel_bab4.py`, a thesis table script listed in the manifest, is not included. The file `.gitattributes` disables line-ending conversion so that the hashes remain valid after cloning.

## Legal alignment data

Two independent raters (one with a background in IT audit and privacy compliance, one with a legal background) scored whether each rule corresponds to the article it cites (Group A, 33 items) and whether each Partial provision can be checked automatically (Group B, 11 items). Both consented to publication of their anonymized scores.

- `skor_per_butir.csv` contains their first, independent scores, the predefined category of mismatch they selected (free-text explanations removed), and the deliberation outcome per item.
- `kappa_ringkasan.json` holds the contingency table, which can be recomputed from the first two score columns.
- `penilaian_ulang.csv` gives the re-rating of the revised rules for Articles 35 and 52.
- `kartu_vs_shape.csv` places each rated Group A card next to the constraint units of the final `shapes_pdp.ttl`. The rules for Articles 35 and 52 were revised after deliberation, so their cards describe the version rated first.
- `klausul_instrumen.csv` is published as it was used. The column `sumber_kutipan` ("source of the quotation") refers to the official PDF of Law No. 27 of 2022, which is not included here but is available at https://peraturan.go.id/id/uu-no-27-tahun-2022.

Rater identities, free-text comments, and the raw form responses are not published.

## Provenance scripts

The scripts in `legal_alignment/provenance/` and `traceability/provenance/` show how the published CSV files were derived. They read the authors' internal working files (raw form exports, the screening matrix, and the mapping documents), which are not published, so they cannot be re-run from this repository; they are included as documentation. `traceability/provenance/buat_keterlacakan.py` also checks that the two traceability files are consistent with `shapes_pdp.ttl` and `ontology_pdp.ttl` (76 articles; 33 Fully Operable clauses; all 30 node shapes and 49 constraint units covered).

## Documentation language

The two files in `traceability/` are in English, except for the official text of each clause, which is quoted in Indonesian as enacted. The comments and messages in the `.ttl` files and scripts, and the rule cards in `legal_alignment/klausul_instrumen.csv`, are written in Indonesian.

## Citation

Please cite the article and this dataset. Dataset: F. Tarmizi and A. H. Muhammad, *SHACL shapes, RDFS ontology, and synthetic test data for selected clauses of Indonesia's Personal Data Protection Law*, version 1.0.0, Zenodo, 2026, doi: [DOI after the Zenodo release]. Machine-readable metadata are in `CITATION.cff`.

## License

- Code (`*.py`, `*.ps1`): MIT License, see `LICENSE`.
- Data, ontology, and shapes (`*.ttl`, `*.csv`, `*.json`, result files, and documentation): Creative Commons Attribution 4.0 International (CC BY 4.0), see `LICENSE-DATA`.
- The quotations of Law No. 27 of 2022 included in the files are not subject to copyright. Under Article 42(b) of Law of the Republic of Indonesia No. 28 of 2014 on Copyright, there is no copyright in statutory regulations ("Tidak ada Hak Cipta atas hasil karya berupa: … b. peraturan perundang-undangan"). Article 42(d) applies likewise to court decisions, including the quoted ruling of Constitutional Court Decision No. 151/PUU-XXII/2024.
