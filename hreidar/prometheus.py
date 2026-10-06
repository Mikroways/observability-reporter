"""Cliente de la API de consultas de Prometheus / Mimir."""

from typing import Any

import requests

QUERY_LIMIT = "5000"
QUERY_TIMEOUT = 30


# Muestra del vector de Prometheus: {"metric": {...}, "value": [ts, "valor"]}.
Sample = dict[str, Any]


def fetch(
    url: str,
    org_id: str,
    query: str,
    timeout: int = QUERY_TIMEOUT,
) -> list[Sample]:
    """Ejecuta la consulta instantánea y devuelve el vector de resultados.

    Levanta RuntimeError si la API responde con error o si el resultado no es
    un vector (por ejemplo, una range query que devuelve 'matrix').
    """
    headers = {}
    if org_id:
        headers["X-Scope-OrgID"] = org_id
    resp = requests.get(
        url,
        params={"query": query, "limit": QUERY_LIMIT},
        headers=headers,
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"Consulta no exitosa: {payload}")
    data = payload["data"]
    if data.get("resultType") != "vector":
        raise RuntimeError(
            f"Se esperaba una consulta instantánea (vector), pero llegó "
            f"'{data.get('resultType')}'. Usá una query que devuelva un "
            f"vector."
        )
    return data["result"]
