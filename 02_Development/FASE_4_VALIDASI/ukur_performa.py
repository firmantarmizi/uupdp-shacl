"""
Pengukuran performa validasi pySHACL: waktu, memori, dan skalabilitas.

Protokol:
  - Yang diukur: satu panggilan alat_evaluasi.validate() (pyshacl, inference="rdfs", allow_warnings=True)
    pada graf data yang sudah di-parse. Waktu parsing berkas dicatat terpisah.
  - Waktu: 1 run pemanasan (dibuang), lalu >= 10 run dengan time.perf_counter() TANPA tracemalloc.
    Dilaporkan median, simpangan baku sampel (SD), mean, koefisien variasi (CV = SD/mean), minimum,
    maksimum, dan pencilan Tukey (1,5 x IQR; hanya ditandai, tidak dibuang).
    Waktu setiap eksekusi (termasuk pemanasan, cek hasil, dan run memori) ditulis ke runs_mentah.csv,
    beserta stempel waktu mulai/selesai dan kinerja CPU rerata selama eksekusi (penghitung PDH
    "% Processor Performance" x "Processor Frequency"; tanpa hak admin). Penghitung dibaca DI LUAR interval
    perf_counter dan hanya bersifat deskriptif: tidak dipakai untuk menyaring run (CHANGELOG 2026-10-28 §15).
  - Memori: run terpisah dengan tracemalloc (puncak alokasi Python), median dari --mem-runs run.
  - Skalabilitas: graf pelanggaran direplikasi xk (subjek pdp: diberi sufiks _i). Setiap faktor diperiksa:
    jumlah sh:Violation dan sh:Warning harus tepat k x jumlah pada x1.
Keluaran: CSV, JSON, dan PNG di --keluaran, masing-masing memuat label status (--status).

Contoh:
  ..\\..\\.venv\\Scripts\\python.exe ukur_performa.py
  ..\\..\\.venv\\Scripts\\python.exe ukur_performa.py --faktor 1 10 --keluaran validation_results\\coba
"""

import argparse
import csv
import datetime
import gc
import json
import os
import platform
import statistics
import sys
import time
import tracemalloc

import rdflib

import alat_evaluasi as ae

STATUS_DEFAULT = "UJI ALAT - bukan angka resmi Bab 4; akan diukur ulang setelah Bagian B/D"


# Setiap eksekusi (cek hasil, pemanasan, run ukur, run memori, parse) dicatat di sini dan ditulis ke
# runs_mentah.csv, sehingga tidak ada run yang hilang dari jejak audit.
RAW = []


class CpuCounter:
    """Kinerja CPU rerata selama satu eksekusi lewat pdh.dll (Windows, tanpa hak admin).

    "% Processor Performance" adalah penghitung laju, sehingga nilai sesudah collect kedua adalah rerata
    sejak collect pertama. Nama penghitung bahasa Inggris (PdhAddEnglishCounterW) agar tidak bergantung bahasa
    Windows. Bila tidak tersedia, semua nilai None dan alasannya disimpan di .galat.
    """
    PATHS = (r"\Processor Information(_Total)\% Processor Performance",
             r"\Processor Information(_Total)\Processor Frequency")

    def __init__(self):
        self.galat, self.pdh = None, None
        try:
            import ctypes

            class VALUE(ctypes.Structure):
                _fields_ = [("CStatus", ctypes.c_ulong), ("doubleValue", ctypes.c_double)]

            self.VALUE, self.ctypes = VALUE, ctypes
            pdh = ctypes.WinDLL("pdh")
            self.query = ctypes.c_void_p()
            if pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.query)):
                raise OSError("PdhOpenQueryW gagal")
            self.counters = []
            for p in self.PATHS:
                c = ctypes.c_void_p()
                rc = pdh.PdhAddEnglishCounterW(self.query, p, 0, ctypes.byref(c))
                if rc:
                    raise OSError(f"PdhAddEnglishCounterW {p}: 0x{rc & 0xFFFFFFFF:08x}")
                self.counters.append(c)
            pdh.PdhCollectQueryData(self.query)
            self.pdh = pdh
        except Exception as e:  # noqa: BLE001
            self.galat = str(e)

    def mulai(self):
        if self.pdh:
            self.pdh.PdhCollectQueryData(self.query)

    def selesai(self):
        """(persen kinerja, MHz nominal, MHz efektif) rerata sejak mulai(); None bila tidak tersedia."""
        if not self.pdh:
            return None, None, None
        self.pdh.PdhCollectQueryData(self.query)
        out = []
        for c in self.counters:
            v = self.VALUE()
            rc = self.pdh.PdhGetFormattedCounterValue(c, 0x200 | 0x8000, None, self.ctypes.byref(v))  # DOUBLE|NOCAP100
            out.append(v.doubleValue if rc == 0 else None)
        pct, mhz = out
        eff = pct * mhz / 100 if pct is not None and mhz is not None else None
        return (round(pct, 2) if pct is not None else None, round(mhz) if mhz is not None else None,
                round(eff) if eff is not None else None)


