# Hreidar

Reporte de métricas para Grafana Mimir / Prometheus.

**Hreidar** ejecuta **N consultas PromQL** contra la API de Grafana Mimir /
Prometheus y genera un reporte **HTML** (apto para enviar por correo) con una
sección por consulta. Las columnas de cada tabla se arman dinámicamente según
las etiquetas que devuelva la consulta, así que sirve para cualquier métrica.
Opcionalmente envía el reporte por **Amazon SES**.

## Requisitos

- Python 3.11+
- [`direnv`](https://direnv.net/) (opcional, pero recomendado)
- Acceso de red al endpoint de métricas (Mimir o Prometheus)

## Instalación

Con **direnv** (gestiona el entorno virtual automáticamente):

```bash
direnv allow                      # crea/activa el venv en .direnv/ y carga variables
pip install -r requirements.txt   # instala las dependencias en el venv
cp queries.example.yaml queries.yaml  # definir las consultas
```

Sin direnv (venv manual):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
set -a; . ./.envrc; set +a          # cargar variables de entorno
```

## Uso

```bash
python report.py                                  # consultas de queries.yaml -> stdout
python report.py -o reporte.html                  # a archivo
python report.py -c otras.yaml                    # otro archivo de consultas
python report.py -q 'up == 0' -q 'sum(up)'        # consultas ad hoc (ignora el YAML)
python report.py --send                           # genera y envía por SES
```

`python -m hreidar` es equivalente a `python report.py`, con los mismos
argumentos.

### Las consultas

Se definen en un archivo YAML (por defecto `queries.yaml`; se cambia con
`REPORT_CONFIG` o `--config`). Ver `queries.example.yaml`:

```yaml
title: Reporte de métricas      # opcional
queries:
  - title: Targets caídos       # opcional (default: "Consulta N")
    description: Nodos que no respondieron al scrape.  # opcional
    query: up == 0              # obligatorio
    unit: targets               # opcional
    org_id: mi-tenant           # opcional (default: METRICS_ORG_ID)
  - title: Otra consulta
    query: |
      sort_desc(sum(rate(http_requests_total[5m])) by (instance))
```

`description` es el texto que va debajo del título de la sección, y es lo que
lee quien recibe el reporte: el PromQL no se muestra. `unit` se imprime después
de cada valor, tal cual se escribe (`s`, `ms`, `%`, `MiB`, `millicores`,
`errores`); el número no se convierte ni se reformatea. Las dos son opcionales:
sin ellas la sección muestra solo el título y el número pelado.

Si se pasa `--query` (una o más veces) se ejecutan solo esas consultas y no se
lee el archivo. No hay consulta por defecto: sin archivo ni `--query` el
script termina con error.

Cada consulta debe ser **instantánea y devolver un vector** (no un `matrix` /
range query). Cada sección del reporte tiene una columna por etiqueta presente
en el resultado, más una columna `Valor`, ordenando de mayor a menor.

Si una consulta falla, su sección muestra el error, el resto del reporte se
genera (y envía) igual y el proceso termina con código de salida `1`.

## Configuración

Variables de entorno (definidas en `.envrc`), sin tocar el código:

| Variable         | Descripción                                             | Valor por defecto                                             |
| ---------------- | ------------------------------------------------------- | ------------------------------------------------------------ |
| `METRICS_URL`    | Endpoint de consulta (API Prometheus de Mimir)          | `http://localhost:9090/api/v1/query`                         |
| `METRICS_ORG_ID` | Tenant de Mimir (header `X-Scope-OrgID`); vacío = omite | vacío                                                        |
| `REPORT_CONFIG`  | Archivo YAML de consultas                               | `queries.yaml`                                               |
| `REPORT_TITLE`   | Título del reporte (el del YAML y `--title` lo pisan)   | `Reporte de métricas`                                        |
| `REPORT_TEMPLATE`| Template Jinja2 del HTML (lo pisa `--template`)         | `templates/report.html.j2` (junto a `report.py`)             |

> **Nota:** Mimir expone la API bajo el prefijo `/prometheus`. Usar
> `/api/v1/query` directamente devuelve `404`.

### El HTML (template Jinja2)

El HTML se genera con el template [Jinja2](https://jinja.palletsprojects.com/)
`templates/report.html.j2`. Para cambiar el diseño se edita ese archivo, o se
usa otro con `--template` / `REPORT_TEMPLATE`, sin tocar el código.

El escapado de HTML es automático. Variables disponibles:

| Variable     | Contenido                                                               |
| ------------ | ----------------------------------------------------------------------- |
| `title`      | Título del reporte                                                      |
| `generated`  | Fecha de generación (UTC)                                               |
| `url`        | Endpoint de métricas consultado                                         |
| `results`    | Lista de consultas: `title`, `description`, `query`, `unit`, `org_id`, `columns`, `rows`, `error` |
| `total_rows` | Total de filas de todas las consultas                                   |
| `failed`     | Cantidad de consultas con error                                         |

Cada elemento de `rows` tiene `labels` (diccionario de etiquetas) y `value`
(valor ya formateado). El template por defecto no imprime `query`, pero sigue
disponible para un template propio. Ejemplo mínimo:

```jinja
{% for r in results %}
  <h3>{{ r.title }}</h3>
  {% if r.error %}<p>Error: {{ r.error }}</p>{% endif %}
  {% for row in r.rows %}
    <p>{{ row.labels.instance }}: {{ row.value }}</p>
  {% endfor %}
{% endfor %}
```

Si se usa una variable inexistente el script falla con un error claro, en vez
de dejar el campo vacío. Los estilos van inline porque los clientes de correo
no soportan hojas de estilo externas.

### La imagen

El workflow `.github/workflows/release.yml` construye la imagen y la publica en
`ghcr.io/mikroways/observability-reporter` al crear un tag `X.Y.Z`; la imagen
lleva el mismo tag (por ejemplo `ghcr.io/mikroways/observability-reporter:1.0.0`).
En los pull requests solo la construye, sin publicarla.

La primera vez que se publica, GHCR crea el paquete como **privado**, aunque el
repo sea público. Para que se pueda bajar sin credenciales (por ejemplo desde
el cluster, sin `imagePullSecret`), hacerlo público una sola vez en
*Packages → observability-reporter → Package settings → Change visibility →
Public*.

```bash
git tag 1.0.0 && git push origin 1.0.0
```

### En el cluster

La imagen no incluye consultas: montar el YAML (por ejemplo desde un
ConfigMap) en `/app/queries.yaml`, o en otra ruta indicada con `REPORT_CONFIG`.
El template por defecto viene en la imagen; para usar otro, montarlo y
apuntar `REPORT_TEMPLATE` a esa ruta.

De eso se encarga el chart de Helm del repo: ver
[Despliegue en Kubernetes](#despliegue-en-kubernetes).

## Envío por correo (Amazon SES)

Con `--send` el reporte se manda por Amazon SES, de una de dos formas:

- **API de SES (recomendado en EKS):** si **no** se definen las credenciales
  SMTP, se usa la API de SES con `boto3` y la cadena de credenciales por
  defecto de AWS: IRSA, variables `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`,
  perfil de `~/.aws`, rol de la instancia, etc.
- **SMTP:** si se definen `SES_SMTP_USER` y `SES_SMTP_PASSWORD`, se usa el
  endpoint SMTP de SES con `smtplib`.

| Variable            | Descripción                                                     |
| ------------------- | --------------------------------------------------------------- |
| `SES_SENDER`        | Remitente verificado en SES (obligatorio)                       |
| `SES_TO`            | Destinatarios separados por coma (obligatorio)                  |
| `SES_SUBJECT`       | Asunto (opcional; hay uno por defecto con el título)            |
| `AWS_REGION`        | Región de SES (ej: `us-east-1`); obligatoria con la API, y con SMTP si no se define `SES_SMTP_HOST` |
| `SES_SMTP_USER`     | Usuario SMTP de SES (solo SMTP)                                 |
| `SES_SMTP_PASSWORD` | Contraseña SMTP de SES (solo SMTP)                              |
| `SES_SMTP_HOST`     | Host SMTP (opcional; default `email-smtp.$AWS_REGION.amazonaws.com`) |
| `SES_SMTP_PORT`     | Puerto SMTP (opcional; default `587` con STARTTLS, `465` = SSL) |

### Con IRSA (IAM role para la service account)

IRSA entrega credenciales temporales, que **no** sirven para SMTP: en EKS se
usa la API. Pasos:

1. Crear un IAM role con trust policy para el OIDC provider del cluster,
   limitada a la service account del job, y esta política:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["ses:SendEmail", "ses:SendRawEmail"],
         "Resource": "*",
         "Condition": {
           "StringEquals": { "ses:FromAddress": "reportes@example.com" }
         }
       }
     ]
   }
   ```

   `Resource` se puede acotar a la identidad verificada
   (`arn:aws:ses:<región>:<cuenta>:identity/<dominio o casilla>`).

2. Anotar la service account con el role:

   ```yaml
   apiVersion: v1
   kind: ServiceAccount
   metadata:
     name: hreidar
     annotations:
       eks.amazonaws.com/role-arn: arn:aws:iam::<cuenta>:role/<role>
   ```

3. Usarla en el pod (`serviceAccountName: hreidar`) y definir `SES_SENDER`,
   `SES_TO` y `AWS_REGION`, **sin** `SES_SMTP_USER`/`SES_SMTP_PASSWORD`. El
   webhook de EKS inyecta `AWS_ROLE_ARN` y `AWS_WEB_IDENTITY_TOKEN_FILE`, y
   `boto3` las toma solo.

### Con SMTP

Las **credenciales SMTP** se crean en la consola de SES (*SMTP settings →
Create SMTP credentials*). **No** son las AWS access keys: son un usuario y
contraseña SMTP específicos.

## Despliegue en Kubernetes

El chart de Helm está en `helm/hreidar` y despliega el reporte como un
`CronJob`:

| Recurso                                                       | Cuándo                                        |
| ------------------------------------------------------------- | --------------------------------------------- |
| `CronJob` con el schedule del reporte                         | siempre                                       |
| `ServiceAccount` anotada para IRSA con `serviceAccount.roleArn` | `serviceAccount.create=true`                |
| `ConfigMap` con el archivo de consultas, al que apunta `REPORT_CONFIG` | salvo que se use `queries.existingConfigMap` |
| `ConfigMap` con las variables de entorno                      | si hay `config.env`                           |
| `Secret` con las variables sensibles                          | si hay `config.secretEnv`                     |

Valores mínimos para enviar por SES con IRSA:

```yaml
serviceAccount:
  roleArn: arn:aws:iam::<cuenta>:role/<role>

