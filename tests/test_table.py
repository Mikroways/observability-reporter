"""Tests de hreidar.table: formato de valores y armado de la tabla."""

import pytest

from hreidar.table import build_table, format_value


def sample(value, **labels):
    return {"metric": labels, "value": [0, value]}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("42", "42"),
        ("42.0", "42"),
        ("-3", "-3"),
        ("0.12345", "0.123"),
        ("0.1", "0.100"),
        ("1e3", "1000"),
        ("NaN", "NaN"),
        ("+Inf", "inf"),
        ("-Inf", "-inf"),
        ("abc", "abc"),
        (None, "None"),
    ],
)
def test_format_value(raw, expected):
    assert format_value(raw) == expected


def test_build_table_vacio():
    assert build_table([]) == ([], [])


def test_build_table_columnas_con_name_primero():
    columns, _ = build_table(
        [
            sample("1", __name__="up", job="a", instance="h1"),
            sample("2", zone="z1"),
        ]
    )
    assert columns == ["__name__", "instance", "job", "zone"]


def test_build_table_ordena_de_mayor_a_menor():
    _, rows = build_table(
        [
            sample("1", job="uno"),
            sample("10", job="diez"),
            sample("abc", job="texto"),
            sample("-5", job="negativo"),
        ]
    )
    # Los valores no numéricos se ordenan como si fueran 0.
    assert [labels["job"] for labels, _ in rows] == [
        "diez",
        "uno",
        "texto",
        "negativo",
    ]
    assert [value for _, value in rows] == ["10", "1", "abc", "-5"]


def test_build_table_muestra_sin_etiquetas():
    columns, rows = build_table([{"value": [0, "3"]}])
    assert columns == []
    assert rows == [({}, "3")]
