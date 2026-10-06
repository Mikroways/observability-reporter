"""Tests de hreidar.render: HTML del reporte con Jinja2."""

import pytest

from hreidar.config import QuerySpec
from hreidar.query import QueryResult
from hreidar.render import DEFAULT_TEMPLATE, render_html

URL = "http://mimir/api/v1/query"


def result(title="Q", rows=None, error=None, columns=None):
    rows = rows or []
    if columns is None:
        columns = sorted({key for labels, _ in rows for key in labels})
    return QueryResult(
        spec=QuerySpec(title=title, query="up", org_id=""),
        columns=columns,
        rows=rows,
        error=error,
    )


def test_default_template_existe():
    assert DEFAULT_TEMPLATE.is_file()


def test_render_html_con_datos():
    html = render_html(
        DEFAULT_TEMPLATE,
        "Reporte",
        [result(rows=[({"job": "api", "instance": "h1"}, "0.500")])],
        URL,
    )
    assert "<title>Reporte</title>" in html
    assert "1 resultado(s)." in html
    assert ">instance</th>" in html
    assert "<td>api</td>" in html
    assert "0.500" in html
    assert URL in html


def test_render_html_escapa_el_html():
    html = render_html(
        DEFAULT_TEMPLATE,
        "<script>x</script>",
        [result(rows=[({"job": "a<b>&"}, "1")])],
        URL,
    )
    assert "<script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "a&lt;b&gt;&amp;" in html


def test_render_html_error_y_vacio():
    html = render_html(
        DEFAULT_TEMPLATE,
        "R",
        [result("Rota", error="Error HTTP: 500"), result("Vacía")],
        URL,
    )
    assert "Error ejecutando la consulta: Error HTTP: 500" in html
    assert "La consulta no devolvió resultados." in html


def test_render_html_contexto_del_template(tmp_path):
    template = tmp_path / "t.j2"
    template.write_text(
        "{{ title }}|{{ total_rows }}|{{ failed }}|{{ url }}|"
        "{% for r in results %}{{ r.title }}:{{ r.error }};{% endfor %}",
        encoding="utf-8",
    )
    html = render_html(
        template,
        "T",
        [
            result("A", rows=[({}, "1"), ({}, "2")]),
            result("B", error="falló"),
        ],
        URL,
    )
    assert html == f"T|2|1|{URL}|A:;B:falló;"


def test_render_html_template_inexistente(tmp_path):
    with pytest.raises(SystemExit, match="No se pudo cargar el template"):
        render_html(tmp_path / "no-existe.j2", "T", [], URL)


def test_render_html_variable_inexistente(tmp_path):
    template = tmp_path / "t.j2"
    template.write_text("{{ no_existe }}", encoding="utf-8")
    with pytest.raises(SystemExit, match="Error renderizando el template"):
        render_html(template, "T", [], URL)
