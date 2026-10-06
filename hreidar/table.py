"""Conversión del vector de Prometheus en columnas y filas del reporte."""

import math
from typing import Any

from hreidar.prometheus import Sample

VALUE_DECIMALS = 3

Labels = dict[str, str]
Row = tuple[Labels, str]


def format_value(raw: Any) -> str:
    """Formatea el valor: entero si corresponde, si no 3 decimales.

    Si no es un número, lo devuelve tal cual como texto.
    """
    try:
        num = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    if math.isnan(num):
        return "NaN"
    if num.is_integer():
        return str(int(num))
    return f"{num:.{VALUE_DECIMALS}f}"


def build_table(result: list[Sample]) -> tuple[list[str], list[Row]]:
    """Arma (columnas, filas) a partir del vector de Prometheus.

    columnas: nombres de etiquetas presentes (con __name__ primero si existe).
    filas: lista de (dict_de_etiquetas, valor_str), ordenada por valor desc.
    """
    label_keys = set()
    for item in result:
        label_keys.update(item.get("metric", {}).keys())

    columns = []
    if "__name__" in label_keys:
        columns.append("__name__")
        label_keys.discard("__name__")
    columns.extend(sorted(label_keys))

    def sort_key(item: Sample) -> float:
        try:
            return -float(item["value"][1])
        except (TypeError, ValueError):
            return 0.0

    rows = [
        (item.get("metric", {}), format_value(item["value"][1]))
        for item in sorted(result, key=sort_key)
    ]
    return columns, rows
