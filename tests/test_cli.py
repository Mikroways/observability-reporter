"""Tests de hreidar.cli: la línea de comandos de punta a punta.

La API de métricas y el envío de correo se reemplazan por dobles de prueba.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from hreidar import cli, query

ROOT = Path(__file__).resolve().parent.parent

#: Respuestas de la API falsa, por consulta PromQL.
SAMPLES = {
    "up": [
        {"metric": {"job": "a"}, "value": [0, "1"]},
        {"metric": {"job": "b"}, "value": [0, "2"]},
    ],
    "empty": [],
}


@pytest.fixture(autouse=True)
def fake_fetch(monkeypatch):
    """La API falsa: devuelve SAMPLES, y error para cualquier otra consulta."""
    calls = []

    def fetch(url, org_id, promql):
        calls.append((url, org_id, promql))
        if promql not in SAMPLES:
            raise RuntimeError(f"consulta rota: {promql}")
        return SAMPLES[promql]

    monkeypatch.setattr(query, "fetch", fetch)
    return calls


@pytest.fixture
def sent(monkeypatch):
    """Reemplaza el envío por SES; devuelve los correos 'enviados'."""
    mails = []

    def send(document, subject):
        mails.append({"document": document, "subject": subject})
        return "API (test)"

    monkeypatch.setattr(cli, "send_email_ses", send)
    return mails


def test_main_a_stdout(capsys):
    cli.main(["-q", "up", "-t", "Mi reporte"])
    out = capsys.readouterr().out
    assert "<title>Mi reporte</title>" in out
    assert "2 resultado(s)." in out


def test_main_a_archivo(tmp_path, capsys):
    output = tmp_path / "r.html"
    cli.main(["-q", "up", "-q", "empty", "-o", str(output)])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "(2 consulta/s, 2 fila/s)" in captured.err
    assert "La consulta no devolvió resultados." in output.read_text("utf-8")


def test_main_usa_url_y_tenant_del_entorno(monkeypatch, fake_fetch, capsys):
    monkeypatch.setenv("METRICS_URL", "http://mimir/api/v1/query")
    monkeypatch.setenv("METRICS_ORG_ID", "tenant")
    cli.main(["-q", "up"])
    assert fake_fetch == [("http://mimir/api/v1/query", "tenant", "up")]
    assert "http://mimir/api/v1/query" in capsys.readouterr().out


def test_main_lee_el_archivo_de_consultas(tmp_path, capsys):
    config = tmp_path / "q.yaml"
    config.write_text(
        "title: Desde YAML\nqueries:\n  - title: Activos\n    query: up\n",
        encoding="utf-8",
    )
    cli.main(["-c", str(config)])
    out = capsys.readouterr().out
    assert "<title>Desde YAML</title>" in out
    assert "Activos" in out


def test_main_consulta_con_error(tmp_path, capsys):
    output = tmp_path / "r.html"
    with pytest.raises(SystemExit) as exc:
        cli.main(["-q", "up", "-q", "rota", "-o", str(output)])
    assert exc.value.code == "1 de 2 consulta(s) fallaron."
    # El reporte se genera igual, con el error en su sección.
    assert "consulta rota: rota" in output.read_text("utf-8")
    assert "[Consulta 2] Respuesta inesperada" in capsys.readouterr().err


def test_main_template_propio(monkeypatch, tmp_path, capsys):
    env_template = tmp_path / "env.j2"
    env_template.write_text("env:{{ title }}", encoding="utf-8")
    arg_template = tmp_path / "arg.j2"
    arg_template.write_text("arg:{{ title }}", encoding="utf-8")
    monkeypatch.setenv("REPORT_TEMPLATE", str(env_template))

    cli.main(["-q", "up", "-t", "T"])
    assert capsys.readouterr().out == "env:T"
    cli.main(["-q", "up", "-t", "T", "--template", str(arg_template)])
    assert capsys.readouterr().out == "arg:T"


def test_main_send(sent, capsys):
    cli.main(["-q", "up", "-t", "T", "--send"])
    captured = capsys.readouterr()
    # Con --send y sin -o no se escribe el HTML en stdout.
    assert captured.out == ""
    assert "Correo enviado por SES vía API (test)." in captured.err
    [mail] = sent
    assert mail["subject"] == "T - 2 resultado(s)"
    assert "<title>T</title>" in mail["document"]


def test_main_send_con_error_lo_indica_en_el_asunto(sent):
    with pytest.raises(SystemExit):
        cli.main(["-q", "up", "-q", "rota", "-t", "T", "--send"])
    assert sent[0]["subject"] == "T - 2 resultado(s) (1 consulta(s) con error)"


def test_main_send_asunto_de_la_variable(monkeypatch, sent):
    monkeypatch.setenv("SES_SUBJECT", "Asunto fijo")
    cli.main(["-q", "up", "--send"])
    assert sent[0]["subject"] == "Asunto fijo"


def test_main_send_falla(monkeypatch):
    def send(document, subject):
        raise OSError("sin red")

    monkeypatch.setattr(cli, "send_email_ses", send)
    with pytest.raises(SystemExit) as exc:
        cli.main(["-q", "up", "--send"])
    assert exc.value.code == "Error enviando el correo por SES: sin red"


def test_main_sin_consultas(tmp_path):
    with pytest.raises(SystemExit, match="No se pudo leer"):
        cli.main(["-c", str(tmp_path / "no-existe.yaml")])


@pytest.mark.parametrize(
    "command",
    [[sys.executable, "report.py"], [sys.executable, "-m", "hreidar"]],
    ids=["report.py", "python -m hreidar"],
)
def test_puntos_de_entrada(command):
    proc = subprocess.run(
        [*command, "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--send" in proc.stdout
