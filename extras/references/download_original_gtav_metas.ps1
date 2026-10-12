param(
    [string]$Destination = (Join-Path $PSScriptRoot 'snags_original'),
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$zipUrl = 'https://github.com/CyCoSnag/snag_weapon_metas/archive/refs/heads/main.zip'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('weapon_metas_' + [guid]::NewGuid().ToString('N'))
$zipPath = Join-Path $tempRoot 'snag_weapon_metas.zip'
$extractPath = Join-Path $tempRoot 'extract'

if ((Test-Path $Destination) -and -not $Force) {
    $existing = Get-ChildItem -Path $Destination -Recurse -Filter '*.meta' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) {
        Write-Host "[OK] Referencia ya instalada: $Destination"
        exit 0
    }
}

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
try {
    Write-Host '[DOWNLOAD] Paquete original GTAV/DLC de Snag...'
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
    $source = Get-ChildItem -Path $extractPath -Directory | Select-Object -First 1
    if (-not $source) { throw 'No se encontró la carpeta extraída.' }
    $metas = Join-Path $source.FullName 'metas'
    if (-not (Test-Path $metas)) { throw 'El paquete descargado no contiene /metas.' }
    if (Test-Path $Destination) { Remove-Item -Path $Destination -Recurse -Force }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Copy-Item -Path $metas -Destination (Join-Path $Destination 'metas') -Recurse -Force
    Write-Host "[OK] Referencia instalada: $(Join-Path $Destination 'metas')"
}
finally {
    if (Test-Path $tempRoot) { Remove-Item -Path $tempRoot -Recurse -Force }
}
