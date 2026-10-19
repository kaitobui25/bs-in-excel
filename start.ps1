param([string]$Url = 'https://www.siemens.com/ja-jp/products/tia-portal/')
$ErrorActionPreference = 'Stop'
$python = (Get-Command python -ErrorAction Stop).Source
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$data = Join-Path $env:LOCALAPPDATA 'bs-in-excel'
New-Item -ItemType Directory -Path $data -Force | Out-Null
Push-Location $root
try {
    & $python -c "import playwright.sync_api, win32com.client"
    if ($LASTEXITCODE -ne 0) { throw 'Install dependencies: python -m pip install -r requirements.txt' }
    $args = @('-m','text_browser','--url',('"' + $Url + '"'))
    $process = Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $data 'stdout.log') -RedirectStandardError (Join-Path $data 'stderr.log')
    Write-Host "Excel Text Browser started. PID: $($process.Id)"
    Write-Host "In Excel, open Text Browser sheet and type in C4."
} finally { Pop-Location }
