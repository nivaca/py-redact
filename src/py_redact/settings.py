"""The user's settings for redacting, kept in the configuration file
(config.toml, [parameters]; see config.py) next to the language.

Each setting is checked when it is read: a value that is missing, of the
wrong type or not one of those allowed gives the usual one, so a file edited
by hand can never stop the program.
"""

from __future__ import annotations

import dataclasses
import re

from . import config

COLOR = re.compile(r"#[0-9a-f]{6}")
IMAGES = ("pixels", "whole", "none")  # what happens to images under a box
DRAWINGS = ("covered", "touched", "none")  # and to drawings (lines, shapes)


@dataclasses.dataclass(frozen=True)
class Settings:
    color: str = "#000000"  # of new boxes ('' for none)
    text: str = ""  # written over new boxes
    text_color: str = "#ffffff"
    font_size: float = 0  # 0: as large as fits
    align: str = "center"
    repeat_text: bool = False
    clean: bool = False  # also remove metadata, hidden text, attachments, scripts
    images: str = "pixels"
    drawings: str = "covered"
    pattern_language: str = "en"  # the forms of the patterns of Find and redact (see patterns.py)
    mark_outline: str = "#d03030"  # of boxes not yet applied
    mark_opacity: int = 60  # their fill, in % (100: as they will be once applied)
    pdfconform: str = ""  # the path of pdf2iso; '' to look for it (see conform.find)


DEFAULTS = Settings()
KEYS = {"color": "redact_color", "clean": "redact_clean", "images": "redact_images",
        "drawings": "redact_drawings", "text": "box_text",
        "text_color": "box_text_color", "font_size": "box_font_size", "align": "box_align",
        "repeat_text": "box_repeat_text", "pattern_language": "pattern_language",
        "mark_outline": "mark_outline", "mark_opacity": "mark_opacity", "pdfconform": "pdfconform"}
APPEARANCE = ("color", "text", "text_color", "font_size", "align", "repeat_text")  # (of new boxes)


def valid(name: str, value) -> bool:
    if name == "color":
        return isinstance(value, str) and (value == "" or bool(COLOR.fullmatch(value.lower())))
    if name == "pdfconform":
        return isinstance(value, str) and "\n" not in value
    if name == "pattern_language":
        return value in ("en", "es")
    if name == "mark_opacity":
        return isinstance(value, int) and not isinstance(value, bool) and 10 <= value <= 100
    if name in ("text_color", "mark_outline"):
        return isinstance(value, str) and bool(COLOR.fullmatch(value.lower()))
    if name == "text":
        return isinstance(value, str) and "\n" not in value and len(value) <= 200
    if name == "font_size":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 72
    if name == "align":
        return value in ("left", "center", "right")
    if name in ("clean", "repeat_text"):
        return isinstance(value, bool)
    if name == "images":
        return value in IMAGES
    if name == "drawings":
        return value in DRAWINGS
    return False


def load() -> Settings:
    try:
        params = config.read().get("parameters", {})
    except config.ConfigError:
        params = {}
    if not isinstance(params, dict):
        params = {}
    values = {}
    for name, key in KEYS.items():
        value = params.get(key)
        if valid(name, value):
            values[name] = value.lower() if name in ("color", "text_color", "mark_outline") else value
    return dataclasses.replace(DEFAULTS, **values)


def save(settings: Settings) -> None:
    """Keep SETTINGS in the configuration file (raises OSError)."""
    for name, key in KEYS.items():
        value = getattr(settings, name)
        if not valid(name, value):
            raise ValueError(f"{name} = {value!r}")
        config.set(key, value)