cronjob:
  schedule: "0 7 * * *"
  timeZone: America/Argentina/Cordoba

config:
  env:
    METRICS_URL: https://mimir.example.com/prometheus/api/v1/query
    METRICS_ORG_ID: mi-tenant
    AWS_REGION: us-east-1
    SES_SENDER: reportes@example.com
    SES_TO: sre@example.com

queries:
  config:
    title: Reporte de métricas
    queries:
      - title: Targets caídos
        description: Nodos que no respondieron al scrape.
        query: up == 0
        unit: targets
```

```bash
helm upgrade --install hreidar oci://ghcr.io/mikroways/charts/hreidar \
  --version 1.0.0 --namespace observability --values values.yaml
```

Las credenciales SMTP, si se usan en lugar de IRSA, van en `config.secretEnv`
(cifrado con helm secrets / SOPS) o en un Secret externo referenciado con
`extraEnvFrom`. Para disparar el reporte sin esperar al schedule:

```bash
kubectl create job --from=cronjob/hreidar hreidar-manual
```

El detalle de cada valor está en `helm/hreidar/README.md`.

### Publicación del chart

El chart lo maneja `.github/workflows/_chart.yml`: `helm lint`, los unit tests y
el empaquetado. Lo invocan el workflow del pull request y el del push a `main`;
solo este último publica el chart como artefacto OCI en
`ghcr.io/mikroways/charts/hreidar`. En los pull requests el `.tgz` queda como
artefacto del run.

La versión la manda `helm/hreidar/Chart.yaml`, no el tag de git:

- `version` es la del chart. El job `package` primero mira si el commit tocó
  `helm/`; si no lo tocó, no hace nada. Si lo tocó, chequea la versión contra el
  registry y **falla** si ya está publicada, así que cada cambio bajo `helm/` va
  con su bump. El error aparece ya en el pull request.
- `appVersion` es el tag de la imagen que despliega el chart, y sube solo cuando
  se publica una imagen nueva (que sigue saliendo del tag `X.Y.Z`, ver
  [La imagen](#la-imagen)).

Igual que con la imagen, la primera vez GHCR crea el paquete como **privado**:
hay que hacerlo público una vez en *Packages → charts/hreidar → Package
settings → Change visibility*.

### Dónde vive la configuración del despliegue

Este repo tiene el código, la imagen y el chart. Los valores de cada ambiente
(schedule, consultas, destinatarios, rol de IRSA) y la versión desplegada viven
en el repo GitOps del cliente, no acá. Al liberar una versión nueva, el tag se
actualiza **a mano** en ese repo: el pipeline termina en la publicación.

## Cómo probar

### 1. Contra Mimir (requiere acceso al endpoint)

```bash
cp queries.example.yaml queries.yaml   # ajustar las consultas
python report.py -o reporte.html       # abrir reporte.html en el navegador
echo $?                                # 0 = todas OK, 1 = alguna consulta falló
```

### 2. Sin acceso a Mimir: Prometheus local

Levantar un Prometheus que se monitorea a sí mismo:

```bash
docker run -d --rm --name prom-test -p 9090:9090 prom/prometheus
```

Esperar unos 15 segundos al primer scrape; antes de eso `up` no devuelve datos.

Crear `prueba.yaml` con una consulta con datos, una vacía y una inválida
(`up[5m]` devuelve una `matrix`, así se ve cómo queda una sección con error):

```yaml
title: Prueba local
queries:
  - title: Targets activos
    query: up
  - title: Targets caídos (vacío)
    query: up == 0
  - title: Consulta inválida (error)
    query: up[5m]
