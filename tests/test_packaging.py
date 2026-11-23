"""Tests of the packaging: the versions agree, and the files that make the
RPM and the AppImage are sound."""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from py_redact import __version__

ROOT = Path(__file__).resolve().parent.parent


def spec_field(name: str) -> str:
    m = re.search(rf"^{name}:\s*(\S+)", (ROOT / "packaging/py-redact.spec").read_text(), re.M)
    return m.group(1) if m else ""


def test_versions_agree():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["version"] == __version__
    assert spec_field("Version") == __version__, "bump the spec: rpmdev-bumpspec -n VERSION"


def test_spec_changelog_has_this_version():
    changelog = (ROOT / "packaging/py-redact.spec").read_text().split("%changelog", 1)[1]
    first = next(line for line in changelog.splitlines() if line.startswith("*"))
    assert first.rstrip().endswith(f"- {__version__}-{spec_field('Release').split('%')[0]}")


@pytest.mark.skipif(not shutil.which("desktop-file-validate"), reason="desktop-file-utils not installed")
def test_desktop_file():
    r = subprocess.run(["desktop-file-validate", str(ROOT / "packaging/py-redact.desktop")],
                       capture_output=True, text=True)
    assert r.stdout + r.stderr == ""


def test_scripts_parse():
    assert subprocess.run(["bash", "-n", str(ROOT / "packaging/build-rpm.sh")]).returncode == 0
    for tool in ("release.py", "sign_release.py", "bundle-appimage.py", "icons.py"):
        compile((ROOT / "tools" / tool).read_text(), tool, "exec")


@pytest.mark.skipif(not shutil.which("rpmspec"), reason="rpm-build not installed")
def test_spec_parses():
    r = subprocess.run(["rpmspec", "-q", "--srpm", "--qf", "%{version}", str(ROOT / "packaging/py-redact.spec")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == __version__, r.stderr


def pinned_key() -> str:
    m = re.search(r'SIGNING_KEY="\$\{SIGNING_KEY:-([0-9A-F]{40})\}"', (ROOT / "packaging/build-rpm.sh").read_text())
    assert m, "build-rpm.sh must pin the project's signing key"
    return m.group(1)


@pytest.mark.skipif(not shutil.which("gpg"), reason="gpg not installed")
def test_the_shipped_key_is_the_pinned_one(tmp_path):
    r = subprocess.run(["gpg", "--batch", "--with-colons", "--show-keys",
                        str(ROOT / "packaging/RPM-GPG-KEY-py-redact")],
                       capture_output=True, text=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    fprs = [line.split(":")[9] for line in r.stdout.splitlines() if line.startswith("fpr:")]
    assert fprs and fprs[0] == pinned_key()


@pytest.mark.skipif(not all(shutil.which(t) for t in ("gpg", "git", "rpmbuild", "rpmspec")),
                    reason="gpg, git or rpm-build not installed")
def test_signing_without_the_key_says_how_to_import_it(tmp_path):
    """--sign uses only the pinned key: with an empty keyring it stops before building."""
    env = {"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin", "RPMSIGN": "/bin/true"}
    r = subprocess.run(["bash", str(ROOT / "packaging/build-rpm.sh"), "--sign"], capture_output=True, text=True,
                       env=env)
    assert r.returncode == 1
    assert f"no secret key matching {pinned_key()}" in r.stderr and "gpg --import" in r.stderr


@pytest.mark.skipif(not (ROOT / "install").is_dir(), reason="the installers are not here")
def test_installers(tmp_path):
    """The installers parse, explain themselves, and refuse what they can't do."""
    sh = ROOT / "install/install.sh"
    assert subprocess.run(["bash", "-n", str(sh)]).returncode == 0
    r = subprocess.run(["bash", str(sh), "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "--uninstall" in r.stdout and "#" not in r.stdout
    r = subprocess.run(["bash", str(sh), "--python", str(tmp_path / "none")], capture_output=True, text=True,
                       env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 1 and "3.14 or later" in r.stderr
    assert not (tmp_path / ".local").exists()  # (nothing made)
    ps1 = (ROOT / "install/install.ps1").read_text()
    assert "param(" in ps1 and "-m py_redact.gui" in ps1 and "LOCALAPPDATA" in ps1
    assert ps1.isascii()  # (Windows PowerShell reads a file without a BOM as ANSI)
    assert "install.ps1" in (ROOT / "install/install.bat").read_text()


@pytest.mark.skipif(not shutil.which("uv"), reason="uv not installed")
def test_the_appimage_takes_the_locked_versions(tmp_path):
    """The AppImage gets PyMuPDF and PySide6 in the versions of uv.lock, those the tests run with."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("bundle", ROOT / "tools" / "bundle-appimage.py")
    bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle)
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    locked = {p["name"]: p["version"] for p in lock["package"]}
    wanted = bundle.locked(tmp_path).read_text().split()
    assert f"pymupdf=={locked['pymupdf']}" in wanted and f"pyside6-essentials=={locked['pyside6-essentials']}" in wanted
