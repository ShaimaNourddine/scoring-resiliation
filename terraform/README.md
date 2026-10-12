# Terraform — Architecture cible AWS

## Structure

```
terraform/
├── main.tf                     # Point d'entrée, appel des modules
├── variables.tf                # Variables globales
├── outputs.tf                  # Valeurs exportées
└── modules/
    ├── vpc/                    # VPC, subnets, IGW, NAT Gateway
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── ecr/                    # Registres Docker (API + Frontend)
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── eks/                    # Cluster Kubernetes + node group
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── secrets/                # AWS Secrets Manager
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

## Architecture provisionnée

```
Internet
    │
    ▼
[AWS ALB] ── port 80/443
    │
    ├── / ──────────────► [scoring-frontend pods] (nginx, 2 replicas)
    └── /api, /docs ────► [scoring-api pods]      (FastAPI, 2-5 replicas)
                              │
                              ├── [AWS Secrets Manager] (JWT, Oracle creds)
                              ├── [Amazon ECR]          (images Docker)
                              └── [Oracle DB] ◄─── réseau privé entreprise
                                  (172.25.72.29 via VPN ou Direct Connect)

Infrastructure :
  VPC 10.0.0.0/16
  ├── Subnets publics  (ALB, NAT Gateway)
  └── Subnets privés   (nœuds EKS, pods)
```

## Prérequis

```bash
# Installer Terraform >= 1.6
# https://developer.hashicorp.com/terraform/install

# Configurer AWS CLI
aws configure

# Vérifier l'accès
aws sts get-caller-identity
```

## Commandes

```bash
cd terraform

# Initialiser les providers
terraform init

# Valider la syntaxe (sans accès AWS)
terraform validate

# Planifier (affiche ce qui sera créé)
terraform plan -out=terraform.tfplan

# Appliquer (crée l'infrastructure réelle)
terraform apply terraform.tfplan

# Configurer kubectl
aws eks update-kubeconfig --region eu-west-3 --name scoring-resiliation-production

# Détruire l'infrastructure (attention !)
terraform destroy
```

## Coûts estimés (eu-west-3, Paris)

| Ressource              | Type         | Coût/mois estimé |
|------------------------|--------------|------------------|
| EKS Control Plane      | Fixe         | ~73 €            |
| EC2 nœuds (2× t3.med) | À l'usage    | ~60 €            |
| NAT Gateway            | À l'usage    | ~35 €            |
| ECR (2 dépôts)         | Stockage     | < 5 €            |
| ALB                    | À l'usage    | ~20 €            |
| **Total estimé**       |              | **~193 €/mois**  |

> Note : la connexion Oracle depuis AWS nécessite un AWS Site-to-Site VPN
> ou AWS Direct Connect vers le réseau de l'entreprise (non inclus ici).
