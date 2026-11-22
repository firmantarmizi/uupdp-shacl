# Angka Tabel Bab 4 (dihitung oleh hitung_tabel_bab4.py)

## Tabel 4.2 Distribusi kelas operabilitas

| Kategori | Jumlah | % | Pasal |
|---|:---:|:---:|---|
| Fully Operable (skor >= 4) | 33 | 43,42 | 13, 18, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 48, 51, 52, 53, 56, 65 |
| Parsial (skor 3) | 11 | 14,47 | 4, 6, 7, 8, 9, 10, 11, 17, 33, 55, 66 |
| Non-Operable (skor <= 2) | 32 | 42,11 | 1, 2, 3, 5, 12, 14, 15, 16, 19, 23, 47, 49, 50, 54, 57, 58, 59, 60, 61, 62, 63, 64, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76 |
| Total | 76 | 100,00 |  |

## Tabel 4.3 Sebaran Fully Operable per bab

| Bab | Judul | Jumlah | Pasal |
|---|---|:---:|---|
| IV | Hak Subjek Data Pribadi | 1 | 13 |
| V | Pemrosesan Data Pribadi | 1 | 18 |
| VI | Kewajiban Pengendali dan Prosesor Data Pribadi | 29 | 20, 21, 22, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 48, 51, 52, 53 |
| VII | Transfer Data Pribadi | 1 | 56 |
| XIII | Larangan dalam Penggunaan Data Pribadi | 1 | 65 |
| Total |  | 33 |  |

## Tabel 4.4 Distribusi deontik dan pemetaan severity

| Modalitas | Jumlah klausul | Pasal | Severity |
|---|:---:|---|---|
| Obligation | 32 | Ps. 13 ayat (1); Ps. 18 ayat (2); Ps. 20 ayat (1)–(2); Ps. 21 ayat (1); Ps. 22 ayat (1); Ps. 24; Ps. 25 ayat (2); Ps. 26 ayat (3); Ps. 27; Ps. 28; Ps. 29 ayat (1)–(2); Ps. 30 ayat (1); Ps. 31; Ps. 32 ayat (2); Ps. 34 ayat (1); Ps. 35 huruf a; Ps. 36; Ps. 37; Ps. 38; Ps. 39 ayat (1)–(2); Ps. 40 ayat (2); Ps. 41 ayat (1); Ps. 42 ayat (1); Ps. 43 ayat (1); Ps. 44 ayat (1); Ps. 45; Ps. 46 ayat (1)–(2); Ps. 48 ayat (1)–(2); Ps. 51 ayat (1); Ps. 52; Ps. 53 ayat (1); Ps. 56 ayat (2)–(4) | sh:Violation |
| Prohibition | 1 | Ps. 65 ayat (2)–(3) | sh:Violation |
| Permission | 0 |  | - |
| Peringatan dini bila lebih dari 48 jam; bila lebih dari 72 jam tercatat bersama pelanggaran (bukan klausul tersendiri) | - | Pola Tenggat (Ps. 30, 32, 40, 41, 46) | sh:Warning |

Unit constraint di shapes_pdp.ttl: property shape Violation 42, Warning 5, Info 0; constraint tingkat node Violation 2. NodeShape 30.

## Tabel 4.7 Distribusi per kelas batasan (N_constraint = 24; multiset: 25)

Hasil = sh:ValidationResult; pasangan = (focus node, unit) terpicu; entitas = focus node terpicu (graf ECP compliant + violation). Entitas total dapat lebih kecil daripada jumlah per kelas bila satu entitas terpicu di beberapa kelas.

