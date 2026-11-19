<#
Installs py-redact from this folder of its source, for this user, on
Windows, to run with Python (3.14 or later): no binaries are built.

    install\install.bat                     install, or update
    install\install.bat -Python C:\...\python.exe   with that Python
    install\install.bat -Desktop            also a shortcut on the desktop
    install\install.bat -Uninstall          remove what it installed

(install.bat runs this script, install.ps1, with PowerShell.)

It makes a virtual environment of its own, %LOCALAPPDATA%\py-redact\venv,
and installs py-redact in it, with PyMuPDF and PySide6 from PyPI (so it
needs internet the first time); then it adds py-redact to the Start menu.
Nothing needs to be run as administrator, and nothing is put anywhere
else; the settings (%APPDATA%\py-redact) are never touched.

py-redact: Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
SPDX-License-Identifier: GPL-3.0-or-later (see LICENSE)
#>

param(
    [string]$Python = "",
    [switch]$Desktop,
    [switch]$Uninstall,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$Name = "py-redact"
$Root = Split-Path -Parent $PSScriptRoot
$Data = Join-Path $env:LOCALAPPDATA $Name
$Venv = Join-Path $Data "venv"
$Icon = Join-Path $Data "$Name.ico"
$StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "$Name.lnk"
$OnDesktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "$Name.lnk"

function Say($text) { Write-Host "==> $text" }

function Fail($text) {
    Write-Host "install.ps1: $text" -ForegroundColor Red
    exit 1
}

# ----------------------------------------------------------------- Python

# The full path of a Python 3.14 or later with venv and pip, run as COMMAND (an array:
# the program and its arguments, such as "py", "-3.14"), or $null.
function Test-Python([string[]]$command) {
    $program = $command[0]
    $arguments = @()
    if ($command.Count -gt 1) { $arguments = $command[1..($command.Count - 1)] }
    try {
        $out = & $program @arguments -c "import sys, venv, ensurepip; print(sys.executable) if sys.version_info >= (3, 14) else None" 2>$null
    } catch {
        return $null
    }
    if ($LASTEXITCODE -eq 0 -and $out) { return ($out | Select-Object -Last 1).Trim() }
    return $null
}

function Find-Python {
    $candidates = @(@("py", "-3.16"), @("py", "-3.15"), @("py", "-3.14"), @("python"), @("python3"))
    foreach ($candidate in $candidates) {
        if (Get-Command $candidate[0] -ErrorAction SilentlyContinue) {
            $found = Test-Python $candidate
            if ($found) { return $found }
        }
    }
    return $null
}

function No-Python {
    Write-Host "install.ps1: py-redact needs Python 3.14 or later." -ForegroundColor Red
    Write-Host "  Install it from https://www.python.org/downloads/windows/ (the Python install"
    Write-Host "  manager, or the installer of 3.14), and run this again; or give it with -Python."
    exit 1
}

# ----------------------------------------------------------------- installing

# The icon of the shortcuts: an .ico made of the PNG icons (an .ico may hold PNGs as they are).
$MakeIcon = @'
import struct, sys
from pathlib import Path
icons, target = Path(sys.argv[1]), Path(sys.argv[2])
pngs = [(icons / f"{s}x{s}" / "apps" / "py-redact.png").read_bytes() for s in (16, 24, 32, 48, 64, 128, 256)]
sizes = (16, 24, 32, 48, 64, 128, 256)
head = struct.pack("<HHH", 0, 1, len(pngs))
offset = 6 + 16 * len(pngs)
entries = b""
for size, png in zip(sizes, pngs):
    entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset)
    offset += len(png)
target.write_bytes(head + entries + b"".join(pngs))
'@

function New-Shortcut([string]$path) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($path)
    # (pythonw: no console window; -m py_redact.gui: the window)
    $link.TargetPath = Join-Path $Venv "Scripts\pythonw.exe"
    $link.Arguments = "-m py_redact.gui"
    $link.WorkingDirectory = $HOME
    $link.IconLocation = "$Icon,0"
    $link.Description = "Redact PDF documents"
    $link.Save()
}

function Install-PyRedact {
    if (-not ((Test-Path (Join-Path $Root "pyproject.toml")) -and (Test-Path (Join-Path $Root "src\py_redact")))) {
        Fail "run it from the folder of py-redact's source (cloned, or the zip unpacked)"
    }
    if ($Python) {
        $found = Test-Python @($Python)
        if (-not $found) { No-Python }
    } else {
        $found = Find-Python
        if (-not $found) { No-Python }
    }
    $version = & $found -c "import sys; print(sys.version.split()[0])"
    Say "Python: $found ($version)"
    Say "Making the environment: $Venv"
    New-Item -ItemType Directory -Force -Path $Data | Out-Null
    & $found -m venv --clear $Venv
    if ($LASTEXITCODE -ne 0) { Fail "the environment could not be made" }
    $venvPython = Join-Path $Venv "Scripts\python.exe"
    Say "Installing py-redact, PyMuPDF and PySide6 in it (this takes a while the first time)"
    & $venvPython -m pip install --quiet --upgrade pip
    & $venvPython -m pip install --quiet $Root
    if ($LASTEXITCODE -ne 0) { Fail "py-redact could not be installed (see the messages above)" }
    Say "Checking that it starts"
    & $venvPython -m py_redact --version
    if ($LASTEXITCODE -ne 0) { Fail "py-redact was installed, but doesn't start" }
    # (from a file: Windows PowerShell would spoil the quotes of a script given with -c)
    $maker = Join-Path $Data "make-icon.py"
    Set-Content -Path $maker -Value $MakeIcon -Encoding ASCII
    & $venvPython $maker (Join-Path $Root "src\py_redact\icons\linux\hicolor") $Icon
    Remove-Item -Force $maker
    Say "Installed:"
    New-Shortcut $StartMenu
    Write-Host "  in the Start menu: $StartMenu"
    if ($Desktop) {
        New-Shortcut $OnDesktop
        Write-Host "  on the desktop: $OnDesktop"
    }
    Write-Host "  the command: $(Join-Path $Venv 'Scripts\py-redact.exe')"
    Write-Host ""
    Write-Host "Start it from the Start menu (py-redact). To update it, run this again after"
    Write-Host "updating the source; to remove it, install\install.bat -Uninstall."
}

function Uninstall-PyRedact {
    Say "Removing py-redact"
    foreach ($path in @($StartMenu, $OnDesktop, $Icon)) {
        if (Test-Path $path) {
            Remove-Item -Force $path
            Write-Host "  $path"
        }
    }
    if (Test-Path $Venv) {
        Remove-Item -Recurse -Force $Venv
        Write-Host "  $Venv"
    }
    if ((Test-Path $Data) -and -not (Get-ChildItem $Data -Force)) { Remove-Item -Force $Data }
    Write-Host "The settings and the redaction codes were kept, in $(Join-Path $env:APPDATA $Name)."
}

if ($Help) {
    Get-Content $PSCommandPath | Select-Object -Skip 1 -First 18
    exit 0
}
if ($Uninstall) { Uninstall-PyRedact } else { Install-PyRedact }
