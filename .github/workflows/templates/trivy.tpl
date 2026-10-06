{{- /* Resumen en Markdown de Trivy (format: template). */ -}}
{{- $found := false }}
{{- range . }}
{{- if or .Vulnerabilities .Secrets .Misconfigurations }}{{ $found = true }}{{ end }}
{{- end }}
{{- if not $found }}

No findings.
{{- else }}
{{- range . }}
{{- $target := .Target }}
{{- if .Vulnerabilities }}

#### Vulnerabilities: `{{ $target }}`

| Severity | ID | Package | Installed | Fixed | Title |
| --- | --- | --- | --- | --- | --- |
{{- range .Vulnerabilities }}
| {{ .Severity }} | [{{ .VulnerabilityID }}]({{ .PrimaryURL }}) | {{ .PkgName }} | {{ .InstalledVersion }} | {{ .FixedVersion }} | {{ .Title | replace "|" "\\|" }} |
{{- end }}
{{- end }}
{{- if .Secrets }}

#### Secrets: `{{ $target }}`

| Severity | Rule | Line | Title |
| --- | --- | --- | --- |
{{- range .Secrets }}
| {{ .Severity }} | {{ .RuleID }} | {{ .StartLine }} | {{ .Title | replace "|" "\\|" }} |
{{- end }}
{{- end }}
{{- if .Misconfigurations }}

#### Misconfigurations: `{{ $target }}`

| Severity | ID | Line | Title | Message |
| --- | --- | --- | --- | --- |
{{- range .Misconfigurations }}
| {{ .Severity }} | [{{ .ID }}]({{ .PrimaryURL }}) | {{ .CauseMetadata.StartLine }} | {{ .Title | replace "|" "\\|" }} | {{ .Message | replace "|" "\\|" | replace "\n" " " }} |
{{- end }}
{{- end }}
{{- end }}
{{- end }}
