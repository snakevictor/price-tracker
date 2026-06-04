import pytest

from price_tracker.attributes import (
    canonical,
    is_relevant,
    normalize,
    option_matches,
    parse_attr_args,
)


def test_normalize_strips_accents_and_case():
    assert normalize("  Memória  Interna ") == "memoria interna"
    assert normalize(None) == ""


@pytest.mark.parametrize(
    "value,expected",
    [
        ("256 GB", "256gb"),
        ("256gb", "256gb"),
        ("256 Gigabytes", "256gb"),
        ("1 TB", "1tb"),
        ("Preto", "preto"),
        ("Black", "preto"),
        ("Negro", "preto"),
        ("Branco", "branco"),
    ],
)
def test_canonical(value, expected):
    assert canonical(value) == expected


def test_parse_attr_args():
    assert parse_attr_args(["cor=preto", "256gb", "armazenamento = 256 GB "]) == [
        "preto",
        "256gb",
        "256 GB",
    ]
    assert parse_attr_args(None) == []


@pytest.mark.parametrize(
    "label,target,expected",
    [
        ("256 GB", "256gb", True),
        ("iPhone 17 Pro 256GB Preto", "256gb", True),
        ("iPhone 17 Pro 256GB Preto", "black", True),
        ("Preto", "black", True),
        ("128 GB", "256gb", False),
        ("128gb", "8gb", False),  # substring must not match across digit runs
        ("Azul", "preto", False),
        ("iPhone 17 Pro 256GB - Prateado", "prata", True),  # silver adjective form
        ("iPhone 17 Pro - Azul-profundo", "azul", True),
        ("iPhone 17 Pro - Laranja-cósmico", "laranja", True),
        ("iPhone 17 Pro - Prateado", "silver", True),  # synonym -> prata -> prateado
    ],
)
def test_option_matches(label, target, expected):
    assert option_matches(label, target) is expected


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Apple iPhone 17 Pro (256 GB) - Prateado", True),
        ("iPhone 17 Pro 256GB - Laranja-cósmico", True),
        ("Apple iPhone 17 Pro Max (256 GB) - Prateado", False),  # different model
        ("Apple iPhone 17 de 512 GB — Preto", False),  # missing "pro"
        ("Apple iPhone 16e de 128 GB — Preto", False),  # wrong generation
        ("Smartphone OPPO RENO 14 F 5G 256GB", False),  # different brand
        ("Capa para iPhone 17 Pro", True),  # same product (accessory handled by category)
    ],
)
def test_is_relevant(title, expected):
    assert is_relevant(title, "iphone 17 pro") is expected
