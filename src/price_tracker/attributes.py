"""Attribute normalization and matching for product variants."""

import re
import unicodedata

# Each alias maps to a single canonical token. Colours fold to the form the
# marketplaces actually print (adjective, e.g. "prateado"), so prefix matching
# reaches the compound names (azul→azul-profundo, laranja→laranja-cósmico).
_SYNONYMS = {
    "black": "preto",
    "negro": "preto",
    "white": "branco",
    "silver": "prateado",
    "prata": "prateado",
    "gray": "cinza",
    "grey": "cinza",
    "gold": "dourado",
    "blue": "azul",
    "red": "vermelho",
    "green": "verde",
    "orange": "laranja",
}

_UNIT_RE = re.compile(r"(\d+)\s*(gigabytes?|terabytes?|gb|tb|mb)\b")
_UNIT_CANON = {"gigabyte": "gb", "gigabytes": "gb", "terabyte": "tb", "terabytes": "tb"}


def normalize(text: str | None) -> str:
    if not text:
        return ""
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _canon_units(text: str) -> str:
    return _UNIT_RE.sub(lambda m: m.group(1) + _UNIT_CANON.get(m.group(2), m.group(2)), text)


def canonical(value: str | None) -> str:
    """Normalize, fold storage units (256 GB -> 256gb), and apply synonyms."""
    v = _canon_units(normalize(value))
    return _SYNONYMS.get(v, v)


def parse_attr_args(args: list[str] | None) -> list[str]:
    """Parse repeated --attr values; accepts 'key=value' (value kept) or bare 'value'."""
    targets = []
    for raw in args or []:
        value = raw.split("=", 1)[1] if "=" in raw else raw
        value = value.strip()
        if value:
            targets.append(value)
    return targets


def option_matches(label: str | None, target: str) -> bool:
    """True if a variant/option/spec label satisfies the target attribute value."""
    label_c, target_c = canonical(label), canonical(target)
    if not target_c:
        return False
    if label_c == target_c:
        return True
    # Left word boundary only: target as a token prefix. Matches adjective colour
    # forms (prata→prateado, azul→azul-profundo) while keeping 8gb out of 128gb.
    return re.search(rf"\b{re.escape(target_c)}", label_c) is not None
