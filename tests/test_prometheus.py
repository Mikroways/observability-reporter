"""Tests de hreidar.prometheus: llamada a la API de consultas."""

import pytest
import requests

from hreidar import prometheus
from hreidar.prometheus import QUERY_LIMIT, QUERY_TIMEOUT, fetch

URL = "http://mimir/prometheus/api/v1/query"


class FakeResponse:
    """Respuesta mínima de requests para los tests."""

    def __init__(self, payload=None, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status} Server Error")

    def json(self):
        return self.payload


@pytest.fixture
def fake_get(monkeypatch):
    """Reemplaza requests.get; devuelve la lista de llamadas registradas."""
    calls = []
    response = {"value": FakeResponse()}

    def get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return response["value"]

    monkeypatch.setattr(prometheus.requests, "get", get)

    def respond(payload=None, status=200):
        response["value"] = FakeResponse(payload, status)
        return calls

    return respond


def vector(*samples):
    return {
        "status": "success",
        "data": {"resultType": "vector", "result": list(samples)},
    }


def test_fetch_devuelve_el_vector(fake_get):
    sample = {"metric": {"job": "a"}, "value": [0, "1"]}
    calls = fake_get(vector(sample))
    assert fetch(URL, "", "up") == [sample]
    assert calls == [
        {
            "url": URL,
            "params": {"query": "up", "limit": QUERY_LIMIT},
            "headers": {},
            "timeout": QUERY_TIMEOUT,
        }
    ]


def test_fetch_manda_el_tenant(fake_get):
    calls = fake_get(vector())
    fetch(URL, "mi-tenant", "up", timeout=5)
    assert calls[0]["headers"] == {"X-Scope-OrgID": "mi-tenant"}
    assert calls[0]["timeout"] == 5


def test_fetch_error_http(fake_get):
    fake_get(status=500)
    with pytest.raises(requests.HTTPError, match="500"):
        fetch(URL, "", "up")


def test_fetch_status_no_exitoso(fake_get):
    fake_get({"status": "error", "error": "parse error"})
    with pytest.raises(RuntimeError, match="no exitosa"):
        fetch(URL, "", "up(")


def test_fetch_rechaza_resultados_que_no_son_vector(fake_get):
    fake_get({"status": "success", "data": {"resultType": "matrix"}})
    with pytest.raises(RuntimeError, match="'matrix'"):
        fetch(URL, "", "up[5m]")
