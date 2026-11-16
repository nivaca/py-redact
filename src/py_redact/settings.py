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
    color: str = "#000000"  # of new boxes
    clean: bool = False  # also remove metadata, hidden text, attachments, scripts
    images: str = "pixels"
    drawings: str = "covered"


DEFAULTS = Settings()
KEYS = {"color": "redact_color", "clean": "redact_clean", "images": "redact_images",
        "drawings": "redact_drawings"}


def valid(name: str, value) -> bool:
    if name == "color":
        return isinstance(value, str) and bool(COLOR.fullmatch(value.lower()))
    if name == "clean":
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
            values[name] = value.lower() if name == "color" else value
    return dataclasses.replace(DEFAULTS, **values)


def save(settings: Settings) -> None:
    """Keep SETTINGS in the configuration file (raises OSError)."""
    for name, key in KEYS.items():
        value = getattr(settings, name)
        if not valid(name, value):
            raise ValueError(f"{name} = {value!r}")
        config.set(key, value)
