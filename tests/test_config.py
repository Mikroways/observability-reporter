"""Tests de hreidar.config: variables de entorno y YAML de consultas."""

import pytest

from hreidar.config import (
    QuerySpec,
    cfg,
    load_config,
    parse_queries,
    resolve_report,
    split_list,
)


def test_cfg_usa_el_valor_por_defecto():
    assert cfg("METRICS_URL") == "http://localhost:9090/api/v1/query"


def test_cfg_usa_la_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("METRICS_URL", "http://mimir/api/v1/query")
    assert cfg("METRICS_URL") == "http://mimir/api/v1/query"


def test_cfg_respeta_una_variable_vacia(monkeypatch):
    monkeypatch.setenv("REPORT_TITLE", "")
    assert cfg("REPORT_TITLE") == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a@x.com", ["a@x.com"]),
        ("a@x.com, b@x.com", ["a@x.com", "b@x.com"]),
        ("a@x.com b@x.com,,c@x.com ", ["a@x.com", "b@x.com", "c@x.com"]),
        ("", []),
        (" , ", []),
    ],
)
def test_split_list(raw, expected):
    assert split_list(raw) == expected


def test_load_config_lee_el_yaml(tmp_path):
    path = tmp_path / "q.yaml"
    path.write_text("title: T\nqueries:\n  - query: up\n", encoding="utf-8")
    assert load_config(str(path)) == {
        "title": "T",
        "queries": [{"query": "up"}],
    }


def test_load_config_archivo_vacio_devuelve_mapa_vacio(tmp_path):
    path = tmp_path / "q.yaml"
    path.write_text("", encoding="utf-8")
    assert load_config(str(path)) == {}


def test_load_config_archivo_inexistente(tmp_path):
    with pytest.raises(SystemExit, match="No se pudo leer"):
        load_config(str(tmp_path / "no-existe.yaml"))


def test_load_config_yaml_invalido(tmp_path):
    path = tmp_path / "q.yaml"
    path.write_text("queries: [", encoding="utf-8")
    with pytest.raises(SystemExit, match="YAML inválido"):
        load_config(str(path))


def test_load_config_no_es_un_mapa(tmp_path):
    path = tmp_path / "q.yaml"
    path.write_text("- query: up\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="se esperaba un mapa"):
        load_config(str(path))


def test_parse_queries_valores_por_defecto(monkeypatch):
    monkeypatch.setenv("METRICS_ORG_ID", "tenant-env")
    specs = parse_queries([{"query": "  up  "}, {"query": "sum(up)"}], "src")
    assert specs == [
        QuerySpec(title="Consulta 1", query="up", org_id="tenant-env"),
        QuerySpec(title="Consulta 2", query="sum(up)", org_id="tenant-env"),
    ]


def test_parse_queries_valores_explicitos(monkeypatch):
    monkeypatch.setenv("METRICS_ORG_ID", "tenant-env")
    raw = [
        {"title": "Caídos", "query": "up == 0", "org_id": "otro"},
        {"query": "up", "org_id": ""},
        {"query": "up", "org_id": None},
    ]
    specs = parse_queries(raw, "src")
    assert specs[0] == QuerySpec("Caídos", "up == 0", "otro")
    # Un org_id vacío o nulo explícito no manda tenant.
    assert specs[1].org_id == ""
    assert specs[2].org_id == ""


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (None, "debe ser una lista no vacía"),
        ([], "debe ser una lista no vacía"),
        ({"query": "up"}, "debe ser una lista no vacía"),
        (["up"], "la consulta #1 debe ser un mapa"),
        (
            [{"query": "up"}, {"title": "sin query"}],
            "la consulta #2 no define",
        ),
        ([{"query": "   "}], "la consulta #1 no define"),
    ],
)
def test_parse_queries_invalidas(raw, message):
    with pytest.raises(SystemExit, match=message) as exc:
        parse_queries(raw, "archivo.yaml")
    assert str(exc.value.code).startswith("archivo.yaml:")


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "q.yaml"
    path.write_text(
        "title: Del YAML\nqueries:\n  - title: A\n    query: up\n",
        encoding="utf-8",
    )
    return path


def test_resolve_report_lee_el_archivo(config_file):
    title, specs = resolve_report(None, str(config_file), None)
    assert title == "Del YAML"
    assert [spec.title for spec in specs] == ["A"]


def test_resolve_report_usa_report_config(monkeypatch, config_file):
    monkeypatch.setenv("REPORT_CONFIG", str(config_file))
    assert resolve_report(None, None, None)[0] == "Del YAML"


def test_resolve_report_queries_ignora_el_archivo(tmp_path):
    # El archivo no existe: si se leyera, terminaría con error.
    title, specs = resolve_report(["up", "sum(up)"], str(tmp_path / "x"), None)
    assert title == "Reporte de métricas"
    assert [spec.query for spec in specs] == ["up", "sum(up)"]


def test_resolve_report_prioridad_del_titulo(monkeypatch, config_file):
    monkeypatch.setenv("REPORT_TITLE", "De la variable")
    assert resolve_report(None, str(config_file), "Del argumento")[0] == (
        "Del argumento"
    )
    assert resolve_report(None, str(config_file), None)[0] == "Del YAML"
    assert resolve_report(["up"], None, None)[0] == "De la variable"
