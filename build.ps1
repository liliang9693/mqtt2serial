param(
    [string]$Name = "MQTT2Serial"
)
$ErrorActionPreference = "Stop"
python -m pip install -U pip
python -m pip install -r requirements.txt
try { Get-Process -Name $Name -ErrorAction SilentlyContinue | Stop-Process -Force } catch {}
python assets\make_icon.py

# 动态收集需要打入exe的DLL并作为 --add-binary 参数传入
$prefix = python -c "import sys; print(sys.base_prefix)"
$libBin = Join-Path $prefix "Library\bin"
$dllsDir = Join-Path $prefix "DLLs"
$patterns = @("ffi-*.dll","libcrypto-*.dll","libssl-*.dll","liblzma*.dll","libbz2*.dll")
$addBinArgs = @()
foreach ($pat in $patterns) {
    Get-ChildItem -Path $libBin -Filter $pat -ErrorAction SilentlyContinue | ForEach-Object { $addBinArgs += "--add-binary"; $addBinArgs += ("{0};." -f $_.FullName) }
    Get-ChildItem -Path $dllsDir -Filter $pat -ErrorAction SilentlyContinue | ForEach-Object { $addBinArgs += "--add-binary"; $addBinArgs += ("{0};." -f $_.FullName) }
}

# 额外打包资源文件（icon）
$addDataArgs = @("--add-data","assets\icon.ico;assets")

python -m PyInstaller --noconfirm --onefile --windowed --name $Name --icon assets\icon.ico main.py @addBinArgs @addDataArgs

$distDir = Join-Path (Get-Location) "dist"
Write-Output "EXE built (single-file): $distDir/$Name.exe"
