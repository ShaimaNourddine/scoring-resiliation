# ============================================================
# Terraform — Architecture cible AWS
# Scoring Résiliation — PFE Masteri
#
# Infrastructure provisionnée :
#   - VPC avec subnets publics/privés
#   - Amazon ECR (registre d'images Docker)
#   - Amazon EKS (cluster Kubernetes)
#   - AWS ALB (Application Load Balancer)
#   - AWS Secrets Manager (secrets applicatifs)
#
# Usage :
#   terraform init
#   terraform validate
#   terraform plan -out=terraform.tfplan
#   terraform apply terraform.tfplan
# ============================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
  }

  # Backend S3 pour le state Terraform (à activer en prod)
  # backend "s3" {
  #   bucket         = "masteri-terraform-state"
  #   key            = "scoring/terraform.tfstate"
  #   region         = "eu-west-3"
  #   encrypt        = true
  #   dynamodb_table = "masteri-terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "scoring-resiliation"
      Environment = var.environment
      ManagedBy   = "terraform"
      Team        = "masteri-pfe"
    }
  }
}

# ============================================================
# MODULE VPC
# ============================================================
module "vpc" {
  source = "./modules/vpc"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
}

# ============================================================
# MODULE ECR (registre images Docker)
# ============================================================
module "ecr" {
  source = "./modules/ecr"

  project_name = var.project_name
  environment  = var.environment
}

# ============================================================
# MODULE EKS (cluster Kubernetes)
# ============================================================
module "eks" {
  source = "./modules/eks"

  project_name     = var.project_name
  environment      = var.environment
  vpc_id           = module.vpc.vpc_id
  private_subnets  = module.vpc.private_subnet_ids
  cluster_version  = var.eks_cluster_version
  node_instance_type = var.eks_node_instance_type
  node_min_size    = var.eks_node_min_size
  node_max_size    = var.eks_node_max_size
  node_desired_size = var.eks_node_desired_size
}

# ============================================================
# MODULE SECRETS MANAGER
# ============================================================
module "secrets" {
  source = "./modules/secrets"

  project_name = var.project_name
  environment  = var.environment
}
