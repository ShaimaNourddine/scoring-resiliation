# Manifests Kubernetes — Scoring Résiliation

## Structure

```
k8s/
├── namespace.yaml          # Namespace dédié "scoring"
├── configmap.yaml          # Variables non sensibles
├── secret.yaml             # Variables sensibles (à surcharger en prod)
├── pvc.yaml                # Volume pour le modèle ML
├── deployment-api.yaml     # Deployment API FastAPI (2 replicas)
├── deployment-frontend.yaml # Deployment Frontend Angular (2 replicas)
├── service.yaml            # Services ClusterIP (api + frontend)
├── ingress.yaml            # Ingress nginx (local) / ALB (AWS EKS)
└── hpa.yaml                # Autoscaling CPU/mémoire
```

## Déploiement local avec kind

### 1. Créer le cluster kind
```bash
kind create cluster --name scoring
```

### 2. Charger les images locales dans kind
```bash
# Build des images
docker build -f Dockerfile.api -t scoring-api:latest .
docker build -f Dockerfile.frontend -t scoring-frontend:latest .

# Charger dans kind
kind load docker-image scoring-api:latest --name scoring
kind load docker-image scoring-frontend:latest --name scoring
```

### 3. Installer le contrôleur nginx Ingress
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=90s
```

### 4. Appliquer les manifests
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment-api.yaml
kubectl apply -f k8s/deployment-frontend.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml
```

### 5. Vérifier l'état
```bash
kubectl get all -n scoring
kubectl get ingress -n scoring
kubectl logs -n scoring deployment/scoring-api
```

### 6. Accéder à l'application
Ajouter dans `C:\Windows\System32\drivers\etc\hosts` :
```
127.0.0.1  scoring.masteri.local
```
Puis ouvrir : http://scoring.masteri.local

## Déploiement AWS EKS (architecture cible)

1. Remplacer les images `scoring-api:latest` → `<account>.dkr.ecr.<region>.amazonaws.com/scoring-api:<tag>`
2. Décommenter les annotations ALB dans `ingress.yaml`
3. Remplacer `storageClassName: standard` → `gp2` dans `pvc.yaml`
4. Injecter les secrets via AWS Secrets Manager + External Secrets Operator
