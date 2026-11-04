# Günlük özet ve yayın, bu bilgisayardan (Windows zamanlanmış görevi "iett-dakiklik gunluk").
# Ham konumları toplayici_calistir.ps1 toplar; bu betik özetler, site verisini üretir ve gönderir.
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
Start-Transcript -Append -Path (Join-Path $PSScriptRoot "veri\yerel_guncelle.log") | Out-Null
try {
    git pull --ff-only -q
    .\.venv\Scripts\python.exe ozetle.py
    if ($LASTEXITCODE -ne 0) { throw "ozetle.py başarısız ($LASTEXITCODE)" }
    .\.venv\Scripts\python.exe site_uret.py
    if ($LASTEXITCODE -ne 0) { throw "site_uret.py başarısız ($LASTEXITCODE)" }
    git add veri/ozet veri/plan site/veri
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -q -m ("Veri: " + (Get-Date).ToString("yyyy-MM-dd") + " (yerel görev)")
        git push -q
        if ($LASTEXITCODE -ne 0) { throw "git push başarısız" }
    } else { "değişiklik yok" }
} catch { "HATA: $_" } finally { Stop-Transcript | Out-Null }
