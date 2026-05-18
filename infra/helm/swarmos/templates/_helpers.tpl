{{/*
SwarmOS Helm helpers (Phase 6.E).
*/}}

{{- define "swarmos.name" -}}
swarmos
{{- end -}}

{{- define "swarmos.fullname" -}}
{{- $name := default "swarmos" .Release.Name -}}
{{- if eq $name (include "swarmos.name" .) -}}
{{- include "swarmos.name" . -}}
{{- else -}}
{{- printf "%s-%s" $name (include "swarmos.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{/*
Common labels applied to every resource.
*/}}
{{- define "swarmos.labels" -}}
app.kubernetes.io/name: {{ include "swarmos.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: swarmos
swarmos.io/site: {{ .Values.siteId | quote }}
{{- end -}}

{{/*
Compose an image reference. Prefer digest pinning over tag when present
(the image-sign workflow fills in `digest:` from the published GHCR
manifest digest).
*/}}
{{- define "swarmos.image" -}}
{{- $img := .img -}}
{{- if $img.digest -}}
{{ printf "%s@%s" $img.repository $img.digest }}
{{- else -}}
{{ printf "%s:%s" $img.repository $img.tag }}
{{- end -}}
{{- end -}}

{{/*
Hash of the rendered site config — placed as a Pod template annotation
so a config change rolls the Deployment without manual intervention.
*/}}
{{- define "swarmos.siteConfigHash" -}}
{{- toYaml .Values.siteConfig | sha256sum -}}
{{- end -}}
