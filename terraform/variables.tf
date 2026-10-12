# ============================================================
# Variables Terraform — Architecture cible AWS
# ============================================================

variable "aws_region" {
  description = "Région AWS cible"
  type        = string
  default     = "eu-west-3"    # Paris
}

variable "project_name" {
  description = "Nom du projet (utilisé dans tous les noms de ressources)"
  type        = string
  default     = "scoring-resiliation"
}

variable "environment" {
  description = "Environnement de déploiement"
  type        = string
  default     = "production"
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "L'environnement doit être : development, staging ou production."
  }
}

# --- VPC ---
variable "vpc_cidr" {
  description = "Bloc CIDR du VPC principal"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Zones de disponibilité à utiliser (minimum 2 pour la HA)"
  type        = list(string)
  default     = ["eu-west-3a", "eu-west-3b", "eu-west-3c"]
}

# --- EKS ---
variable "eks_cluster_version" {
  description = "Version de Kubernetes sur EKS"
  type        = string
  default     = "1.29"
}

variable "eks_node_instance_type" {
  description = "Type d'instance EC2 pour les nœuds EKS"
  type        = string
  default     = "t3.medium"    # 2 vCPU, 4 GB — suffisant pour l'API FastAPI + XGBoost
}

variable "eks_node_min_size" {
  description = "Nombre minimum de nœuds (autoscaling)"
  type        = number
  default     = 2
}

variable "eks_node_max_size" {
  description = "Nombre maximum de nœuds (autoscaling)"
  type        = number
  default     = 5
}

variable "eks_node_desired_size" {
  description = "Nombre initial de nœuds"
  type        = number
  default     = 2
}
