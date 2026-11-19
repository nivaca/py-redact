#!/usr/bin/env python3
"""Draws the PNG icons of py-redact, in every size of the hicolor theme, from
its two SVG pictures: the scalable one (hicolor/scalable/apps/py-redact.svg)
for 48 pixels and more, and a plainer one (icons/source/py-redact-small.svg),
with fewer and bolder lines, for 32 pixels and less.

    python3 tools/icons.py [--inkscape INKSCAPE]

It needs Inkscape (by default, `inkscape` on the PATH, or the AppImage in
~/AppImages/inkscape.appimage).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "src" / "py_redact" / "icons"
HICOLOR = ICONS / "linux" / "hicolor"
LARGE = HICOLOR / "scalable" / "apps" / "py-redact.svg"
SMALL = ICONS / "source" / "py-redact-small.svg"
SIZES = (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512)


def inkscape(given: str | None) -> str:
    for candidate in (given, shutil.which("inkscape"), str(Path.home() / "AppImages" / "inkscape.appimage")):
        if candidate and (Path(candidate).exists() or shutil.which(candidate)):
            return candidate
    raise SystemExit("icons.py: Inkscape is needed (--inkscape gives where it is)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inkscape", help="the Inkscape to use")
    program = inkscape(parser.parse_args().inkscape)
    for size in SIZES:
        target = HICOLOR / f"{size}x{size}" / "apps" / "py-redact.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        source = SMALL if size <= 32 else LARGE
        subprocess.run([program, str(source), "--export-type=png", f"--export-filename={target}",
                        f"--export-width={size}", f"--export-height={size}"],
                       check=True, capture_output=True)
        print(f"{target.relative_to(ROOT)}  (from {source.name})")


if __name__ == "__main__":
    main()
