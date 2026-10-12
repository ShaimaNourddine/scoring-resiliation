# ============================================================
# Outputs Terraform — valeurs exportées après apply
# ============================================================

output "vpc_id" {
  description = "ID du VPC créé"
  value       = module.vpc.vpc_id
}

output "eks_cluster_name" {
  description = "Nom du cluster EKS"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "Endpoint de l'API Kubernetes"
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "ecr_api_url" {
  description = "URL du dépôt ECR pour l'image API"
  value       = module.ecr.api_repository_url
}

output "ecr_frontend_url" {
  description = "URL du dépôt ECR pour l'image Frontend"
  value       = module.ecr.frontend_repository_url
}

output "kubeconfig_command" {
  description = "Commande pour configurer kubectl"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}
