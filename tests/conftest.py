"""Fixtures comunes de los tests."""

import os

import pytest

#: Prefijos de las variables de entorno que lee Hreidar.
ENV_PREFIXES = ("METRICS_", "REPORT_", "SES_", "AWS_")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Cada test arranca sin la configuración del entorno (ej: .envrc)."""
    for key in list(os.environ):
        if key.startswith(ENV_PREFIXES):
            monkeypatch.delenv(key)
