FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY report.py .
COPY hreidar/ hreidar/
COPY templates/ templates/

RUN useradd --create-home --uid 10001 appuser
USER 10001

ENTRYPOINT ["python", "report.py"]
CMD ["--send"]
