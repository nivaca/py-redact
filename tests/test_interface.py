"""The Spanish interface: every text of the program is translated, and nothing else is."""

from __future__ import annotations

import ast
from pathlib import Path

from py_redact import config, interface
from py_redact.interface import ntr, tr

SRC = Path(__file__).resolve().parent.parent / "src" / "py_redact"


def program_texts() -> set[str]:
    texts = []
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("tr", "ntr", "N_"):
                args = node.args[:2] if node.func.id == "ntr" else node.args[:1]
                texts += [a.value for a in args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    return {interface.key_of(t) for t in texts if t.strip()}


def test_spanish_is_complete():
    spanish = interface.read(interface.files()["es"])
    program = program_texts()
    assert sorted(program - spanish.keys()) == [], "texts without a translation"
    assert sorted(spanish.keys() - program) == [], "translations no longer used"


def test_tr():
    assert interface.use("es")
    assert tr("Page ") == "Página "
    assert ntr("{count} box selected", "{count} boxes selected", 3) == "3 recuadros seleccionados"
    assert not interface.use("xx") and interface.code() == "en"


def test_configured_language():
    config.set("interface", "es")
    assert interface.use_configured() == "es"
    config.set("interface", "es")  # (the file is written in the language in use)
    assert config.config_path().read_text(encoding="utf-8").startswith("# La configuración")
