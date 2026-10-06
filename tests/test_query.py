"""Tests de hreidar.query: ejecución de una consulta y captura de errores."""

import pytest
import requests

from hreidar import query
from hreidar.config import QuerySpec
from hreidar.query import run_query

URL = "http://mimir/api/v1/query"
SPEC = QuerySpec(title="T", query="up", org_id="tenant")


def test_run_query_ok(monkeypatch):
    calls = []

    def fetch(url, org_id, promql):
        calls.append((url, org_id, promql))
        return [{"metric": {"job": "a"}, "value": [0, "1"]}]

    monkeypatch.setattr(query, "fetch", fetch)
    result = run_query(URL, SPEC)
    assert calls == [(URL, "tenant", "up")]
    assert result.spec == SPEC
    assert result.columns == ["job"]
    assert result.rows == [({"job": "a"}, "1")]
    assert result.error is None


@pytest.mark.parametrize(
    ("exc", "message"),
    [
        (requests.HTTPError("500 Server Error"), "Error HTTP"),
        (requests.ConnectionError("refused"), "Error de conexión"),
        (requests.Timeout("timeout"), "Error de conexión"),
        (RuntimeError("no es vector"), "Respuesta inesperada"),
        (ValueError("JSON inválido"), "Respuesta inesperada"),
        (KeyError("data"), "Respuesta inesperada"),
    ],
)
def test_run_query_captura_errores(monkeypatch, exc, message):
    def fetch(*_args):
        raise exc

    monkeypatch.setattr(query, "fetch", fetch)
    result = run_query(URL, SPEC)
    assert result.error.startswith(message)
    assert result.columns == []
    assert result.rows == []


def test_run_query_muestra_mal_formada(monkeypatch):
    # Falta "value": el error sale de build_table y también se captura.
    monkeypatch.setattr(query, "fetch", lambda *_: [{"metric": {}}])
    assert run_query(URL, SPEC).error.startswith("Respuesta inesperada")
