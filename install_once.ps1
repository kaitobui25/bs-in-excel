param([switch]$NoAutoStart)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) {
    throw 'Python Windows launcher (pythonw.exe) not found next to python.exe.'
}
& $python -c 'import playwright.sync_api'
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install -r (Join-Path $root 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Python dependencies installation failed.' }
}
$cert = Join-Path $env:USERPROFILE '.office-addin-dev-certs\localhost.crt'
$key = Join-Path $env:USERPROFILE '.office-addin-dev-certs\localhost.key'
if (-not (Test-Path $cert) -or -not (Test-Path $key)) {
    throw 'Office development certificate missing. Use the reference L2Chart certificate installation instructions.'
}
$certInfo = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 $cert
if ($certInfo.NotAfter -le (Get-Date)) { throw 'Office localhost certificate has expired. Renew it before installing.' }
$entry = Join-Path $root 'run_addin.pyw'
$command = '"'+$pythonw+'" "'+$entry+'"'
if (-not $NoAutoStart) {
    $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    New-Item -Path $runKey -Force | Out-Null
    Set-ItemProperty -Path $runKey -Name 'BSInExcelTextBrowser' -Value $command
}
$alreadyListening = Get-NetTCPConnection -LocalPort 3010 -State Listen -ErrorAction SilentlyContinue
if (-not $alreadyListening) {
    Start-Process -FilePath $pythonw -ArgumentList @(('"' + $entry + '"')) -WorkingDirectory $root -WindowStyle Hidden
}
Write-Host 'Backend configured. The Excel add-in manifest is:'
Write-Host (Join-Path $root 'addin\manifest.xml')
Write-Host 'Upload this manifest in Excel: Home > Add-ins > My Add-ins > Upload My Add-in (once).'
