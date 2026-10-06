"""Envío del reporte por Amazon SES, por SMTP o por la API."""

import os
import smtplib
import ssl
import sys
from dataclasses import dataclass
from email.message import EmailMessage

from hreidar.config import split_list

SMTP_TIMEOUT = 30
SMTP_DEFAULT_PORT = 587
SMTP_SSL_PORT = 465


@dataclass(frozen=True)
class SmtpSettings:
    """Parámetros de conexión al endpoint SMTP de Amazon SES."""

    host: str
    port: int
    user: str
    password: str

    @property
    def endpoint(self) -> str:
        """Devuelve el endpoint SMTP en formato host:puerto."""
        return f"{self.host}:{self.port}"


@dataclass(frozen=True)
class MailSettings:
    """Parámetros de envío por Amazon SES.

    `smtp` es None cuando no hay credenciales SMTP: se usa la API de SES.
    """

    sender: str
    recipients: list[str]
    region: str | None
    smtp: SmtpSettings | None


def load_mail_settings() -> MailSettings:
    """Lee y valida las variables de entorno de envío por SES.

    Termina el proceso con un mensaje de error si falta algún dato obligatorio.
    """
    sender = os.environ.get("SES_SENDER")
    recipients = split_list(os.environ.get("SES_TO", ""))
    region = os.environ.get("AWS_REGION") or os.environ.get(
        "AWS_DEFAULT_REGION"
    )

    smtp_user = os.environ.get("SES_SMTP_USER")
    smtp_password = os.environ.get("SES_SMTP_PASSWORD")
    smtp_host = os.environ.get("SES_SMTP_HOST")
    smtp_port = int(os.environ.get("SES_SMTP_PORT", str(SMTP_DEFAULT_PORT)))

    if not sender:
        sys.exit("SES_SENDER es obligatorio para enviar por correo (--send).")
    if not recipients:
        sys.exit("SES_TO es obligatorio para enviar por correo (--send).")
    if bool(smtp_user) != bool(smtp_password):
        sys.exit(
            "SES_SMTP_USER y SES_SMTP_PASSWORD van juntos: definí ambos para "
            "enviar por SMTP, o ninguno para usar la API de SES."
        )

    if not smtp_user:
        if not region:
            sys.exit("AWS_REGION es obligatorio para usar la API de SES.")
        return MailSettings(sender, recipients, region, smtp=None)

    if not smtp_host:
        if not region:
            sys.exit(
                "Definí SES_SMTP_HOST o AWS_REGION para armar el host SMTP "
                "de SES."
            )
        smtp_host = f"email-smtp.{region}.amazonaws.com"

    smtp = SmtpSettings(
        host=smtp_host,
        port=smtp_port,
        user=smtp_user,
        password=smtp_password,
    )
    return MailSettings(sender, recipients, region, smtp=smtp)


def build_message(
    html_body: str,
    subject: str,
    settings: MailSettings,
) -> EmailMessage:
    """Arma el correo multipart (texto plano + alternativa HTML)."""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.sender
    message["To"] = ", ".join(settings.recipients)
    message.set_content(
        "Este reporte está en formato HTML. "
        "Usá un cliente que soporte HTML para verlo."
    )
    message.add_alternative(html_body, subtype="html")
    return message


def send_smtp(message: EmailMessage, settings: SmtpSettings) -> None:
    """Envía el correo por el endpoint SMTP de SES.

    Por defecto usa el puerto 587 con STARTTLS; con el puerto 465 usa SSL
    directo.
    """
    context = ssl.create_default_context()

    if settings.port == SMTP_SSL_PORT:
        with smtplib.SMTP_SSL(
            settings.host,
            settings.port,
            context=context,
            timeout=SMTP_TIMEOUT,
        ) as smtp:
            smtp.login(settings.user, settings.password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(
            settings.host, settings.port, timeout=SMTP_TIMEOUT
        ) as smtp:
            smtp.starttls(context=context)
            smtp.login(settings.user, settings.password)
            smtp.send_message(message)


def send_api(message: EmailMessage, settings: MailSettings) -> None:
    """Envía el correo por la API de SES (SendEmail de SESv2, contenido raw).

    Usa la cadena de credenciales por defecto de boto3, que incluye IRSA
    (AWS_ROLE_ARN + AWS_WEB_IDENTITY_TOKEN_FILE) en EKS.
    """
    import boto3  # noqa: PLC0415 - solo hace falta con la API de SES

    client = boto3.client("sesv2", region_name=settings.region)
    client.send_email(
        FromEmailAddress=settings.sender,
        Destination={"ToAddresses": settings.recipients},
        Content={"Raw": {"Data": message.as_bytes()}},
    )


def send_email_ses(html_body: str, subject: str) -> str:
    """Envía el reporte HTML por Amazon SES, por SMTP o por la API.

    Devuelve una descripción del medio utilizado, para el log.
    """
    settings = load_mail_settings()
    message = build_message(html_body, subject, settings)

    if settings.smtp:
        send_smtp(message, settings.smtp)
        return f"SMTP ({settings.smtp.endpoint})"

    send_api(message, settings)
    return f"API ({settings.region})"
