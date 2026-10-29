output "application_url" { value = google_cloud_run_v2_service.app.uri }
output "artifact_repository" { value = google_artifact_registry_repository.images.id }
output "workload_identity_provider" { value = google_iam_workload_identity_pool_provider.github.name }
output "deploy_service_account" { value = google_service_account.deploy.email }
output "sql_connection_name" { value = google_sql_database_instance.platform.connection_name }
output "job_name" { value = google_cloud_run_v2_job.worker.name }