| Kelas | Target | NodeShape | Pasal | Komponen | Unit V | Unit W | Hasil V | Pasangan V | Entitas V | Hasil W | Pasangan W | Entitas W |
|---|---|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| K01 | DataUpdateRequest | DataUpdateShape | Pasal 30 ayat (1) | datatype, maxInclusive, minCount | 2 | 1 | 2 | 2 | 2 | 2 | 2 | 2 |
| K02 | DataAccessRequest | DataAccessShape | Pasal 32 ayat (2) | datatype, maxInclusive, minCount | 2 | 1 | 2 | 2 | 2 | 2 | 2 | 2 |
| K03 | ConsentWithdrawalRequest | ProcessingCessationShape | Pasal 40 ayat (2) | datatype, maxInclusive, minCount | 2 | 1 | 2 | 2 | 2 | 2 | 2 | 2 |
| K04 | ProcessingRestrictionRequest | ProcessingRestrictionShape | Pasal 41 ayat (1) | datatype, maxInclusive, minCount | 2 | 1 | 2 | 2 | 2 | 2 | 2 | 2 |
| K05 | BreachIncident | BreachNotificationShape | Pasal 46 ayat (1) | datatype, maxInclusive, minCount | 2 | 1 | 2 | 2 | 2 | 2 | 2 | 2 |
| K06 | DataController, DataProcessor | SecurityMeasuresShape, ConfidentialityShape, SupervisionShape, ElectronicSecuritySystemShape, AuditLogShape, DataAccuracyShape | Pasal 35 huruf a dan Pasal 38; Pengendalian Hak Akses Pasal 39 ayat (1); bagi Prosesor jo. Pasal 52 / Pasal 36; bagi Prosesor jo. Pasal 52 / Pasal 37; bagi Prosesor jo. Pasal 52 / Pasal 39 ayat (1) dan (2); bagi Prosesor jo. Pasal 52 / Pasal 31; bagi Prosesor jo. Pasal 52 / Pasal 29 ayat (2); bagi Prosesor jo. Pasal 52 | datatype, in, minCount | 14 | 0 | 21 | 21 | 3 | 0 | 0 | 0 |
| K07 | HighRiskProcessingController | DPIAShape | Pasal 34 ayat (1) | datatype, hasValue, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K08 | DataController | LegalBasisShape | Pasal 20 ayat (1) dan (2) | datatype, in, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K09 | ConsentBasedController | ConsentEvidenceShape, ProcessingNoticeShape | Pasal 24 jo. Pasal 22 ayat (1) / Pasal 21 ayat (1) | datatype, hasValue, minCount | 2 | 0 | 2 | 2 | 1 | 0 | 0 | 0 |
| K10 | ChildDataController | ChildConsentShape | Pasal 25 ayat (2) | datatype, hasValue, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K11 | DisabilityDataController | DisabilityConsentShape | Pasal 26 ayat (3) | datatype, hasValue, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K12 | DataController | DataMinimizationShape | Pasal 27 dan Pasal 28 | datatype, hasValue, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K13 | JointController | JointControllerShape | Pasal 18 ayat (2) | datatype, hasValue, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K14 | ProcessingTerminationGround | ProcessingTerminationShape | Pasal 42 ayat (1) | datatype, hasValue, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K15 | BreachIncident | BreachNotificationContentShape | Pasal 46 ayat (2) | datatype, hasValue, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K16 | CrossBorderTransfer | InternationalTransferShape | Pasal 56 ayat (2) sampai (4) | or | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K17 | DataProcessor | ProcessorInstructionShape | Pasal 51 ayat (1) | datatype, hasValue, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K18 | PSE | UnauthorizedProcessingShape | Pasal 65 ayat (2) dan (3) | datatype, hasValue | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K19 | CorporateAction | CorporateActionNoticeShape | Pasal 48 ayat (1) dan (2) | datatype, hasValue, minCount | 2 | 0 | 2 | 2 | 1 | 0 | 0 | 0 |
| K20 | DPORequiredActor | DataProtectionOfficerShape | Pasal 53 ayat (1) | datatype, hasValue, minCount | 1 | 0 | 2 | 2 | 2 | 0 | 0 | 0 |
| K21 | DataPortabilityRequest | DataPortabilityShape | Pasal 13 ayat (1) | datatype, hasValue, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K22 | DeletionGround | DataDeletionShape | Pasal 43 ayat (1) | datatype, hasValue, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K23 | DestructionGround | DataDestructionShape | Pasal 44 ayat (1) | datatype, hasValue, minCount | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| K24 | ErasureGround | DeletionNoticeShape | Pasal 45 | or | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| Total | | | | | 44 | 5 | 52 | 52 | 32 | 10 | 10 | 10 |
