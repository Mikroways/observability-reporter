"""Generación del HTML del reporte con Jinja2."""

import sys
from datetime import UTC, datetime
from pathlib import Path

import jinja2

from hreidar.query import QueryResult

#: Template HTML por defecto: templates/report.html.j2 en la raíz del repo.
DEFAULT_TEMPLATE = (
    Path(__file__).resolve().parent.parent / "templates" / "report.html.j2"
)


def render_html(
    template_path: Path,
    title: str,
    results: list[QueryResult],
    url: str,
) -> str:
    """Arma el documento HTML del reporte con el template Jinja2."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path.parent),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    try:
        template = env.get_template(template_path.name)
    except jinja2.TemplateError as exc:
        sys.exit(f"No se pudo cargar el template {template_path}: {exc}")

    context = {
        "title": title,
        "generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "url": url,
        "results": [
            {
                "title": result.spec.title,
                "query": result.spec.query,
                "description": result.spec.description,
                "unit": result.spec.unit,
                "org_id": result.spec.org_id,
                "columns": result.columns,
                "rows": [
                    {"labels": labels, "value": value}
                    for labels, value in result.rows
                ],
                "error": result.error or "",
            }
            for result in results
        ],
        "total_rows": sum(len(result.rows) for result in results),
        "failed": sum(1 for result in results if result.error),
    }
    try:
        return template.render(context)
    except jinja2.TemplateError as exc:
        sys.exit(f"Error renderizando el template {template_path}: {exc}")
