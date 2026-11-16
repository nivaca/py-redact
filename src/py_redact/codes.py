"""Redaction codes, as Acrobat has them: short texts written over a redacted
box to say why it was redacted ("(b)(6)"), grouped in code sets. A box may
carry several codes, written separated by commas.

Two sets come with the program, the U.S. FOIA exemptions and the U.S. Privacy
Act exemptions. The user's own sets are kept in codes.xml, in the
configuration folder (see config.py), in this form, which is also the one of
the files exported and imported:

    <codes>
      <set name="Mine">
        <code>Personal data</code>
        ...
      </set>
    </codes>
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from . import config

BUILT_IN = {
    "U.S. FOIA": ["(b)(1)", "(b)(2)", "(b)(3)", "(b)(4)", "(b)(5)", "(b)(6)", "(b)(7)(A)", "(b)(7)(B)",
                  "(b)(7)(C)", "(b)(7)(D)", "(b)(7)(E)", "(b)(7)(F)", "(b)(8)", "(b)(9)"],
    "U.S. Privacy Act": ["(d)(5)", "(j)(1)", "(j)(2)", "(k)(1)", "(k)(2)", "(k)(3)", "(k)(4)", "(k)(5)",
                         "(k)(6)", "(k)(7)"],
}
SEPARATOR = ", "


class CodesError(Exception):
    """A file of codes that cannot be read or written."""


def path() -> Path:
    return config.config_dir() / "codes.xml"


def parse(text_or_path) -> dict[str, list[str]]:
    """The sets of a codes file (raises CodesError)."""
    try:
        root = ET.parse(text_or_path).getroot() if isinstance(text_or_path, Path) \
            else ET.fromstring(text_or_path)
    except (OSError, ET.ParseError) as e:
        raise CodesError(str(e)) from None
    if root.tag != "codes":
        raise CodesError("the root element must be <codes>")
    sets: dict[str, list[str]] = {}
    for item in root.findall("set"):
        name = " ".join((item.get("name") or "").split())
        if not name:
            continue
        codes = sets.setdefault(name, [])
        for code in item.findall("code"):
            text = " ".join((code.text or "").split())
            if text and text not in codes:
                codes.append(text)
    return sets


def dump(sets: dict[str, list[str]]) -> str:
    root = ET.Element("codes")
    for name, codes in sets.items():
        item = ET.SubElement(root, "set", name=name)
        for code in codes:
            ET.SubElement(item, "code").text = code
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def user_sets() -> dict[str, list[str]]:
    """The user's own sets ({} if there are none, or if the file can't be read)."""
    try:
        return parse(path()) if path().is_file() else {}
    except CodesError:
        return {}


def all_sets() -> dict[str, list[str]]:
    """The sets that come with the program, then the user's (which may replace them by name)."""
    return {**BUILT_IN, **user_sets()}


def save_user_sets(sets: dict[str, list[str]]) -> None:
    """Keep SETS as the user's (raises OSError)."""
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(dump(sets), encoding="utf-8")
    os.replace(tmp, target)


def codes_of(text: str) -> list[str]:
    """The codes in the text of a box ("(b)(6), (b)(7)(C)")."""
    return [c.strip() for c in text.split(",") if c.strip()]


def toggle(text: str, code: str) -> str:
    """TEXT with CODE added (or taken out, if it has it already)."""
    have = codes_of(text)
    if code in have:
        have.remove(code)
    else:
        have.append(code)
    return SEPARATOR.join(have)
