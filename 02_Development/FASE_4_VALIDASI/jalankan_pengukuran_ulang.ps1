<#
Pengukuran resmi untuk Bab 4. Folder keluaran = parameter -Keluaran (default validation_results\resmi_v3,
hasil utama sejak 2026-10-28). resmi_v2\ dan resmi\ adalah arsip: skrip menolak menulis ke sana.

Jalankan di luar VS Code (tutup aplikasi lain, laptop tersambung AC):
    powershell -ExecutionPolicy Bypass -File jalankan_pengukuran_ulang.ps1

Langkah:
  1. Prasyarat: <Keluaran>\sha256_artefak.txt ada; berkas performa di <Keluaran>\ belum ada (tidak menimpa).
  2. Mencocokkan SHA-256 setiap artefak dengan sha256_artefak.txt; berhenti bila ada yang berbeda.
  3. Menunggu mesin tenang: uptime >= MinUptimeMenit, lalu rerata beban CPU (12 sampel x 5 detik) < AmbangCPU,
     paling lama MaksTungguMenit (bila tercapai, pengukuran tetap berjalan dan nilainya dicatat).
  4. Snapshot awal (proses, beban CPU, RAM, daya, skema daya).
  5. Mencoba skema daya High performance (SCHEME_MIN) dan mencegah sleep; keduanya dikembalikan di blok finally.
  6. Verifikasi singkat run_validation.py (berhenti bila kode keluar != 0).
  7. ukur_performa.py --runs 10 --mem-runs 3 --faktor 1 10 50 100 250 --keluaran <Keluaran>
     (runs_mentah.csv mencatat per run: stempel waktu mulai/selesai dan kinerja CPU rerata selama run).
  8. Snapshot akhir dan ringkasan_skrip.txt.
Opsi -UjiKering: semua langkah, tetapi keluaran ke folder sementara di %TEMP% dan pengukuran hanya --faktor 1;
manifest tetap dibaca dari <Keluaran>.
Skrip ini tidak memerlukan hak administrator. Kompatibel dengan Windows PowerShell 5.1.
#>
param(
    [string]$Keluaran = 'validation_results\resmi_v3',
    [int]$MinUptimeMenit = 15,
    [int]$MaksTungguMenit = 20,
    [double]$AmbangCPU = 15,
    [switch]$UjiKering
)

$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$dev = Split-Path $here -Parent
$py = (Resolve-Path (Join-Path $dev '..\.venv\Scripts\python.exe')).Path
$resmi = if ([IO.Path]::IsPathRooted($Keluaran)) { $Keluaran } else { Join-Path $here $Keluaran }
$namaResmi = Split-Path $resmi -Leaf
if (@('resmi', 'resmi_v2') -contains $namaResmi) {
    Write-Host "BERHENTI: $namaResmi adalah folder arsip (CHANGELOG 2026-10-28 15); pilih folder lain."; exit 2
}
$manifest = Join-Path $resmi 'sha256_artefak.txt'
$HIGH_PERF = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'
$env:PYTHONIOENCODING = 'utf-8'

