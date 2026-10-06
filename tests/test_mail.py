"""Tests de hreidar.mail: configuración y envío por Amazon SES."""

import email
import sys
from types import SimpleNamespace
from typing import ClassVar

import pytest

from hreidar import mail
from hreidar.mail import (
    MailSettings,
    SmtpSettings,
    build_message,
    load_mail_settings,
    send_api,
    send_email_ses,
    send_smtp,
)


@pytest.fixture
def ses_env(monkeypatch):
    """Variables mínimas para enviar por la API de SES."""
    monkeypatch.setenv("SES_SENDER", "reportes@example.com")
    monkeypatch.setenv("SES_TO", "a@example.com, b@example.com")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    return monkeypatch


@pytest.fixture
def smtp_env(ses_env):
    """Variables mínimas para enviar por SMTP."""
    ses_env.setenv("SES_SMTP_USER", "usuario")
    ses_env.setenv("SES_SMTP_PASSWORD", "clave")
    return ses_env


# --- load_mail_settings ------------------------------------------------------


def test_load_mail_settings_modo_api(ses_env):
    settings = load_mail_settings()
    assert settings == MailSettings(
        sender="reportes@example.com",
        recipients=["a@example.com", "b@example.com"],
        region="us-east-1",
        smtp=None,
    )


def test_load_mail_settings_usa_aws_default_region(ses_env):
    ses_env.delenv("AWS_REGION")
    ses_env.setenv("AWS_DEFAULT_REGION", "sa-east-1")
    assert load_mail_settings().region == "sa-east-1"


def test_load_mail_settings_modo_smtp(smtp_env):
    assert load_mail_settings().smtp == SmtpSettings(
        host="email-smtp.us-east-1.amazonaws.com",
        port=587,
        user="usuario",
        password="clave",
    )


def test_load_mail_settings_smtp_host_y_puerto(smtp_env):
    smtp_env.delenv("AWS_REGION")
    smtp_env.setenv("SES_SMTP_HOST", "smtp.local")
    smtp_env.setenv("SES_SMTP_PORT", "465")
    smtp = load_mail_settings().smtp
    assert (smtp.host, smtp.port) == ("smtp.local", 465)
    assert smtp.endpoint == "smtp.local:465"


@pytest.mark.parametrize(
    ("unset", "message"),
    [
        ("SES_SENDER", "SES_SENDER es obligatorio"),
        ("SES_TO", "SES_TO es obligatorio"),
        ("AWS_REGION", "AWS_REGION es obligatorio"),
    ],
)
def test_load_mail_settings_faltan_datos(ses_env, unset, message):
    ses_env.delenv(unset)
    with pytest.raises(SystemExit, match=message):
        load_mail_settings()


def test_load_mail_settings_destinatarios_vacios(ses_env):
    ses_env.setenv("SES_TO", " , ")
    with pytest.raises(SystemExit, match="SES_TO es obligatorio"):
        load_mail_settings()


@pytest.mark.parametrize("only", ["SES_SMTP_USER", "SES_SMTP_PASSWORD"])
def test_load_mail_settings_credenciales_smtp_incompletas(ses_env, only):
    ses_env.setenv(only, "x")
    with pytest.raises(SystemExit, match="van juntos"):
        load_mail_settings()


def test_load_mail_settings_smtp_sin_host_ni_region(smtp_env):
    smtp_env.delenv("AWS_REGION")
    with pytest.raises(SystemExit, match="SES_SMTP_HOST o AWS_REGION"):
        load_mail_settings()


# --- build_message -----------------------------------------------------------

SETTINGS = MailSettings(
    sender="reportes@example.com",
    recipients=["a@example.com", "b@example.com"],
    region="us-east-1",
    smtp=None,
)