CPU = None  # diisi di main() agar impor modul tidak membuka query PDH


def run_once(fn):
    """Satu eksekusi terukur. Penghitung CPU dan stempel waktu dibaca di luar interval perf_counter."""
    CPU.mulai()
    mulai = datetime.datetime.now()
    t = time.perf_counter()
    result = fn()
    dt = time.perf_counter() - t
    selesai = datetime.datetime.now()
    pct, mhz, eff = CPU.selesai()
    return result, dt, {"mulai": mulai.isoformat(timespec="milliseconds"),
                        "selesai": selesai.isoformat(timespec="milliseconds"),
                        "cpu_kinerja_persen": pct, "cpu_mhz_nominal": mhz, "cpu_mhz_efektif": eff}


def catat_run(bagian, nama, jenis, run_ke, detik, info, mb=""):
    RAW.append({"bagian": bagian, "graf_atau_faktor": nama, "jenis": jenis, "run_ke": run_ke,
                "detik": round(detik, 6), "mb": mb, **info})


def median_eff(bagian, nama, jenis="ukur"):
    """Median MHz efektif run ukur (deskriptif)."""
    v = [r["cpu_mhz_efektif"] for r in RAW
         if r["bagian"] == bagian and r["graf_atau_faktor"] == nama and r["jenis"] == jenis
         and r["cpu_mhz_efektif"] is not None]
    return round(statistics.median(v)) if v else None


def memory_status():
    """RAM total dan bebas (GB) lewat GlobalMemoryStatusEx; None di luar Windows."""
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return {"ram_total_gb": round(m.ullTotalPhys / 1024**3, 2), "ram_bebas_gb": round(m.ullAvailPhys / 1024**3, 2)}
    except Exception as e:  # noqa: BLE001
        return {"ram_total_gb": None, "ram_bebas_gb": None, "ram_galat": str(e)}


def power_status():
    """Status daya lewat GetSystemPowerStatus dan skema daya aktif lewat powercfg; None di luar Windows."""
    out = {}
    try:
        import ctypes

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                        ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                        ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
        s = SYSTEM_POWER_STATUS()
        ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))
        out["daya_ac"] = {0: "baterai", 1: "AC terhubung"}.get(s.ACLineStatus, "tidak diketahui")
        out["baterai_persen"] = None if s.BatteryLifePercent in (-1, 255) else s.BatteryLifePercent
    except Exception as e:  # noqa: BLE001
        out["daya_galat"] = str(e)
    try:
        import subprocess
        out["skema_daya"] = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True,
                                           text=True, timeout=10).stdout.strip()
    except Exception as e:  # noqa: BLE001
        out["skema_daya"] = f"tidak terbaca: {e}"
    return out


def cpu_name():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
    except Exception:  # noqa: BLE001
        return platform.processor()