if ($UjiKering) {
    $out = Join-Path $env:TEMP ('uji_kering_pengukuran_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    $faktor = @('1'); $memRuns = '1'
    $status = 'UJI KERING skrip pengukuran - bukan angka resmi'
    if (-not $PSBoundParameters.ContainsKey('MinUptimeMenit')) { $MinUptimeMenit = 0 }
    if (-not $PSBoundParameters.ContainsKey('MaksTungguMenit')) { $MaksTungguMenit = 1 }
} else {
    $out = $resmi
    $faktor = @('1', '10', '50', '100', '250'); $memRuns = '3'
    $status = "PENGUKURAN RESMI $namaResmi - Bab 4"
}
$ringkasan = New-Object System.Collections.Generic.List[string]
function Catat([string]$t) { $line = '[{0}] {1}' -f (Get-Date -Format s), $t; Write-Host $line; $ringkasan.Add($line) }
function Simpan-Ringkasan { $ringkasan | Out-File -Encoding utf8 (Join-Path $out 'ringkasan_skrip.txt') }

# ---------- 1. Prasyarat ----------
if (-not (Test-Path -LiteralPath $manifest)) { Write-Host "BERHENTI: $manifest tidak ada."; exit 2 }
if (-not $UjiKering) {
    foreach ($f in @('performa_per_graf.csv', 'skalabilitas.csv', 'runs_mentah.csv')) {
        if (Test-Path -LiteralPath (Join-Path $out $f)) { Write-Host "BERHENTI: $f sudah ada di $out (tidak menimpa)."; exit 2 }
    }
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
Catat "Mulai skrip. Mode: $(if ($UjiKering) {'UJI KERING'} else {'RESMI'}). Keluaran: $out"

# ---------- 2. Hash artefak ----------
$beda = @()
$n = 0
foreach ($line in Get-Content -LiteralPath $manifest -Encoding UTF8) {
    if ($line -match '^\s*#' -or $line.Trim() -eq '') { continue }
    $parts = $line -split '  ', 2
    $path = Join-Path $dev $parts[1].Trim()
    $n++
    if (-not (Test-Path -LiteralPath $path)) { $beda += "hilang: $($parts[1])"; continue }
    $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLower()
    if ($h -ne $parts[0].Trim()) { $beda += "berubah: $($parts[1])" }
}
if ($beda.Count -gt 0) {
    Catat "BERHENTI: hash artefak tidak cocok ($($beda.Count) dari $n): $($beda -join '; ')"
    Simpan-Ringkasan; exit 3
}
Catat "Hash artefak cocok: $n berkas."

# ---------- 3. Menunggu mesin tenang ----------
function Get-CpuLoad { (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average }
function Get-CpuRerata {
    $s = @(); for ($i = 0; $i -lt 12; $i++) { $s += Get-CpuLoad; Start-Sleep -Seconds 5 }
    return [math]::Round(($s | Measure-Object -Average).Average, 1)
}
$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$uptime = (Get-Date) - $boot
Catat ("Uptime: {0:N1} menit (boot {1:s})." -f $uptime.TotalMinutes, $boot)
if ($uptime.TotalMinutes -lt $MinUptimeMenit) {
    $sisa = [math]::Ceiling(($MinUptimeMenit - $uptime.TotalMinutes) * 60)
    Catat "Menunggu $sisa detik agar uptime >= $MinUptimeMenit menit."
    Start-Sleep -Seconds $sisa
}
$tungguMulai = Get-Date
$cpu = Get-CpuRerata
Catat "Beban CPU rerata 60 detik: $cpu %"
while ($cpu -ge $AmbangCPU -and ((Get-Date) - $tungguMulai).TotalMinutes -lt $MaksTungguMenit) {
    $cpu = Get-CpuRerata
    Catat "Beban CPU rerata 60 detik: $cpu % (menunggu < $AmbangCPU %)"
}
if ($cpu -ge $AmbangCPU) { Catat "PERHATIAN: batas tunggu $MaksTungguMenit menit tercapai; beban CPU $cpu % >= $AmbangCPU %. Pengukuran tetap berjalan." }
$cpuSebelum = $cpu

# ---------- 4. Snapshot ----------
function Snapshot([string]$nama) {
    $os = Get-CimInstance Win32_OperatingSystem
    $bat = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
    $prc = Get-CimInstance Win32_Processor | Select-Object -First 1
    $l = @("Snapshot $nama - $(Get-Date -Format s)",
        ("RAM bebas MB: {0:N0} dari {1:N0}" -f ($os.FreePhysicalMemory / 1024), ($os.TotalVisibleMemorySize / 1024)),
        ("Beban CPU sesaat (%): {0}" -f (Get-CpuLoad)),
        ("Win32_Processor CurrentClockSpeed/MaxClockSpeed MHz: {0}/{1} (nilai WMI ini dapat statis; ukuran per run ada di runs_mentah.csv)" -f $prc.CurrentClockSpeed, $prc.MaxClockSpeed),
        ("Baterai: {0}" -f $(if ($bat) { "status $($bat.BatteryStatus) (2 = AC), sisa $($bat.EstimatedChargeRemaining) %" } else { 'tidak ada' })),
        ("Skema daya: {0}" -f ((powercfg /getactivescheme) -join ' ')),
        '', 'Proses teratas menurut CPU (detik kumulatif):')
    $l += (Get-Process | Sort-Object CPU -Descending | Select-Object -First 25 Name, Id,
        @{n = 'CPU_s'; e = { [math]::Round($_.CPU, 1) } }, @{n = 'WS_MB'; e = { [math]::Round($_.WorkingSet64 / 1MB) } } |
        Format-Table -AutoSize | Out-String -Width 200)
    $l += 'Proses teratas menurut memori:'
    $l += (Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 25 Name, Id,
        @{n = 'WS_MB'; e = { [math]::Round($_.WorkingSet64 / 1MB) } } | Format-Table -AutoSize | Out-String -Width 200)
    $l | Out-File -Encoding utf8 (Join-Path $out "lingkungan_$nama.txt")
}
Snapshot 'awal'

# ---------- 5-7. Daya, verifikasi, pengukuran ----------
Add-Type -Namespace Win32 -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
$asli = [regex]::Match(((powercfg /getactivescheme) -join ' '), '[0-9a-fA-F-]{36}').Value
$kodeUkur = $null
try {
    [void][Win32.Power]::SetThreadExecutionState([uint32]2147483649)   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    Catat "Sleep dicegah selama skrip berjalan. Skema daya asli: $asli"
    powercfg /setactive SCHEME_MIN 2>&1 | Out-Null
    $aktif = [regex]::Match(((powercfg /getactivescheme) -join ' '), '[0-9a-fA-F-]{36}').Value
    if ($aktif -eq $HIGH_PERF) { Catat 'Skema daya High performance aktif.' }
    else { Catat "High performance tidak tersedia; skema yang dipakai: $aktif $((powercfg /getactivescheme) -join ' ')" }
    $skemaDipakai = (powercfg /getactivescheme) -join ' '

    Set-Location $here
    $logV = Join-Path $out 'log_verifikasi_pra_ukur.txt'
    $o = & $py run_validation.py 2>&1 | ForEach-Object { "$_" }
    $kodeV = $LASTEXITCODE
    $o | Out-File -Encoding utf8 $logV
    Catat "run_validation.py: kode keluar $kodeV (log $logV)"
    if ($kodeV -ne 0) { throw "Verifikasi gagal; pengukuran tidak dijalankan." }

    $logU = Join-Path $out 'log_ukur_performa.txt'
    Catat "Mulai ukur_performa.py (faktor $($faktor -join ' '))."
    $argsU = @('-u', 'ukur_performa.py', '--runs', '10', '--mem-runs', $memRuns, '--faktor') + $faktor +
             @('--keluaran', $out, '--status', $status)
    $o = & $py @argsU 2>&1 | ForEach-Object { "$_" } | Tee-Object -Variable baris | Out-Host
    $kodeUkur = $LASTEXITCODE
    $baris | Out-File -Encoding utf8 $logU
    Catat "ukur_performa.py: kode keluar $kodeUkur (log $logU)"
}
catch {
    Catat "GALAT: $($_.Exception.Message)"
}
finally {
    if ($asli) { powercfg /setactive $asli 2>&1 | Out-Null }
    $kembali = [regex]::Match(((powercfg /getactivescheme) -join ' '), '[0-9a-fA-F-]{36}').Value
    Catat ("Skema daya dikembalikan ke {0}: {1}" -f $asli, $(if ($kembali -eq $asli) { 'OK' } else { "GAGAL (aktif $kembali)" }))
    [void][Win32.Power]::SetThreadExecutionState([uint32]2147483648)   # ES_CONTINUOUS: kembali normal
    Catat 'Pencegahan sleep dilepas.'
}

# ---------- 8. Snapshot akhir dan ringkasan ----------
Snapshot 'akhir'
Catat ("Ringkasan: uptime awal {0:N1} menit; beban CPU sebelum ukur {1} %; skema dipakai: {2}; kode ukur: {3}" -f `
    $uptime.TotalMinutes, $cpuSebelum, $skemaDipakai, $kodeUkur)
Simpan-Ringkasan
Write-Host "`nSelesai. Keluaran: $out"
if ($kodeUkur -ne 0) { exit 1 } else { exit 0 }
