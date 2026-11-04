# Konum toplayıcısını süresiz çalıştırır (Windows zamanlanmış görevi "iett-dakiklik toplayici").
# Görev oturum açılınca ve her sabah başlar; zaten çalışıyorsa ikinci kopya açılmaz.
# Yönlendirme cmd ile: PowerShell 5.1'in >> işleci dosyayı UTF-16 yazıyor.
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
cmd /c ".venv\Scripts\python.exe toplayici.py >> veri\toplayici.log 2>&1"
