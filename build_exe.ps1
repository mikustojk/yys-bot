$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $root "script_launcher.cs"
$output = Join-Path $root "script.exe"

if (!(Test-Path -LiteralPath $source)) {
    throw "Missing source file: $source"
}

Add-Type -TypeDefinition (Get-Content -LiteralPath $source -Raw -Encoding UTF8) `
    -ReferencedAssemblies "System.Windows.Forms", "System.Drawing" `
    -OutputAssembly $output `
    -OutputType WindowsApplication

Write-Host "Created: $output"
