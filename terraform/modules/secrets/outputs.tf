output "jwt_secret_arn"          { value = aws_secretsmanager_secret.jwt_secret.arn }
output "oracle_credentials_arn"  { value = aws_secretsmanager_secret.oracle_credentials.arn }
output "admin_password_arn"      { value = aws_secretsmanager_secret.admin_password.arn }