def cpu_mhz_nominal():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            return winreg.QueryValueEx(k, "~MHz")[0]
    except Exception:  # noqa: BLE001
        return None


def environment():
    import matplotlib
    import numpy
    import pyshacl
    return {
        "mulai": datetime.datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0], "pyshacl": pyshacl.__version__, "rdflib": rdflib.__version__,
        "matplotlib": matplotlib.__version__, "numpy": numpy.__version__,
        "os": platform.platform(), "cpu": cpu_name(), "prosesor": platform.processor(),
        "cpu_logis": os.cpu_count(), "cpu_mhz_nominal": cpu_mhz_nominal(),
        "penghitung_cpu": "PDH " + " ; ".join(CpuCounter.PATHS), "penghitung_cpu_galat": CPU.galat,
        **memory_status(), **power_status(),
    }


def stats(ts):
    """Median, SD sampel, mean, CV, min, maks, dan pencilan Tukey (1,5 x IQR) dari SEMUA run.
    Pencilan hanya ditandai; tidak ada run yang dibuang dari perhitungan."""
    q1, _, q3 = statistics.quantiles(ts, n=4, method="inclusive")
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    out = [t for t in ts if t < lo or t > hi]
    mean, sd = statistics.mean(ts), statistics.stdev(ts)
    return {"median_s": statistics.median(ts), "sd_s": sd, "mean_s": mean, "cv_persen": 100 * sd / mean,
            "min_s": min(ts), "max_s": max(ts), "n_pencilan": len(out),
            "pencilan_s": ";".join(f"{t:.4f}" for t in out)}


def time_runs(fn, runs, bagian, nama, jenis="ukur"):
    _, dt, info = run_once(fn)  # pemanasan: tidak masuk statistik, tetapi waktunya dicatat
    catat_run(bagian, nama, f"pemanasan_{jenis}", 0, dt, info)
    ts = []
    for i in range(runs):
        gc.collect()
        _, dt, info = run_once(fn)
        ts.append(dt)
        catat_run(bagian, nama, jenis, i + 1, dt, info)
    return {**stats(ts), "runs": runs, "semua_s": ts}


def peak_memory(fn, runs, bagian, nama):
    peaks = []
    for i in range(runs):
        gc.collect()
        tracemalloc.start()
        _, dt, info = run_once(fn)
        peaks.append(tracemalloc.get_traced_memory()[1] / 1048576)
        tracemalloc.stop()
        # waktu run memori dicatat hanya untuk audit; tidak dipakai sebagai angka waktu (tracemalloc aktif)
        catat_run(bagian, nama, "memori", i + 1, dt, info, round(peaks[-1], 4))
    return {"median_mb": statistics.median(peaks), "runs": runs, "semua_mb": peaks}


def time_fields(tv):
    return {k: round(tv[k], 4) for k in ("median_s", "sd_s", "mean_s", "min_s", "max_s")} | {
        "cv_persen": round(tv["cv_persen"], 2), "n_pencilan": tv["n_pencilan"], "pencilan_s": tv["pencilan_s"]}


def replicate(base, k):
    """Replikasi xk. Subjek pdp: diberi sufiks _i; objek yang juga merupakan subjek data (mis. tautan
    pdp:responsibleController dari peristiwa ke Pengendali) ikut diberi sufiks agar replika tetap tertaut
    ke Pengendali replika yang sama. Objek berupa kelas (mis. pdp:DataController) tidak diubah."""
    entities = {s for s in base.subjects() if str(s).startswith(ae.PDP)}
    g = rdflib.Graph()
    for i in range(k):
        ren = lambda x: rdflib.URIRef(f"{x}_{i}") if x in entities else x  # noqa: E731
        for s, p, o in base:
            g.add((ren(s), p, ren(o)))
    return g


