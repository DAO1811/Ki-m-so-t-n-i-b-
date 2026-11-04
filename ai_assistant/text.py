"""Small, deterministic Vietnamese search helpers; no model or remote service."""

import re
import unicodedata


def plain(value):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
        if not unicodedata.combining(c)
    )


def contains(text, phrase):
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))


def any_phrase(text, phrases):
    return any(contains(text, phrase) for phrase in phrases)
