terraform {
  required_version = ">= 1.13, < 2.0"
  required_providers {
    google      = { source = "hashicorp/google", version = "~> 7.0" }
    google-beta = { source = "hashicorp/google-beta", version = "~> 7.0" }
  }
  # Estado remoto: terraform init -backend-config=backend.hcl
  # Criar o bucket de estado em um projeto de bootstrap antes de habilitar este bloco.
  # backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