def write_rows(path, rows, status):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(f"# {status}\n")
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def plot(rows, path, status):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, grid, surface, series = "#1f1f1e", "#6b6b68", "#e4e4e1", "#fcfcfb", "#2a78d6"
    x = [r["triple"] for r in rows]
    y = [r["median_s"] for r in rows]
    e = [r["sd_s"] for r in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    ax.errorbar(x, y, yerr=e, color=series, linewidth=2, marker="o", markersize=6,
                markeredgecolor=surface, markeredgewidth=1.5, ecolor=series, elinewidth=1.2, capsize=3)
    for i, r in enumerate(rows):
        # titik pertama diberi label di atas agar tidak berimpit dengan titik kedua di dekat titik nol
        offset = (4, 8) if i == 0 else (6, -12)
        ax.annotate(f"x{r['faktor']}", (r["triple"], r["median_s"]), textcoords="offset points",
                    xytext=offset, fontsize=8, color=muted)
    ax.set_xlabel("Jumlah triple graf data", color=ink, fontsize=9)
    ax.set_ylabel("Waktu validasi, median (detik)", color=ink, fontsize=9)
    ax.set_title("Waktu validasi pySHACL terhadap ukuran graf", color=ink, fontsize=11, loc="left", pad=22)
    ax.text(0, 1.02, f"Median dan SD dari {rows[0]['runs']} run per faktor. {status}",
            transform=ax.transAxes, fontsize=7, color=muted, va="bottom")
    ax.grid(True, color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(grid)
    ax.tick_params(colors=muted, labelsize=8)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(path, facecolor=surface)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--mem-runs", type=int, default=3)
    ap.add_argument("--faktor", type=int, nargs="+", default=[1, 10, 50, 100, 250])
    ap.add_argument("--keluaran", default=os.path.join(ae.OUTPUT_DIR, "uji_alat_E"))
    ap.add_argument("--status", default=STATUS_DEFAULT)
    ap.add_argument("--lewati-skala", action="store_true")
    ap.add_argument("--hanya-grafik", action="store_true",
                    help="gambar ulang PNG dari skalabilitas.csv di --keluaran tanpa mengukur ulang")
    a = ap.parse_args()
    if a.hanya_grafik:
        with open(os.path.join(a.keluaran, "skalabilitas.csv"), encoding="utf-8") as f:
            status = f.readline().lstrip("# ").strip()
            rows = [{k: (float(v) if k in ("median_s", "sd_s") else int(v) if k in ("faktor", "triple", "runs") else v)
                     for k, v in r.items()} for r in csv.DictReader(f)]
        plot(rows, os.path.join(a.keluaran, "skalabilitas_waktu_vs_triple.png"), status)
        print("Grafik digambar ulang dari skalabilitas.csv")
        return 0
    if a.runs < 10:
        sys.exit("Protokol penelitian mensyaratkan minimal 10 run (--runs >= 10).")
    os.makedirs(a.keluaran, exist_ok=True)
    global CPU
    CPU = CpuCounter()
    if CPU.galat:
        print(f"PERHATIAN: penghitung CPU tidak tersedia ({CPU.galat}); kolom CPU dikosongkan.")

    env = environment()
    print(f"[{a.status}]\nLingkungan: {env}\n")
    shapes, ont = ae.load_graph(ae.SHAPES_PATH), ae.load_graph(ae.ONTOLOGY_PATH)

    # --- Performa per graf ---
    graf_rows = []
    for name, path in (("compliant", ae.COMPLIANT_PATH), ("violation", ae.VIOLATION_PATH), ("uji_batas_bva", ae.BVA_PATH)):
        if not os.path.exists(path):
            continue
        parse = time_runs(lambda: ae.load_graph(path), a.runs, "per_graf", name, "parse")
        g = ae.load_graph(path)
        tv = time_runs(lambda: ae.validate(g, shapes, ont), a.runs, "per_graf", name)
        mem = peak_memory(lambda: ae.validate(g, shapes, ont), a.mem_runs, "per_graf", name)
        row = {"graf": name, "triple": len(g), "runs": a.runs, **time_fields(tv),
               "parse_median_s": round(parse["median_s"], 4),
               "mem_puncak_median_mb": round(mem["median_mb"], 2), "mem_runs": a.mem_runs,
               "cpu_mhz_efektif_median": median_eff("per_graf", name)}
        graf_rows.append(row)
        print(f"{name:<14}{len(g):>6} triple | validasi median {row['median_s']:.3f} s (SD {row['sd_s']:.3f}, "
              f"CV {row['cv_persen']:.1f}%, pencilan {row['n_pencilan']}) | parse {row['parse_median_s']:.3f} s | memori puncak {row['mem_puncak_median_mb']:.2f} MB")
    write_rows(os.path.join(a.keluaran, "performa_per_graf.csv"), graf_rows, a.status)

    # --- Skalabilitas ---
    skala_rows = []
    if not a.lewati_skala:
        base = ae.load_graph(ae.VIOLATION_PATH)
        _, rep1, _ = ae.validate(base, shapes, ont)
        c1 = ae.severity_counts(rep1)
        print(f"\nSkalabilitas (graf pelanggaran; x1 = {c1['Violation']} V / {c1['Warning']} W)")
        for k in a.faktor:
            g = replicate(base, k)
            (_, rep, _), dt, info = run_once(lambda: ae.validate(g, shapes, ont))
            catat_run("skala", k, "cek_hasil", 0, dt, info)
            ck = ae.severity_counts(rep)
            ok = ck["Violation"] == k * c1["Violation"] and ck["Warning"] == k * c1["Warning"]
            tv = time_runs(lambda: ae.validate(g, shapes, ont), a.runs, "skala", k)
            mem = peak_memory(lambda: ae.validate(g, shapes, ont), 1, "skala", k)
            row = {"faktor": k, "triple": len(g), "runs": a.runs, **time_fields(tv),
                   "mem_puncak_mb": round(mem["median_mb"], 2),
                   "violation": ck["Violation"], "warning": ck["Warning"], "cek_hasil_k_kali": ok,
                   "cpu_mhz_efektif_median": median_eff("skala", k)}
            skala_rows.append(row)
            write_rows(os.path.join(a.keluaran, "skalabilitas.csv"), skala_rows, a.status)
            write_rows(os.path.join(a.keluaran, "runs_mentah.csv"), RAW, a.status)
            print(f"x{k:<5}{len(g):>7} triple | median {row['median_s']:.3f} s (SD {row['sd_s']:.3f}, "
                  f"CV {row['cv_persen']:.1f}%, pencilan {row['n_pencilan']}) | "
                  f"memori {row['mem_puncak_mb']:.2f} MB | {ck['Violation']} V / {ck['Warning']} W | cek {'OK' if ok else 'GAGAL'}")
        plot(skala_rows, os.path.join(a.keluaran, "skalabilitas_waktu_vs_triple.png"), a.status)

    write_rows(os.path.join(a.keluaran, "runs_mentah.csv"), RAW, a.status)
    selesai = datetime.datetime.now()
    env["selesai"] = selesai.isoformat(timespec="seconds")
    env["durasi_menit"] = round((selesai - datetime.datetime.fromisoformat(env["mulai"])).total_seconds() / 60, 1)
    env["ram_bebas_gb_selesai"] = memory_status()["ram_bebas_gb"]
    env.update({f"{k}_selesai": v for k, v in power_status().items() if k in ("daya_ac", "baterai_persen")})
    print(f"Selesai {env['selesai']} (durasi {env['durasi_menit']} menit)")
    with open(os.path.join(a.keluaran, "ringkasan.json"), "w", encoding="utf-8") as f:
        json.dump({"status": a.status, "lingkungan": env, "performa_per_graf": graf_rows,
                   "skalabilitas": skala_rows}, f, ensure_ascii=False, indent=2)
    print(f"\nKeluaran tersimpan di {a.keluaran}")
    if skala_rows and not all(r["cek_hasil_k_kali"] for r in skala_rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
