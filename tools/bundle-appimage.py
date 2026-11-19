#!/usr/bin/env python3
"""Make an AppImage of py-redact, for Linux:

    uv run python tools/bundle-appimage.py [-o FOLDER] [--python APPIMAGE]
                                          [--python-version 3.14] [--appimagetool APPIMAGE]

The AppImage is dist/py-redact-VERSION-x86_64.AppImage (the version of
pyproject.toml; --output gives another folder). It holds a Python of its own
(a relocatable Python of the python-appimage project,
https://github.com/niess/python-appimage) with py-redact and everything it
needs installed into it (PyMuPDF, PySide6), so it runs on any recent Linux
(glibc 2.34 or later: Ubuntu 22.04, Debian 12, Fedora 35 and later) without
installing anything.

    py-redact.AppImage [file.pdf]

What it needs is downloaded the first time and kept in the user's cache
folder (~/.cache/py-redact-build): the Python and appimagetool
(https://github.com/AppImage/appimagetool). The program's wheel is made with
"uv build", and its dependencies come from PyPI (so this needs the network),
in the versions of uv.lock: the AppImage runs the PyMuPDF and the PySide6
that the tests ran with, not whatever is newest on PyPI that day.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
APP_ID = "py-redact"
ARCH = "x86_64"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]

# The Python put in the AppImage (python-appimage has one release per version,
# with an AppImage per manylinux; PySide6 needs glibc 2.34 anyway).
PYTHON = "3.14"
PYTHON_RELEASES = "https://api.github.com/repos/niess/python-appimage/releases/tags/python{version}"
MANYLINUX = ("manylinux_2_28", "manylinux2014")
APPIMAGETOOL = f"https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-{ARCH}.AppImage"

# Parts of PySide6/Qt the program doesn't use (QML/Quick, the designer and
# other tools, headers, type stubs), left out to make the AppImage smaller.
PRUNE = [
    "PySide6/Qt/qml", "PySide6/Qt/libexec", "PySide6/include", "PySide6/typesystems", "PySide6/glue",
    "PySide6/scripts", "PySide6/examples", "PySide6/doc",
    "PySide6/designer", "PySide6/assistant", "PySide6/linguist", "PySide6/lrelease", "PySide6/lupdate",
    "PySide6/qmlformat", "PySide6/qmllint", "PySide6/qmlls", "PySide6/qmlcachegen", "PySide6/qmlimportscanner",
    "PySide6/qmltyperegistrar", "PySide6/balsam", "PySide6/balsamui", "PySide6/svgtoqml", "PySide6/qsb",
    "PySide6/rcc", "PySide6/uic", "PySide6/Qt/plugins/designer", "PySide6/Qt/plugins/qmltooling",
    "PySide6/Qt/plugins/qmllint",
    # (1.0.9: what the window doesn't use either: Qt's tables of types, used
    # only when building; databases, tests, forms read at run time, Lottie
    # animations, the Labs modules, a Wayland compositor (a client is what a
    # window is), EGLFS (Qt on a screen with no desktop); pip and the headers
    # of MuPDF, which only building needs)
    "PySide6/Qt/metatypes", "PySide6/Qt/plugins/sqldrivers", "PySide6/Qt/plugins/egldeviceintegrations",
    "PySide6/Qt/plugins/wayland-graphics-integration-server", "PySide6/Qt/plugins/platforms/libqeglfs.so",
    "PySide6/Qt/plugins/vectorimageformats/libqlottievectorimage.so",
    "pip", "build", "pyproject_hooks", "pymupdf/mupdf-devel",
    # (and what needed libraries that were never there, or are left out above:
    # it couldn't be loaded anyway)
    "PySide6/Qt/plugins/imageformats/libqpdf.so",
    "PySide6/Qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.so",
]
PRUNE_GLOBS = ["PySide6/*.pyi", "PySide6/Qt/lib/libQt6Designer*", "PySide6/Qt/lib/libQt6Qml*",
               "PySide6/Qt/lib/libQt6Quick*", "PySide6/Qt/lib/libQt6ShaderTools*", "PySide6/Qt/lib/libQt6Help*",
               "PySide6/QtQml*", "PySide6/QtQuick*", "PySide6/QtDesigner*", "PySide6/QtHelp*",
               "PySide6/Qt/translations/assistant_*", "PySide6/Qt/translations/designer_*",
               "PySide6/Qt/translations/linguist_*", "PySide6/Qt/translations/qtdeclarative_*",
               "PySide6/Qt/translations/qt_help_*",
               "PySide6/Qt/lib/libQt6Sql*", "PySide6/QtSql*", "PySide6/Qt/lib/libQt6Test*", "PySide6/QtTest*",
               "PySide6/Qt/lib/libQt6UiTools*", "PySide6/QtUiTools*", "PySide6/Qt/lib/libQt6Lottie*",
               "PySide6/Qt/lib/libQt6Labs*", "PySide6/QtLabs*", "PySide6/Qt/lib/libQt6WaylandCompositor*",
               "PySide6/Qt/lib/libQt6WaylandEglCompositor*", "PySide6/QtWaylandCompositor*",
               "PySide6/Qt/lib/libQt6EglFs*", "PySide6/libpyside6qml*", "pip-*.dist-info", "build-*.dist-info", "pyproject_hooks-*.dist-info"]
# Qt's own texts are kept in the languages of the program only
LANGUAGES = ("en", "es")
# Parts of the Python itself the program doesn't use: Tk, IDLE, the turtle,
# the installer of pip, pydoc's topics (relative to the AppDir)
PRUNE_PYTHON = ["opt/python3*/lib/python3.*/tkinter", "opt/python3*/lib/python3.*/idlelib",
                "opt/python3*/lib/python3.*/turtledemo", "opt/python3*/lib/python3.*/ensurepip",
                "opt/python3*/lib/python3.*/pydoc_data", "opt/python3*/lib/python3.*/lib-dynload/_tkinter*",
                "usr/share/tcltk", "usr/lib/libtcl*", "usr/lib/libtk*"]

DESKTOP = (ROOT / "packaging" / f"{APP_ID}.desktop").read_text(encoding="utf-8")

# %(python)s: the interpreter, relative to the AppDir
APPRUN = r"""#!/bin/bash
#  Starts py-redact in the AppImage (made by tools/bundle-appimage.py).
ROOT="$(dirname "$(readlink -f -- "$0")")"
export APPDIR="${APPDIR:-$ROOT}"
PYTHON="$APPDIR/%(python)s"
#  (the AppImage cannot be written to)
export PYTHONDONTWRITEBYTECODE=1
#  Only what is inside the AppImage: not the user's site-packages, nor
#  another Python's settings
export PYTHONNOUSERSITE=1
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP VIRTUAL_ENV
exec "$PYTHON" -m py_redact.gui "$@"
"""


def say(text: str):
    print(text, file=sys.stderr, flush=True)


def name() -> str:
    return f"{APP_ID}-{VERSION}-{ARCH}.AppImage"


def cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    path = base / "py-redact-build"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download(url: str, path: Path) -> Path:
    """Download URL into PATH (unless it is there already)."""
    if not path.is_file():
        say(f"Downloading {url} ...")
        tmp = path.with_name(path.name + ".tmp")
        with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(tmp, path)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def python_appimage(version: str) -> Path:
    """The Python AppImage of VERSION, for the newest manylinux there is one for."""
    url = PYTHON_RELEASES.format(version=version)
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as r:
        assets = json.load(r)["assets"]
    tag = "cp" + version.replace(".", "")
    for manylinux in MANYLINUX:
        end = f"-{tag}-{tag}-{manylinux}_{ARCH}.AppImage"  # (not the free-threaded cp3XXt)
        found = [a["browser_download_url"] for a in assets if a["name"].endswith(end)]
        if found:
            return download(found[0], cache_dir() / found[0].rsplit("/", 1)[1])
    raise OSError(f"there is no Python {version} AppImage at {url}")


def wheel(folder: Path) -> Path:
    """The program's wheel, made with uv build."""
    if not shutil.which("uv"):
        raise OSError("uv is needed to make the wheel (https://docs.astral.sh/uv/)")
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(folder)], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    found = sorted(folder.glob(f"py_redact-{VERSION}-*.whl"))
    if not found:
        raise OSError("uv build made no wheel")
    return found[0]


