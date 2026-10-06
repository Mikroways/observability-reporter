"""Ejecución de una consulta del reporte, con los errores capturados."""

from dataclasses import dataclass

import requests

from hreidar.config import QuerySpec
from hreidar.prometheus import fetch
from hreidar.table import Row, build_table


@dataclass(frozen=True)
class QueryResult:
    """Resultado de ejecutar una consulta: filas o mensaje de error."""

    spec: QuerySpec
    columns: list[str]
    rows: list[Row]
    error: str | None = None


def run_query(url: str, spec: QuerySpec) -> QueryResult:
    """Ejecuta una consulta; los errores quedan en el resultado, no abortan."""
    try:
        columns, rows = build_table(fetch(url, spec.org_id, spec.query))
    except requests.HTTPError as exc:
        error = f"Error HTTP consultando métricas: {exc}"
    except requests.RequestException as exc:
        error = f"Error de conexión consultando métricas: {exc}"
    except (KeyError, IndexError, TypeError, ValueError, RuntimeError) as exc:
        error = f"Respuesta inesperada de la API: {exc}"
    else:
        return QueryResult(spec, columns, rows)
    return QueryResult(spec, [], [], error)
