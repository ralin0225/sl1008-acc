$ErrorActionPreference = 'Stop'
$taskBase = $PSScriptRoot
$graphdbDist = 'C:\Users\dyp\AppData\Local\Programs\GraphDB-10.6.4\graphdb\graphdb-10.6.4'
$javaExe = 'C:\Users\dyp\AppData\Local\Programs\GraphDB-10.6.4\java\jdk-17.0.20.1+1-jre\bin\java.exe'
try {
    $existing = Invoke-RestMethod -Uri 'http://localhost:7200/rest/info/version' -TimeoutSec 2
    if ($existing) { Write-Output 'GraphDB is already running: http://localhost:7200/'; exit 0 }
} catch { }
New-Item -ItemType Directory -Path (Join-Path $taskBase 'home') -Force | Out-Null
$javaArgs = @(
    '-Xms256m', '-Xmx2g', '-XX:MaxDirectMemorySize=2g',
    '--add-opens=java.base/java.lang=ALL-UNNAMED',
    '-Djava.awt.headless=true', '-Dfile.encoding=UTF-8', '-XX:-OmitStackTraceInFastThrow',
    "-Dgraphdb.dist=$graphdbDist",
    "-Dgraphdb.home=$taskBase\home",
    '-Dgraphdb.connector.address=127.0.0.1',
    '-Dgraphdb.connector.port=7200',
    '-Dgraphdb.foreground=yes',
    "-Dgraphdb.pidfile=$taskBase\graphdb.pid",
    '-cp', "$graphdbDist\lib\*", 'com.ontotext.graphdb.server.GraphDBWorkbench'
)
$proc = Start-Process -FilePath $javaExe -ArgumentList $javaArgs -WorkingDirectory $graphdbDist -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskBase 'stdout.log') -RedirectStandardError (Join-Path $taskBase 'stderr.log') -PassThru
$proc.Id | Set-Content -LiteralPath (Join-Path $taskBase 'launcher.pid')
Write-Output "GraphDB started (process $($proc.Id)): http://localhost:7200/"