```

Generar el reporte (Prometheus no usa tenant, por eso `METRICS_ORG_ID` vacío):

```bash
METRICS_URL=http://localhost:9090/api/v1/query METRICS_ORG_ID= \
  python report.py -c prueba.yaml -o prueba.html
```

Resultado esperado: tres secciones (1 resultado, "no devolvió resultados" y el
error en rojo), el error también por stderr y código de salida `1`.

Para probar un template propio, agregar `--template mi-template.html.j2`.

Para probar consultas sueltas sin archivo:

```bash
METRICS_URL=http://localhost:9090/api/v1/query METRICS_ORG_ID= \
  python report.py -q up -q 'up == 0' -o prueba.html
```

### 3. La imagen Docker

Igual que en el cluster: el archivo de consultas se monta en `/app/queries.yaml`.

```bash
docker build -t hreidar:dev .
docker run --rm --network host \
  -v "$PWD/prueba.yaml:/app/queries.yaml:ro" \
  -e METRICS_URL=http://localhost:9090/api/v1/query -e METRICS_ORG_ID= \
  hreidar:dev -o /dev/stdout > prueba.html
```

Sin argumentos la imagen ejecuta `--send`; pasar `-o` evita el envío.

### 4. Envío por correo

Con las variables `SES_*` y `AWS_REGION` cargadas (ver arriba), mandarlo a una
casilla propia. Sin `SES_SMTP_*` usa la API con las credenciales de AWS locales
(por ejemplo `AWS_PROFILE`):

```bash
SES_TO="tu.casilla@mikroways.net" python report.py --send
```

Al terminar, `docker stop prom-test`.

## Tests

Los tests usan [pytest](https://docs.pytest.org/) y están en `tests/`, un
archivo por módulo de `hreidar/`. No necesitan red ni credenciales: la API de
métricas, SMTP y `boto3` se reemplazan por dobles de prueba, y cada test
arranca sin las variables `METRICS_*`, `REPORT_*`, `SES_*` y `AWS_*` del
entorno.

```bash
pip install -r requirements-dev.txt
python -m pytest                       # todos los tests
python -m pytest tests/test_mail.py    # los de un módulo
python -m pytest -k smtp -v            # los que coinciden con un nombre
```

En GitHub los corre el job `pytest` de `.github/workflows/_checks.yml`, en cada
pull request y en cada push a `main`.

También corren con pre-commit (hook `pytest`) en cada commit que toque
`hreidar/`, `tests/`, `templates/`, `report.py`, `pyproject.toml` o los
`requirements*.txt`. pre-commit instala las dependencias de los tests en su
propio entorno (listadas en `.pre-commit-config.yaml`; si cambian las de
`requirements.txt`, actualizarlas ahí también). Para commitear sin correrlos:
`SKIP=pytest git commit ...`.

El chart de Helm tiene sus propios tests, con
[helm-unittest](https://github.com/helm-unittest/helm-unittest), en
`helm/hreidar/tests/`:

```bash
helm plugin install https://github.com/helm-unittest/helm-unittest \
  --version 1.2.1 --verify=false   # --verify=false hace falta con helm 4