def test_build_message():
    message = build_message("<p>hola</p>", "Asunto", SETTINGS)
    assert message["Subject"] == "Asunto"
    assert message["From"] == "reportes@example.com"
    assert message["To"] == "a@example.com, b@example.com"
    assert message.get_content_type() == "multipart/alternative"
    plain, html = message.iter_parts()
    assert plain.get_content_type() == "text/plain"
    assert "formato HTML" in plain.get_content()
    assert html.get_content_type() == "text/html"
    assert "<p>hola</p>" in html.get_content()


# --- send_smtp ---------------------------------------------------------------


class FakeSMTP:
    """Reemplazo de smtplib.SMTP / SMTP_SSL que registra las llamadas."""

    instances: ClassVar[list["FakeSMTP"]] = []

    def __init__(self, host, port, **kwargs):
        self.connection = (host, port, kwargs)
        self.calls = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append("quit")

    def starttls(self, context):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, message):
        self.calls.append(("send", message["Subject"]))


@pytest.fixture
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    plain = type("SMTP", (FakeSMTP,), {})
    ssl_ = type("SMTP_SSL", (FakeSMTP,), {})
    monkeypatch.setattr(mail.smtplib, "SMTP", plain)
    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", ssl_)
    return FakeSMTP.instances


def test_send_smtp_starttls(fake_smtp):
    message = build_message("<p/>", "Asunto", SETTINGS)
    send_smtp(message, SmtpSettings("smtp.local", 587, "u", "p"))
    [smtp] = fake_smtp
    assert type(smtp).__name__ == "SMTP"
    assert smtp.connection[:2] == ("smtp.local", 587)
    assert smtp.calls == [
        "starttls",
        ("login", "u", "p"),
        ("send", "Asunto"),
        "quit",
    ]


def test_send_smtp_ssl_en_puerto_465(fake_smtp):
    message = build_message("<p/>", "Asunto", SETTINGS)
    send_smtp(message, SmtpSettings("smtp.local", 465, "u", "p"))
    [smtp] = fake_smtp
    assert type(smtp).__name__ == "SMTP_SSL"
    assert "context" in smtp.connection[2]
    assert "starttls" not in smtp.calls
    assert ("send", "Asunto") in smtp.calls


# --- send_api ----------------------------------------------------------------


@pytest.fixture
def fake_boto3(monkeypatch):
    """Reemplaza boto3 por un módulo falso; devuelve las llamadas."""
    calls = []

    class Client:
        def send_email(self, **kwargs):
            calls.append(("send_email", kwargs))

    def client(name, region_name=None):
        calls.append(("client", name, region_name))
        return Client()

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=client))
    return calls


def test_send_api(fake_boto3):
    message = build_message("<p>hola</p>", "Asunto", SETTINGS)
    send_api(message, SETTINGS)
    (_, name, region), (_, kwargs) = fake_boto3
    assert (name, region) == ("sesv2", "us-east-1")
    assert kwargs["FromEmailAddress"] == "reportes@example.com"
    assert kwargs["Destination"] == {
        "ToAddresses": ["a@example.com", "b@example.com"]
    }
    sent = email.message_from_bytes(kwargs["Content"]["Raw"]["Data"])
    assert sent["Subject"] == "Asunto"
    assert sent.get_content_type() == "multipart/alternative"


# --- send_email_ses ----------------------------------------------------------


@pytest.fixture
def senders(monkeypatch):
    """Reemplaza send_smtp y send_api; devuelve qué se llamó."""
    calls = []
    monkeypatch.setattr(
        mail, "send_smtp", lambda msg, s: calls.append(("smtp", s.endpoint))
    )
    monkeypatch.setattr(
        mail, "send_api", lambda msg, s: calls.append(("api", s.region))
    )
    return calls


def test_send_email_ses_por_api(ses_env, senders):
    assert send_email_ses("<p/>", "Asunto") == "API (us-east-1)"
    assert senders == [("api", "us-east-1")]


def test_send_email_ses_por_smtp(smtp_env, senders):
    endpoint = "email-smtp.us-east-1.amazonaws.com:587"
    assert send_email_ses("<p/>", "Asunto") == f"SMTP ({endpoint})"
    assert senders == [("smtp", endpoint)]
