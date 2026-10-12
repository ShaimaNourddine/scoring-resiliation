# ============================================================
# Module Secrets Manager — Secrets applicatifs
# Les valeurs réelles sont injectées hors Terraform
# (console AWS ou CLI) pour ne jamais apparaître dans le state
# ============================================================

resource "aws_secretsmanager_secret" "jwt_secret" {
  name                    = "/${var.project_name}/${var.environment}/jwt-secret"
  description             = "Clé secrète JWT pour l'API de scoring résiliation"
  recovery_window_in_days = 7

  tags = {
    Name = "${var.project_name}-${var.environment}-jwt-secret"
  }
}

resource "aws_secretsmanager_secret" "oracle_credentials" {
  name                    = "/${var.project_name}/${var.environment}/oracle-credentials"
  description             = "Identifiants Oracle pour l'API de scoring résiliation"
  recovery_window_in_days = 7

  tags = {
    Name = "${var.project_name}-${var.environment}-oracle-creds"
  }
}

resource "aws_secretsmanager_secret" "admin_password" {
  name                    = "/${var.project_name}/${var.environment}/admin-password"
  description             = "Mot de passe administrateur de l'application de scoring"
  recovery_window_in_days = 7

  tags = {
    Name = "${var.project_name}-${var.environment}-admin-password"
  }
}

# ---- Injecter les valeurs avec la CLI (hors Terraform) ----
# aws secretsmanager put-secret-value \
#   --secret-id /<project>/<env>/jwt-secret \
#   --secret-string '{"SCORING_JWT_SECRET":"votre-cle-secrete"}'
#
# aws secretsmanager put-secret-value \
#   --secret-id /<project>/<env>/oracle-credentials \
#   --secret-string '{"ORACLE_USER":"user","ORACLE_PASSWORD":"pass","ORACLE_DSN":"host:1521/SID"}'
