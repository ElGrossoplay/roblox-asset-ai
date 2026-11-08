# Descarga Blender LTS portable (oficial, download.blender.org) dentro del disco externo.
# Uso: powershell -ExecutionPolicy Bypass -File tools\instalar_blender.ps1 [-Serie 4.5]
param([string]$Serie = "4.5")
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$raiz = Split-Path -Parent $PSScriptRoot
$destino = Join-Path $raiz "runtime\blender"
$cache = Join-Path $raiz "cache"
New-Item -ItemType Directory -Force -Path $destino, $cache | Out-Null

$base = "https://download.blender.org/release/Blender$Serie/"
Write-Host "Buscando la ultima version de Blender $Serie LTS..."
$lista = (Invoke-WebRequest -UseBasicParsing -Uri $base).Content
$patron = "blender-" + [regex]::Escape($Serie) + "\.(\d+)-windows-x64\.zip"
$versiones = [regex]::Matches($lista, $patron) | ForEach-Object { [int]$_.Groups[1].Value } | Sort-Object -Unique -Descending
if (-not $versiones) { throw "No se encontro un .zip para Windows en $base" }
$parche = $versiones[0]
$nombre = "blender-$Serie.$parche-windows-x64.zip"
$zip = Join-Path $cache $nombre

if (Test-Path (Join-Path $destino "blender-$Serie.$parche-windows-x64\blender.exe")) {
    Write-Host "Blender $Serie.$parche ya esta instalado."; exit 0
}
Write-Host "Descargando $nombre (unos 350 MB)..."
Invoke-WebRequest -UseBasicParsing -Uri ($base + $nombre) -OutFile $zip

# verificacion de integridad con el SHA-256 oficial (si el archivo de sumas existe)
$esperado = $null
try {
    $sumas = (Invoke-WebRequest -UseBasicParsing -Uri ($base + "blender-$Serie.$parche.sha256")).Content
    if ($sumas -is [byte[]]) { $sumas = [Text.Encoding]::ASCII.GetString($sumas) }
    $esperado = ([regex]::Match($sumas, "([0-9a-fA-F]{64})\s+\*?" + [regex]::Escape($nombre))).Groups[1].Value
} catch { Write-Host "Aviso: no se pudo descargar el archivo de sumas SHA-256 (continua sin verificar)." }
if ($esperado) {
    $real = (Get-FileHash $zip -Algorithm SHA256).Hash
    if ($real -ne $esperado.ToUpper()) { Remove-Item $zip; throw "SHA-256 no coincide: descarga corrupta, vuelve a intentarlo" }
    Write-Host "Integridad verificada (SHA-256 OK)."
}

Write-Host "Descomprimiendo..."
if (Get-Command tar.exe -ErrorAction SilentlyContinue) { tar.exe -xf $zip -C $destino }
else { Expand-Archive -Force $zip $destino }
Remove-Item $zip
$exe = Get-ChildItem -Path $destino -Recurse -Filter blender.exe | Select-Object -First 1
if (-not $exe) { throw "No se encontro blender.exe tras descomprimir" }
& $exe.FullName -b --factory-startup --version | Select-Object -First 1
Write-Host "Listo: $($exe.FullName)"
