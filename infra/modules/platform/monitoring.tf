resource "google_monitoring_notification_channel" "operations" {
  display_name = "OTM Guard ${var.environment}"
  type         = "email"
  labels       = { email_address = var.alert_email }
}
resource "google_logging_metric" "failed_runs" {
  name   = "${local.name}-failures"
  filter = "resource.type=\"cloud_run_job\" AND jsonPayload.event=\"run_failed\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}
resource "google_monitoring_alert_policy" "failures" {
  display_name          = "OTM Guard: falha de execução ${var.environment}"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.operations.name]
  conditions {
    display_name = "Uma ou mais falhas em 5 minutos"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.failed_runs.name}\" AND resource.type=\"cloud_run_job\""
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
  documentation {
    content = "Consultar run_id e tentativa no log. Não liberar proposta sem estado COMPLETED e invariantes aprovadas. Seguir docs/OPERACAO_ENTERPRISE.md."
  }
  depends_on = [google_project_service.apis]
}