helm lint --strict helm/hreidar
helm unittest helm/hreidar
```

En GitHub los corre el job `test` de `.github/workflows/_chart.yml`.

## Linters

Los linters se corren con [pre-commit](https://pre-commit.com/), que instala
cada herramienta en su propio entorno:

| Linter                                                       | Archivos      | Configuración            |
| ------------------------------------------------------------ | ------------- | ------------------------ |
| [ruff](https://docs.astral.sh/ruff/) (lint y formato)        | `*.py`        | `pyproject.toml`         |
| [yamllint](https://yamllint.readthedocs.io/)                 | `*.yaml`      | `.yamllint.yaml`         |
| [hadolint](https://github.com/hadolint/hadolint)             | `Dockerfile`  | (por defecto)            |
| [markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2) | `*.md` | `.markdownlint-cli2.yaml` |
| [pre-commit-hooks](https://github.com/pre-commit/pre-commit-hooks) | todos   | espacios finales, fin de archivo, conflictos |
| pytest (hook local)                                          | código y tests | ver [Tests](#tests)  |

```bash
pip install pre-commit
pre-commit install            # corre los linters en cada commit
pre-commit run --all-files    # corre los linters sobre todo el repo
```

En GitHub corre lo mismo el job `pre-commit` de `.github/workflows/_checks.yml`,
en cada pull request y en cada push a `main`.

yamllint ignora `helm/*/templates/`: son Go templates, no YAML. El chart se
valida con `helm lint` (ver [Tests](#tests)).

## Análisis de seguridad

`.github/workflows/_checks.yml` trae, además de los linters y los tests, dos
jobs de seguridad, que corren en cada pull request y en cada push a `main`:

| Job        | Qué revisa                                                                  |
| ---------- | --------------------------------------------------------------------------- |
| TruffleHog | Secretos en el historial de git (solo los commits nuevos del push o del PR) |
| Trivy      | Dependencias vulnerables, secretos y malas configuraciones (HIGH/CRITICAL)  |

Cada job falla si encuentra algo y deja un resumen en Markdown en la página
del run. Los templates de esos resúmenes están en `.github/workflows/templates/`.

Las actions y las herramientas están fijadas a un SHA o digest.

## Integración continua

Hay **un workflow por disparador**, así cada commit produce un solo run en la
pestaña Actions en lugar de varios que parecen no relacionados:

| Workflow            | Disparador              | Qué corre                                                      |
| ------------------- | ----------------------- | -------------------------------------------------------------- |
| `pull-request.yml`  | `pull_request`          | checks, lint y unit tests del chart con su chequeo de versión, y build de la imagen (sin publicar nada) |
| `push.yml`          | push a `main`           | checks y publicación del chart                                  |
| `release.yml`       | push de un tag `X.Y.Z`  | build y publicación de la imagen                                |

En `pull-request.yml` un push nuevo a la rama del PR cancela el run anterior.
`push.yml` no cancela: publica el chart, y matar un run a medio publicar puede
dejar sin publicar una versión que ya se mergeó.

Los jobs viven en tres workflows reusables, con `on: workflow_call` y nada más.
Eso los deja fuera del listado de Actions y evita repetir los pasos entre
disparadores:

| Reusable        | Jobs                                                        |
| --------------- | ----------------------------------------------------------- |
| `_checks.yml`   | `pre-commit`, `pytest`, `trufflehog`, `trivy-fs`             |
| `_chart.yml`    | `test` (helm lint y unit tests) y `package`                  |
| `_image.yml`    | `build`                                                      |

El tag `X.Y.Z` no vuelve a correr los checks: el commit que se taggea ya pasó
por el push a `main`.

> **Nota:** para configurar checks obligatorios en branch protection, los
> nombres son los del job llamador más los del job llamado:
> `checks / Linters (pre-commit)`, `checks / Tests (pytest)`,
> `checks / Secrets in git history (TruffleHog)`,
> `checks / Vulnerabilities, secrets, misconfig (Trivy)`,
> `chart / Lint y unit tests del chart`,
> `chart / Empaquetar y publicar el chart` e `image / Construir la imagen`.
> Si se le cambia el `name:` a un job, el check obligatorio deja de reportar y
> los pull requests quedan bloqueados: hay que actualizarlo en los dos lados.

## Archivos

| Archivo            | Descripción                                              |
| ------------------ | ------------------------------------------------------- |
| `report.py`        | Punto de entrada (equivale a `python -m hreidar`)        |
| `hreidar/`         | Código, un módulo por responsabilidad (ver `docs/funciones.md`) |
| `queries.example.yaml` | Ejemplo de archivo de consultas                     |
| `docs/funciones.md` | Módulos del paquete y explicación de cada función   |
| `templates/report.html.j2` | Template Jinja2 del HTML del reporte            |
| `requirements.txt` | Dependencias de Python (`requests`, `PyYAML`, `Jinja2`, `boto3`) |
| `requirements-dev.txt` | Dependencias para desarrollo y tests (`pytest`)     |
| `tests/`           | Tests con pytest, uno por módulo de `hreidar/`           |
| `.envrc`           | Variables de entorno y `layout python` para direnv       |
| `Dockerfile`       | Imagen para ejecutar el reporte en el cluster            |
| `.gitignore`       | Ignora el venv, cachés y los reportes generados          |
| `.dockerignore`    | Excluye de la imagen el venv, `.git/` y los reportes generados |
| `.pre-commit-config.yaml` | Linters del repo (ver [Linters](#linters))        |
| `helm/hreidar/` | Chart de Helm que despliega el reporte como CronJob |
| `.github/workflows/` | CI: un workflow por disparador (ver [Integración continua](#integración-continua)) |
| `.github/workflows/templates/` | Templates de los resúmenes de cada herramienta |
| `pyproject.toml`   | Configuración de ruff y pytest                           |
| `.yamllint.yaml`   | Configuración de yamllint                                |
| `.markdownlint-cli2.yaml` | Configuración de markdownlint                     |
