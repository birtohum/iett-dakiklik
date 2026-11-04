# Konum toplayıcısını süresiz çalıştırır (Windows zamanlanmış görevi "iett-dakiklik toplayici").
# Görev oturum açılınca ve her sabah başlar; zaten çalışıyorsa ikinci kopya açılmaz.
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe toplayici.py *>> (Join-Path $PSScriptRoot "veri\toplayici.log")
