"""PDF/A and PDF/X output, made by the author's py-pdfconform (Ghostscript and
pikepdf), which must be installed and on the PATH: the redacted copy is
written first, then converted.

PDF/A and PDF/X don't allow encryption, so a protected document comes out
unprotected (py-pdfconform is given its password).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .interface import N_, tr

COMMAND = "py-pdfconform"
# (value of py-pdfconform --target, name shown)
STANDARDS = [("a-1b", N_("PDF/A-1b (archiving, the oldest)")), ("a-2b", N_("PDF/A-2b (archiving)")),
             ("a-3b", N_("PDF/A-3b (archiving, with attachments)")), ("x-4", N_("PDF/X-4 (printing)"))]
TIMEOUT = 600  # seconds


class ConformError(Exception):
    """A conversion that failed."""


def own_folders() -> list[Path]:
    """The folders of this program's own Python (its virtual environment, or the
    AppImage), which py-pdfconform must not see: it would run with this Python,
    which hasn't its libraries."""
    out = []
    if sys.prefix != sys.base_prefix:
        out.append(Path(sys.prefix).resolve())
    for name in ("APPDIR", "VIRTUAL_ENV"):  # (also a virtual environment this program was started from)
        if os.environ.get(name):
            out.append(Path(os.environ[name]).resolve())
    return out


def clean_env() -> dict[str, str]:
    """The environment for py-pdfconform: the user's, without this program's Python."""
    own = own_folders()

    def ours(folder: str) -> bool:
        try:
            p = Path(folder).resolve()
        except OSError:
            return False
        return any(p == o or o in p.parents for o in own)

    env = {k: v for k, v in os.environ.items()
           if k not in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH", "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE",
                        "SSL_CERT_FILE", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH")}
    env["PATH"] = os.pathsep.join(f for f in os.environ.get("PATH", "").split(os.pathsep) if f and not ours(f))
    return env


def command() -> str | None:
    """The path of py-pdfconform, or None if it isn't on the PATH."""
    return shutil.which(COMMAND, path=clean_env()["PATH"])


def available() -> bool:
    return command() is not None


def label(standard: str) -> str:
    return "PDF/" + standard[0].upper() + standard[1:] if standard else "PDF"


def convert(source: Path, target: Path, standard: str, password: str = "") -> str:
    """SOURCE converted to STANDARD ('a-2b', 'x-4'...) as TARGET (safely: TARGET
    may be SOURCE). Returns what py-pdfconform says about it (its check)."""
    exe = command()
    if exe is None:
        raise ConformError(tr("{command} is not installed (or not on the PATH)", command=COMMAND))
    if standard not in [s for s, _ in STANDARDS]:
        raise ConformError(standard)
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=target.parent)
    os.close(fd)
    args = [exe, "-t", standard, "-o", tmp] + (["-p", password] if password else []) + [str(source)]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=TIMEOUT, env=clean_env())
        if r.returncode != 0 or not Path(tmp).stat().st_size:
            raise ConformError(tr("{command} could not make {standard}: {error}", command=COMMAND,
                                  standard=label(standard),
                                  error=(r.stderr or r.stdout).strip() or r.returncode))
        os.replace(tmp, target)
    except subprocess.TimeoutExpired:
        raise ConformError(tr("{command} took too long", command=COMMAND)) from None
    except OSError as e:
        raise ConformError(str(e)) from None
    finally:
        Path(tmp).unlink(missing_ok=True)
    # its last line: "OK  (veraPDF: PASS) in.pdf -> out.pdf [PDF/A-2b]"
    said = r.stdout.strip().splitlines()
    check = said[-1] if said else ""
    return check[check.index("(") + 1:check.index(")")] if "(" in check and ")" in check else ""
