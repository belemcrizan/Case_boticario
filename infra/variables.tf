variable "project_id" {
  type        = string
  description = "Projeto GCP autorizado. Usar projetos separados por ambiente."
}
variable "region" {
  type    = string
  default = "southamerica-east1"
}
variable "environment" {
  type    = string
  default = "dev"
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Ambiente deve ser dev, staging ou production."
  }
}
variable "image" {
  type        = string
  description = "Imagem por digest SHA-256 previamente construída e verificada."
  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.image))
    error_message = "Informe imagem imutável por digest."
  }
}
variable "identities" {
  type        = map(string)
  description = "Email autenticado pelo IAP => papel na aplicação."
  validation {
    condition     = length(var.identities) > 0 && alltrue([for role in values(var.identities) : contains(["operator", "viewer", "auditor", "admin"], role)])
    error_message = "Identidades explícitas e papéis válidos são obrigatórios."
  }
}
variable "github_repository" {
  type    = string
  default = "belemcrizan/Case_boticario"
}
variable "github_owner_id" {
  type    = string
  default = "102571985"
}
variable "retention_days" {
  type    = number
  default = 30
  validation {
    condition     = var.retention_days >= 7 && var.retention_days <= 365
    error_message = "Retenção deve estar entre 7 e 365 dias."
  }
}
variable "alert_email" {
  type        = string
  description = "Destinatário operacional autorizado para alertas do projeto."
}
