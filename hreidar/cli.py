"""Reporte genérico de métricas (Grafana Mimir / Prometheus).

Ejecuta N consultas PromQL instantáneas contra la API de Mimir/Prometheus y
genera un HTML básico, apto para enviar por correo, con una sección por
consulta. Las columnas de cada tabla se arman dinámicamente a partir de las
etiquetas devueltas por la consulta.

Las consultas se definen en un archivo YAML (ver queries.example.yaml):

  title: Reporte de métricas        # opcional
  queries:
    - title: Targets caídos         # opcional (default: "Consulta N")
      query: up == 0                # obligatorio
      org_id: mi-tenant             # opcional (default: METRICS_ORG_ID)

Si se pasa una o más veces --query, se ejecutan solo esas consultas y no se
lee el archivo.

Configuración vía variables de entorno (ver .envrc):
  METRICS_URL          Endpoint de consulta (.../prometheus/api/v1/query)
  METRICS_ORG_ID       Tenant de Mimir (X-Scope-OrgID); vacío = no se envía
  REPORT_CONFIG        Archivo YAML de consultas (default: queries.yaml)
  REPORT_TITLE         Título del reporte (opcional)
  REPORT_TEMPLATE      Template Jinja2 del HTML
                       (default: templates/report.html.j2)

Envío por correo (Amazon SES; solo si se usa --send). Si se definen
SES_SMTP_USER y SES_SMTP_PASSWORD se usa SMTP; si no, la API de SES con las
credenciales de AWS por defecto (IRSA, variables AWS_*, perfil, etc.):
  SES_SENDER           Remitente verificado en SES (obligatorio)
  SES_TO               Destinatarios separados por coma (obligatorio)
  SES_SUBJECT          Asunto del correo (opcional; hay uno por defecto)
  AWS_REGION           Región de SES (ej: us-east-1)
  SES_SMTP_USER        Usuario SMTP de SES (solo SMTP)
  SES_SMTP_PASSWORD    Contraseña SMTP de SES (solo SMTP)
  SES_SMTP_HOST        Host SMTP (default: email-smtp.<region>.amazonaws.com)
  SES_SMTP_PORT        Puerto SMTP (opcional; default: 587 con STARTTLS)

Uso:
  python3 report.py                                 # queries.yaml -> stdout
  python3 report.py -c otras.yaml -o out.html       # otro archivo de consultas
  python3 report.py -q 'up == 0' -q 'sum(up)'       # consultas ad hoc
  python3 report.py --title "Nodos caídos" --send   # envío por SES

Si alguna consulta falla, su sección muestra el error, el reporte se genera
(y envía) igual, y el proceso termina con código de salida 1.
"""

import argparse
import os
import sys
from pathlib import Path

from hreidar.config import cfg, resolve_report
from hreidar.mail import send_email_ses
from hreidar.query import run_query
from hreidar.render import DEFAULT_TEMPLATE, render_html


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Define y parsea los argumentos (por defecto, los de sys.argv)."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--config",
        help="Archivo YAML de consultas (precede a REPORT_CONFIG)",
    )
    parser.add_argument(
        "-q",
        "--query",
        action="append",
        help=(
            "Consulta PromQL a ejecutar; repetible. Si se usa, se ignora el "
            "archivo de consultas"
        ),
    )
    parser.add_argument(
        "-t",
        "--title",
        help="Título del reporte (precede al del YAML y a REPORT_TITLE)",
    )
    parser.add_argument(
        "--template",
        help="Template Jinja2 del HTML (precede a REPORT_TEMPLATE)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Archivo HTML de salida (por defecto: stdout)",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help=(
            "Enviar el reporte por correo vía Amazon SES, por SMTP o por "
            "la API (usa SES_SENDER/SES_TO/SES_SMTP_*/AWS_*)"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Genera el reporte y lo escribe a stdout, a un archivo y/o lo envía."""
    args = parse_args(argv)
    title, specs = resolve_report(args.query, args.config, args.title)
    url = cfg("METRICS_URL")

    results = [run_query(url, spec) for spec in specs]
    failed = [result for result in results if result.error]
    for result in failed:
        print(f"[{result.spec.title}] {result.error}", file=sys.stderr)
    total_rows = sum(len(result.rows) for result in results)
    template = Path(
        args.template or os.environ.get("REPORT_TEMPLATE") or DEFAULT_TEMPLATE
    )
    document = render_html(template, title, results, url)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(document)
        print(
            f"Reporte escrito en {args.output} ({len(results)} consulta/s, "
            f"{total_rows} fila/s).",
            file=sys.stderr,
        )
    elif not args.send:
        sys.stdout.write(document)

    if args.send:
        default_subject = f"{title} - {total_rows} resultado(s)"
        if failed:
            default_subject += f" ({len(failed)} consulta(s) con error)"
        subject = os.environ.get("SES_SUBJECT", default_subject)
        try:
            via = send_email_ses(document, subject)
        except Exception as exc:  # noqa: BLE001
            # smtplib, red o botocore (credenciales, permisos, API).
            sys.exit(f"Error enviando el correo por SES: {exc}")
        print(f"Correo enviado por SES vía {via}.", file=sys.stderr)

    if failed:
        sys.exit(f"{len(failed)} de {len(results)} consulta(s) fallaron.")
