"""Configuración: variables de entorno y archivo YAML de consultas."""

import os
import sys
from dataclasses import dataclass
from typing import Any

import yaml

#: Valores por defecto de las variables de entorno de configuración.
DEFAULTS = {
    "METRICS_URL": "http://localhost:9090/api/v1/query",
    "METRICS_ORG_ID": "",
    "REPORT_CONFIG": "queries.yaml",
    "REPORT_TITLE": "Reporte de métricas",
}


@dataclass(frozen=True)
class QuerySpec:
    """Una consulta del reporte."""

    title: str
    query: str
    org_id: str


def cfg(key: str) -> str:
    """Devuelve la variable de entorno `key` o su valor por defecto."""
    return os.environ.get(key, DEFAULTS[key])


def split_list(raw: str) -> list[str]:
    """Convierte 'a, b c' en la lista ['a', 'b', 'c'] (comas y/o espacios)."""
    return [item for item in raw.replace(",", " ").split() if item]


def load_config(path: str) -> dict[str, Any]:
    """Lee el archivo YAML de consultas y valida su estructura básica."""
    try:
        with open(path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
    except OSError as exc:
        sys.exit(f"No se pudo leer el archivo de consultas: {exc}")
    except yaml.YAMLError as exc:
        sys.exit(f"YAML inválido en {path}: {exc}")
    if not isinstance(config, dict):
        sys.exit(f"{path}: se esperaba un mapa con la clave 'queries'.")
    return config


def parse_queries(raw: Any, source: str) -> list[QuerySpec]:
    """Convierte la lista 'queries' del YAML en una lista de QuerySpec."""
    if not isinstance(raw, list) or not raw:
        sys.exit(f"{source}: 'queries' debe ser una lista no vacía.")
    default_org = cfg("METRICS_ORG_ID")
    specs = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            sys.exit(f"{source}: la consulta #{index} debe ser un mapa.")
        query = str(item.get("query") or "").strip()
        if not query:
            sys.exit(f"{source}: la consulta #{index} no define 'query'.")
        specs.append(
            QuerySpec(
                title=str(item.get("title") or f"Consulta {index}"),
                query=query,
                org_id=str(item.get("org_id", default_org) or ""),
            )
        )
    return specs


def resolve_report(
    queries: list[str] | None,
    config_path: str | None,
    title: str | None,
) -> tuple[str, list[QuerySpec]]:
    """Devuelve (título, consultas) según los argumentos y el archivo YAML.

    Con `queries` (--query) se usan solo esas consultas; si no, las del
    archivo YAML (`config_path`, o REPORT_CONFIG).
    Título: `title` (--title) > 'title' del YAML > REPORT_TITLE.
    """
    if queries:
        raw = [{"query": query} for query in queries]
        specs = parse_queries(raw, "--query")
        file_title = None
    else:
        path = config_path or cfg("REPORT_CONFIG")
        config = load_config(path)
        specs = parse_queries(config.get("queries"), path)
        file_title = config.get("title")
    return str(title or file_title or cfg("REPORT_TITLE")), specs
