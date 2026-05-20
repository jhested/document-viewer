{{- define "viewer.labels" -}}
app.kubernetes.io/name: document-viewer
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "viewer.apiImage" -}}
{{ .Values.image.registry }}/{{ .Values.image.repository }}-api:{{ .Values.image.tag }}
{{- end -}}

{{- define "viewer.workerImage" -}}
{{ .Values.image.registry }}/{{ .Values.image.repository }}-worker:{{ .Values.image.tag }}
{{- end -}}
