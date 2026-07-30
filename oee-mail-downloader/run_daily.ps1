$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

uv run python main.py --today

if ($LASTEXITCODE -ne 0) {
    throw "Mail downloader ended with exit code $LASTEXITCODE"
}
