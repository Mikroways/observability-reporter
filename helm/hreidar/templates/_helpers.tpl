{{/*
Expand the name of the chart.
*/}}
{{- define "hreidar.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "hreidar.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "hreidar.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "hreidar.labels" -}}
helm.sh/chart: {{ include "hreidar.chart" . }}
{{ include "hreidar.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "hreidar.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hreidar.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "hreidar.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "hreidar.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Name of the ConfigMap holding the queries file
*/}}
{{- define "hreidar.queriesConfigMapName" -}}
{{- if .Values.queries.existingConfigMap }}
{{- tpl .Values.queries.existingConfigMap . }}
{{- else }}
{{- printf "%s-queries" (include "hreidar.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Full path of the queries file inside the container
*/}}
{{- define "hreidar.queriesPath" -}}
{{- printf "%s/%s" (trimSuffix "/" .Values.queries.mountPath) .Values.queries.key }}
{{- end }}