def locked(folder: Path) -> Path:
    """The versions of uv.lock, as a file of constraints for pip."""
    target = folder / "constraints.txt"
    subprocess.run(["uv", "export", "--frozen", "--no-dev", "--no-hashes", "--no-emit-project",
                    "--no-header", "--no-annotate", "-o", str(target)], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    return target


def make_appdir(appdir: Path, whl: Path):
    """Turn the AppDir of the Python into that of py-redact."""
    pythons = [p for p in sorted(appdir.glob("opt/python3*/bin/python3.*")) if not p.name.endswith("-config")]
    if not pythons:
        raise OSError(f"there is no Python in {appdir}")
    python = pythons[0]
    say(f"Installing py-redact and its dependencies into {python.relative_to(appdir)} ...")
    # Everything must go inside: pip must not see packages of the user's
    # site-packages (or another environment) as already installed.
    env = clean_env()
    subprocess.run([str(python), "-s", "-m", "pip", "install", "--isolated", "--no-cache-dir",
                    "--no-warn-script-location", "--disable-pip-version-check", "--quiet",
                    "-c", str(locked(whl.parent)), str(whl)],
                   check=True, env=env)
    site = next(appdir.glob("opt/python3*/lib/python3.*/site-packages"))
    for rel in PRUNE:
        path = site / rel
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    for pattern in PRUNE_GLOBS:
        for path in site.glob(pattern):
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    for path in (site / "PySide6" / "Qt" / "translations").glob("*.qm"):
        if path.stem.rsplit("_", 1)[-1] not in LANGUAGES:
            path.unlink()
    for pattern in PRUNE_PYTHON:
        for path in appdir.glob(pattern):
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    missing_libraries(site / "PySide6")
    # Out with what makes it the Python's AppImage
    for pattern in ("AppRun", "*.desktop", "*.png", "*.svg", ".DirIcon", "usr/share/applications",
                    "usr/share/metainfo"):
        for path in appdir.glob(pattern):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
    apprun = appdir / "AppRun"
    apprun.write_text(APPRUN % {"python": python.relative_to(appdir)},
                      encoding="utf-8", newline="\n")
    apprun.chmod(0o755)
    (appdir / f"{APP_ID}.desktop").write_text(DESKTOP, encoding="utf-8", newline="\n")
    icons = ROOT / "src" / "py_redact" / "icons" / "linux" / "hicolor"
    shutil.copy2(icons / "256x256" / "apps" / f"{APP_ID}.png", appdir / f"{APP_ID}.png")
    os.symlink(f"{APP_ID}.png", appdir / ".DirIcon")
    shutil.copytree(icons, appdir / "usr" / "share" / "icons" / "hicolor", dirs_exist_ok=True)


def missing_libraries(pyside: Path):
    """Make sure that every library and plugin of Qt left finds the Qt
    libraries it needs (none of them was left out by mistake)."""
    if not shutil.which("readelf"):
        say("(readelf is not installed: the libraries of Qt were not checked)")
        return
    have = {p.name for p in (pyside / "Qt" / "lib").iterdir()}
    wrong = []
    for path in sorted(pyside.rglob("*.so*")):
        if not path.is_file() or path.is_symlink():
            continue
        r = subprocess.run(["readelf", "-d", str(path)], capture_output=True, text=True)
        for name in re.findall(r"\(NEEDED\)\s+Shared library: \[(libQt6[^\]]+)\]", r.stdout):
            if name not in have:
                wrong.append(f"{path.relative_to(pyside)} needs {name}")
    if wrong:
        raise OSError("Qt libraries left out that others need:\n  " + "\n  ".join(wrong))


def clean_env(**extra) -> dict:
    """The environment without anything that would make a Python look outside its own folders."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PYTHON", "PIP_", "VIRTUAL_ENV", "UV_", "CONDA"))}
    env.update(PYTHONNOUSERSITE="1", **extra)
    return env


def check_imports(appdir: Path):
    """Stop if the bundled Python can't import what the program needs, on its own."""
    python = next(p for p in sorted(appdir.glob("opt/python3*/bin/python3.*")) if not p.name.endswith("-config"))
    code = ("import pymupdf, PySide6, py_redact.gui.window; from py_redact.redact import Box, redact; "
            "d = pymupdf.open(); d.new_page().insert_text((72, 72), 'secret'); "
            "assert redact(d, [Box(0, (60, 50, 200, 80))]) == 1 and 'secret' not in d[0].get_text(); "
            "print(pymupdf.VersionBind, PySide6.__version__)")
    r = subprocess.run([str(python), "-s", "-c", code], capture_output=True, text=True,
                       env=clean_env(QT_QPA_PLATFORM="offscreen", APPDIR=str(appdir)))
    if r.returncode != 0:
        raise OSError(f"the bundled Python cannot run the program:\n{r.stderr.strip()}")
    say(f"Bundled PyMuPDF, PySide6: {r.stdout.strip()} (a redaction works)")


def smoke_test(appimage: Path):
    """Run the AppImage as a user with nothing installed would: an empty home folder."""
    with tempfile.TemporaryDirectory() as home:
        env = clean_env(HOME=home, XDG_CONFIG_HOME=f"{home}/.config", XDG_CACHE_HOME=f"{home}/.cache",
                        XDG_DATA_HOME=f"{home}/.local/share", APPIMAGE_EXTRACT_AND_RUN="1")
        r = subprocess.run([str(appimage), "--version"], capture_output=True, text=True, env=env, cwd=home)
        if r.returncode != 0 or VERSION not in r.stdout:
            raise OSError(f"the AppImage failed (--version):\n{(r.stderr or r.stdout).strip()}")
    say("The AppImage runs on its own (empty home folder): --version.")


def open_to_all(appdir: Path):
    """Let everyone read the AppDir: folders 0755, files 0644, or 0755 if they can be run."""
    for folder, dirs, names in os.walk(appdir):
        for d in dirs:
            p = Path(folder, d)
            if not p.is_symlink():
                p.chmod(0o755)
        for n in names:
            p = Path(folder, n)
            if not p.is_symlink():
                p.chmod(0o755 if p.stat().st_mode & stat.S_IXUSR else 0o644)
    appdir.chmod(0o755)


def bundle(output: Path, python: Path | None = None, appimagetool: Path | None = None,
           version: str = PYTHON) -> Path:
    python = python or python_appimage(version)
    appimagetool = appimagetool or download(APPIMAGETOOL, cache_dir() / Path(APPIMAGETOOL).name)
    path = output / name()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        subprocess.run([str(python.resolve()), "--appimage-extract"], cwd=tmp, check=True,
                       stdout=subprocess.DEVNULL)
        appdir = tmp / "squashfs-root"
        make_appdir(appdir, wheel(tmp / "wheel"))
        check_imports(appdir)
        open_to_all(appdir)
        # (without FUSE, as in a container, the tool runs extracted)
        env = dict(os.environ, ARCH=ARCH, APPIMAGE_EXTRACT_AND_RUN="1")
        tmp_out = path.with_name(path.name + ".tmp")
        subprocess.run([str(appimagetool.resolve()), "--no-appstream", "--comp", "zstd", str(appdir),
                        str(tmp_out)], check=True, env=env, stdout=subprocess.DEVNULL)
    os.replace(tmp_out, path)
    smoke_test(path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools/bundle-appimage.py",
                                     description=f"Make an AppImage of py-redact: {name()}, with a Python of "
                                                 "its own.")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="the folder to write it in (default: dist/)")
    parser.add_argument("--python", type=Path, metavar="APPIMAGE",
                        help="the Python AppImage to use (default: one of python-appimage, downloaded)")
    parser.add_argument("--python-version", default=PYTHON, metavar="VERSION",
                        help=f"the version of Python to download (default: {PYTHON})")
    parser.add_argument("--appimagetool", type=Path, metavar="APPIMAGE",
                        help="the appimagetool to use (default: downloaded)")
    args = parser.parse_args(argv)
    if not sys.platform.startswith("linux"):
        sys.exit("bundle-appimage.py: AppImages are made on Linux")
    output = args.output or DIST
    output.mkdir(parents=True, exist_ok=True)
    try:
        path = bundle(output, args.python, args.appimagetool, args.python_version)
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, StopIteration) as e:
        sys.exit(f"bundle-appimage.py: {e}")
    print(f"Wrote {path} ({path.stat().st_size / 1e6:.1f} MB).")


if __name__ == "__main__":
    main()
