terraform {
  required_providers {
    google = { source = "hashicorp/google" }
  }
}

data "google_project" "current" { project_id = var.project_id }
locals {
  name = "otm-guard-${var.environment}"
  services = toset([
    "run.googleapis.com", "artifactregistry.googleapis.com", "storage.googleapis.com",
    "sqladmin.googleapis.com", "iap.googleapis.com", "iam.googleapis.com",
    "iamcredentials.googleapis.com", "sts.googleapis.com", "monitoring.googleapis.com",
    "logging.googleapis.com", "secretmanager.googleapis.com", "containeranalysis.googleapis.com",
    "containerscanning.googleapis.com",
  ])
  common_env = {
    OTM_ENV              = "gcp"
    GOOGLE_CLOUD_PROJECT = var.project_id
    OTM_REGION           = var.region
    OTM_BUCKET           = google_storage_bucket.artifacts.name
    OTM_JOB_NAME         = local.name
    OTM_SQL_INSTANCE     = google_sql_database_instance.platform.connection_name
    OTM_SQL_DATABASE     = google_sql_database.app.name
    OTM_IAP_AUDIENCE     = "/projects/${data.google_project.current.number}/locations/${var.region}/services/${local.name}"
    OTM_PUBLIC_ORIGIN    = "https://${local.name}-${data.google_project.current.number}.${var.region}.run.app"
    OTM_IDENTITIES_JSON  = jsonencode(var.identities)
    OTM_BIND             = "0.0.0.0"
  }
}
resource "google_project_service" "apis" {
  for_each           = local.services
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
resource "google_service_account" "api" {
  account_id   = "${local.name}-api"
  display_name = "OTM Guard API ${var.environment}"
}
resource "google_service_account" "worker" {
  account_id   = "${local.name}-worker"
  display_name = "OTM Guard worker ${var.environment}"
}
resource "google_service_account" "deploy" {
  account_id   = "${local.name}-deploy"
  display_name = "OTM Guard CI ${var.environment}"
}
resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = local.name
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}
resource "google_storage_bucket" "artifacts" {
  name                        = "${var.project_id}-${local.name}-artifacts"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  versioning { enabled = true }
  lifecycle_rule {
    condition { age = var.retention_days }
    action { type = "Delete" }
  }
  soft_delete_policy { retention_duration_seconds = 604800 }
  depends_on = [google_project_service.apis]
}
resource "google_storage_bucket_iam_member" "object_access" {
  for_each = {
    api_create    = { role = "roles/storage.objectCreator", sa = google_service_account.api.email }
    api_read      = { role = "roles/storage.objectViewer", sa = google_service_account.api.email }
    worker_create = { role = "roles/storage.objectCreator", sa = google_service_account.worker.email }
    worker_read   = { role = "roles/storage.objectViewer", sa = google_service_account.worker.email }
  }
  bucket = google_storage_bucket.artifacts.name
  role   = each.value.role
  member = "serviceAccount:${each.value.sa}"
}
resource "google_sql_database_instance" "platform" {
  name                = local.name
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = true
  settings {
    tier                  = "db-custom-1-3840"
    availability_type     = var.environment == "production" ? "REGIONAL" : "ZONAL"
    disk_size             = 20
    disk_autoresize       = true
    disk_autoresize_limit = 100
    connector_enforcement = "REQUIRED"
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }
    maintenance_window {
      day  = 7
      hour = 4
    }
  }
  depends_on = [google_project_service.apis]
}
resource "google_sql_database" "app" {
  name     = "otm_guard"
  instance = google_sql_database_instance.platform.name
}
resource "google_sql_user" "iam" {
  for_each = { api = google_service_account.api.email, worker = google_service_account.worker.email }
  name     = trimsuffix(each.value, ".gserviceaccount.com")
  instance = google_sql_database_instance.platform.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}
resource "google_project_iam_member" "runtime_roles" {
  for_each = {
    api_sql         = { role = "roles/cloudsql.client", sa = google_service_account.api.email }
    api_sql_login   = { role = "roles/cloudsql.instanceUser", sa = google_service_account.api.email }
    worker_sql      = { role = "roles/cloudsql.client", sa = google_service_account.worker.email }
    worker_sql_user = { role = "roles/cloudsql.instanceUser", sa = google_service_account.worker.email }
    api_log         = { role = "roles/logging.logWriter", sa = google_service_account.api.email }
    worker_log      = { role = "roles/logging.logWriter", sa = google_service_account.worker.email }
  }
  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${each.value.sa}"
}
resource "google_cloud_run_v2_job" "worker" {
  name     = local.name
  location = var.region
  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.worker.email
      timeout         = "1800s"
      max_retries     = 0 # Retry de negócio usa estado/lease e teto de três tentativas.
      containers {
        image   = var.image
        command = ["python"]
        args    = ["-m", "platform_api.worker"]
        resources { limits = { cpu = "2", memory = "4Gi" } }
        dynamic "env" {
          for_each = merge(local.common_env, { OTM_SQL_USER = google_sql_user.iam["worker"].name })
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }
  depends_on = [google_project_iam_member.runtime_roles]
}
resource "google_cloud_run_v2_job_iam_member" "api_execute" {
  name     = google_cloud_run_v2_job.worker.name
  location = var.region
  role     = "roles/run.jobsExecutorWithOverrides"
  member   = "serviceAccount:${google_service_account.api.email}"
}
resource "google_cloud_run_v2_service" "app" {
  name                = local.name
  location            = var.region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"
  iap_enabled         = true
  template {
    service_account                  = google_service_account.api.email
    max_instance_request_concurrency = 1
    timeout                          = "300s"
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = var.image
      resources {
        limits   = { cpu = "2", memory = "4Gi" }
        cpu_idle = true
      }
      ports { container_port = 8080 }
      startup_probe {
        initial_delay_seconds = 2
        period_seconds        = 10
        failure_threshold     = 12
        http_get { path = "/healthz" }
      }
      liveness_probe {
        period_seconds = 30
        http_get { path = "/healthz" }
      }
      dynamic "env" {
        for_each = merge(local.common_env, { OTM_SQL_USER = google_sql_user.iam["api"].name })
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  depends_on = [google_cloud_run_v2_job.worker, google_project_iam_member.runtime_roles]
}
resource "google_project_service_identity" "iap" {
  provider   = google
  project    = var.project_id
  service    = "iap.googleapis.com"
  depends_on = [google_project_service.apis]
}
resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  name     = google_cloud_run_v2_service.app.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_project_service_identity.iap.email}"
}
resource "google_iap_web_cloud_run_service_iam_member" "users" {
  for_each               = var.identities
  project                = var.project_id
  location               = var.region
  cloud_run_service_name = google_cloud_run_v2_service.app.name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = "user:${each.key}"
}
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "${local.name}-github"
  display_name              = "OTM Guard GitHub ${var.environment}"
}
resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository"          = "assertion.repository"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
  }
  attribute_condition = "assertion.repository_owner_id == '${var.github_owner_id}' && assertion.repository == '${var.github_repository}' && assertion.sub == 'repo:${var.github_repository}:environment:${var.environment}'"
  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}
resource "google_service_account_iam_member" "federation" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}
resource "google_artifact_registry_repository_iam_member" "ci_push" {
  location   = var.region
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deploy.email}"
}
resource "google_cloud_run_v2_service_iam_member" "ci_deploy" {
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.deploy.email}"
}
resource "google_service_account_iam_member" "ci_act_as" {
  for_each           = { api = google_service_account.api.name, worker = google_service_account.worker.name }
  service_account_id = each.value
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}
