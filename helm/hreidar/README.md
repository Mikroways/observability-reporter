# hreidar

![Version: 0.1.0](https://img.shields.io/badge/Version-0.1.0-informational?style=flat-square)
![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square)
![AppVersion: 0.1.0](https://img.shields.io/badge/AppVersion-0.1.0-informational?style=flat-square)

Reporte periódico de métricas de Grafana Mimir / Prometheus, enviado por correo con Amazon SES.

Despliega [Hreidar](https://github.com/Mikroways/observability-reporter) como un
`CronJob`: en cada ejecución corre las consultas PromQL definidas en un
ConfigMap, arma el reporte HTML y lo envía por Amazon SES.

## Instalación

El chart se publica como artefacto OCI al crear un tag `X.Y.Z` en el repo:

```sh
helm upgrade --install hreidar oci://ghcr.io/mikroways/charts/hreidar \
  --version <X.Y.Z> --namespace observability --values values.yaml
```

Desde el repo, sin publicar: `helm upgrade --install hreidar helm/hreidar -f values.yaml`.

## Qué instala

| Recurso | Template | Cuándo |
|---------|----------|--------|
| `CronJob` | `cronjob.yaml` | siempre |
| `ServiceAccount` | `serviceaccount.yaml` | `serviceAccount.create=true` |
| `ConfigMap` de consultas | `configmap-queries.yaml` | salvo que se use `queries.existingConfigMap` |
| `ConfigMap` de entorno | `configmap.yaml` | si hay `config.env` |
| `Secret` de entorno | `secret.yaml` | si hay `config.secretEnv` |

## Las consultas

`queries.config` tiene la misma estructura que `queries.example.yaml` del repo:
`title` opcional y la lista `queries`, donde cada ítem define `query`
(obligatoria) y, opcionalmente, `title` y `org_id`. El chart lo serializa en el
ConfigMap, lo monta en `queries.mountPath` y apunta la variable `REPORT_CONFIG`
del contenedor al archivo resultante.

```yaml
queries:
  config:
    title: Reporte semanal
    queries:
      - title: Targets caídos
        query: up == 0
      - title: Latencia media HTTP > 0.3s (14d)
        org_id: mi-tenant
        query: |
          sort_desc(
            sum(increase(http_request_duration_seconds_sum{job="mi-app"}[14d])) by (handler)
            /
            sum(increase(http_request_duration_seconds_count{job="mi-app"}[14d])) by (handler)
            > 0.3
          )
```

Si las consultas se gestionan por fuera del chart (otro repo, otro operador),
usar `queries.existingConfigMap` y el chart solo las monta.

## Envío por SES: IRSA o credenciales SMTP

Con **IRSA** (recomendado) no hacen falta secretos: se anota el ServiceAccount
con el rol de IAM y `boto3` toma las credenciales del token proyectado.

```yaml
serviceAccount:
  create: true
  roleArn: arn:aws:iam::123456789012:role/hreidar
config:
  env:
    AWS_REGION: us-east-1
    SES_SENDER: reportes@example.com
    SES_TO: sre@example.com
```

El rol necesita `ses:SendEmail` y `ses:SendRawEmail`, y su trust policy debe
habilitar al ServiceAccount de este namespace.

Con **SMTP**, las credenciales van en `config.secretEnv` (cifrado con helm
secrets / SOPS) o en un Secret externo referenciado con `extraEnvFrom`:

```yaml
extraEnvFrom:
  - secretRef:
      name: hreidar-ses-credentials   # SES_SMTP_USER y SES_SMTP_PASSWORD
```

## Ejecutar el reporte a mano

```sh
kubectl create job --from=cronjob/<release>-hreidar <release>-hreidar-manual
kubectl logs --selector app.kubernetes.io/instance=<release> --tail=-1
```

## Tests del chart

```sh
helm lint helm/hreidar
helm unittest helm/hreidar
```

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| config.env | object | ver `values.yaml` | Key value pairs created using a ConfigMap and rendered as environment variables inside container. Allows gotpl expressions |
| config.secretEnv | object | `{}` | Sensitive key value pairs created using a Secret y renderizadas como variables de entorno. Pensado para `SES_SMTP_USER` / `SES_SMTP_PASSWORD`; cifrar con helm secrets (SOPS) o dejar vacío y usar `extraEnvFrom` |
| cronjob.activeDeadlineSeconds | int | `900` | Tiempo máximo de ejecución del Job, en segundos |
| cronjob.annotations | object | `{}` | Anotaciones del CronJob (helm hooks, argo waves, etc.) |
| cronjob.args | list | `["--send"]` | `args` del contenedor. `--send` envía el reporte por SES |
| cronjob.backoffLimit | int | `2` | Reintentos del Job antes de darlo por fallido |
| cronjob.command | list | `[]` | `command` del contenedor. Vacío usa el ENTRYPOINT de la imagen |
| cronjob.concurrencyPolicy | string | `"Forbid"` | Qué hacer si una ejecución se solapa con la anterior |
| cronjob.failedJobsHistoryLimit | int | `3` | Cantidad de Jobs fallidos que se conservan |
| cronjob.podAnnotations | object | `{}` | Anotaciones del pod. Se suman a los checksums del ConfigMap y el Secret |
| cronjob.podLabels | object | `{}` | Labels extra del pod |
| cronjob.restartPolicy | string | `"Never"` | restartPolicy del pod. Solo `Never` u `OnFailure` |
| cronjob.schedule | string | `"0 7 * * *"` | Expresión cron de ejecución del reporte (obligatoria) |
| cronjob.startingDeadlineSeconds | int | `300` | Margen en segundos para arrancar una ejecución demorada |
| cronjob.successfulJobsHistoryLimit | int | `3` | Cantidad de Jobs exitosos que se conservan |
| cronjob.suspend | bool | `false` | Suspender la ejecución programada |
| cronjob.timeZone | string | `""` | Zona horaria de la expresión cron. Requiere Kubernetes >= 1.27 |
| cronjob.ttlSecondsAfterFinished | int | `86400` | Segundos hasta que el Job terminado se borra solo |
| env | object | `{}` | Key value pairs created as environment of the container. Tiene precedencia sobre `config.env` y `config.secretEnv`. Allows gotpl expressions |
| extraEnvFrom | list | `[]` | Array of objects added as-is to the container `envFrom`. Útil para Secrets creados por External Secrets Operator. Allows gotpl expressions |
| extraVolumeMounts | list | `[]` | Array of objects added as-is to the container `volumeMounts` |
| extraVolumes | list | `[]` | Array of objects added as-is to the pod `volumes` |
| image.pullPolicy | string | `"IfNotPresent"` | Image pullPolicy |
| image.repository | string | `"ghcr.io/mikroways/observability-reporter"` | Imagen del reporte (Hreidar) |
| image.tag | string | `""` | Tag de la imagen. Por defecto, el `appVersion` del chart |
| imagePullSecrets | list | `[]` | Array of objects, each one having key `name:` and value is a secretName. Allows gotpl expressions |
| podSecurityContext | object | `runAsNonRoot: true`, uid/gid `10001`, `seccompProfile: RuntimeDefault` | securityContext del pod. Los uid/gid son los que crea el Dockerfile |
| queries.config | object | un reporte de ejemplo con `up == 0` | Contenido del archivo de consultas, con la misma estructura que `queries.example.yaml`. Allows gotpl expressions |
| queries.existingConfigMap | string | `""` | Usar un ConfigMap ya existente con las consultas en lugar del que crea el chart. Allows gotpl expressions |
| queries.key | string | `"queries.yaml"` | Clave del ConfigMap que contiene el archivo de consultas |
| queries.mountPath | string | `"/etc/hreidar"` | Directorio donde se monta el archivo de consultas |
| resources | object | requests `50m`/`128Mi`, limits `500m`/`256Mi` | Recursos del contenedor del reporte |
| securityContext | object | `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]` | securityContext del contenedor del reporte |
| serviceAccount.annotations | object | `{}` | Anotaciones extra del ServiceAccount. Se suman a la de IRSA. Allows gotpl expressions |
| serviceAccount.create | bool | `true` | Crear o no el ServiceAccount del CronJob |
| serviceAccount.name | string | `""` | Nombre del ServiceAccount. Si queda vacío y `create` es true, se usa el fullname del release |
| serviceAccount.roleArn | string | `""` | ARN del rol de IAM a asumir con IRSA. Si se define, se agrega la anotación `eks.amazonaws.com/role-arn`. El rol necesita `ses:SendEmail` / `ses:SendRawEmail` y su trust policy debe habilitar al ServiceAccount de este namespace. Allows gotpl expressions |

----------------------------------------------
Esta tabla se regenera con [helm-docs](https://github.com/norwoodj/helm-docs)
a partir de `values.yaml` y `README.md.gotmpl`.
