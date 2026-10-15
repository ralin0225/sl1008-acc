$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Start-GraphDB.ps1')
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $version = Invoke-RestMethod -Uri 'http://localhost:7200/rest/info/version' -TimeoutSec 2
        if ($version.productVersion -eq '10.6.4') {
            Start-Process 'http://localhost:7200/'
            exit 0
        }
    } catch { }
    Start-Sleep -Seconds 2
}
throw 'GraphDB did not finish starting. See stdout.log and stderr.log.'
