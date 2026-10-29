module "platform" {
  source            = "./modules/platform"
  project_id        = var.project_id
  region            = var.region
  environment       = var.environment
  image             = var.image
  identities        = var.identities
  github_repository = var.github_repository
  github_owner_id   = var.github_owner_id
  retention_days    = var.retention_days
  alert_email       = var.alert_email
}
