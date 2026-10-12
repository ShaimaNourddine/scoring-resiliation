"""
Module d'authentification — Scoring Résiliation
==================================================

Fournit :
- Hashing / vérification de mot de passe (bcrypt)
- Génération / validation de JWT (JSON Web Token)
- Accès aux utilisateurs (table Oracle SCORING_USERS)
- Dépendances FastAPI réutilisables : get_current_user, require_admin

Sécurité :
- Les mots de passe ne sont JAMAIS stockés ni journalisés en clair.
- La clé secrète JWT (SECRET_KEY) DOIT être fournie via la variable
  d'environnement SCORING_JWT_SECRET en dehors du poste de développement
  (aucune valeur par défaut utilisable en production — cf. avertissement
  au chargement du module).
- Les tokens expirent après ACCESS_TOKEN_EXPIRE_MINUTES (8h par défaut).

Prérequis:
    pip install bcrypt python-jose[cryptography] fastapi
"""

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from oracle_connector import get_connection

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 8 * 60  # 8 heures

SECRET_KEY = os.environ.get("SCORING_JWT_SECRET")
if not SECRET_KEY:
    # Fallback UNIQUEMENT pour le développement local. En l'absence de la
    # variable d'environnement, une clé aléatoire est générée à chaque
    # démarrage : tous les tokens émis avant un redémarrage du serveur
    # deviennent invalides. Ne jamais déployer sans SCORING_JWT_SECRET
    # défini explicitement (valeur fixe, secrète, longue — ex: 64 caractères
    # aléatoires générés une fois avec `python -c "import secrets;
    # print(secrets.token_hex(32))"` et conservée en dehors du code source).
    SECRET_KEY = secrets.token_hex(32)
    logger.warning(
        "SCORING_JWT_SECRET non défini : clé JWT générée aléatoirement pour "
        "cette exécution (tokens invalidés au redémarrage). "
        "À définir explicitement en production."
    )

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# ============================================================================
# MODÈLES PYDANTIC
# ============================================================================
class UserOut(BaseModel):
    """Représentation d'un utilisateur exposée par l'API (jamais le hash)."""
    user_id: int
    email: str
    nom: str
    role: str
    actif: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    email: str
    password: str
    nom: str
    role: str  # "ADMIN" ou "GESTIONNAIRE"


class UserUpdate(BaseModel):
    """Tous les champs sont optionnels : seuls ceux fournis sont modifiés."""
    nom: Optional[str] = None
    role: Optional[str] = None
    actif: Optional[bool] = None
    password: Optional[str] = None


# ============================================================================
# HASHING DE MOT DE PASSE
# ============================================================================
def hash_password(password: str) -> str:
    """Hash un mot de passe en clair avec bcrypt.

    Raises:
        ValueError: si le mot de passe dépasse 72 octets (limite bcrypt).
    """
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Le mot de passe ne doit pas dépasser 72 octets.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Vérifie qu'un mot de passe en clair correspond au hash stocké."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, AttributeError):
        # Hash malformé ou absent : accès refusé, jamais d'exception qui
        # remonterait un détail exploitable côté client.
        return False


# ============================================================================
# JWT
# ============================================================================
def create_access_token(user_id: int, email: str, role: str) -> str:
    """Génère un JWT signé contenant l'identité et le rôle de l'utilisateur."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Décode et valide un JWT. Lève JWTError si invalide/expiré."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ============================================================================
# ACCÈS AUX UTILISATEURS (Oracle)
# ============================================================================
def get_user_by_email(email: str) -> Optional[dict]:
    """Récupère un utilisateur par email (colonnes en minuscules).

    Returns:
        Dict avec user_id, email, password_hash, nom, role, actif, ou None.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT USER_ID, EMAIL, PASSWORD_HASH, NOM, ROLE, ACTIF
                FROM SCORING_USERS
                WHERE LOWER(EMAIL) = LOWER(:email)
                """,
                {"email": email},
            )
            row = cursor.fetchone()
            cursor.close()
            if row is None:
                return None
            return {
                "user_id": row[0],
                "email": row[1],
                "password_hash": row[2],
                "nom": row[3],
                "role": row[4],
                "actif": bool(row[5]),
            }
    except Exception as e:
        logger.error(f"Erreur récupération utilisateur par email: {e}")
        raise


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Récupère un utilisateur par son identifiant."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT USER_ID, EMAIL, PASSWORD_HASH, NOM, ROLE, ACTIF
                FROM SCORING_USERS
                WHERE USER_ID = :user_id
                """,
                {"user_id": user_id},
            )
            row = cursor.fetchone()
            cursor.close()
            if row is None:
                return None
            return {
                "user_id": row[0],
                "email": row[1],
                "password_hash": row[2],
                "nom": row[3],
                "role": row[4],
                "actif": bool(row[5]),
            }
    except Exception as e:
        logger.error(f"Erreur récupération utilisateur par id: {e}")
        raise


def update_last_login(user_id: int) -> None:
    """Met à jour la date de dernière connexion (best-effort, non bloquant)."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE SCORING_USERS SET DERNIERE_CONNEXION = SYSTIMESTAMP WHERE USER_ID = :user_id",
                {"user_id": user_id},
            )
            conn.commit()
            cursor.close()
    except Exception as e:
        # Non bloquant : une erreur ici ne doit jamais empêcher la connexion.
        logger.warning(f"Impossible de mettre à jour DERNIERE_CONNEXION: {e}")


# ============================================================================
# CRUD UTILISATEURS (réservé aux admins, cf. endpoints /admin/users)
# ============================================================================
VALID_ROLES = ("ADMIN", "GESTIONNAIRE")


def _row_to_user_dict(row) -> dict:
    return {
        "user_id": row[0],
        "email": row[1],
        "nom": row[2],
        "role": row[3],
        "actif": bool(row[4]),
    }


def list_users() -> list:
    """Liste tous les utilisateurs (sans le hash de mot de passe)."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT USER_ID, EMAIL, NOM, ROLE, ACTIF
                FROM SCORING_USERS
                ORDER BY USER_ID
                """
            )
            rows = cursor.fetchall()
            cursor.close()
            return [_row_to_user_dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Erreur listage utilisateurs: {e}")
        raise


def create_user(email: str, password: str, nom: str, role: str) -> dict:
    """Crée un nouvel utilisateur.

    Raises:
        ValueError: rôle invalide, mot de passe trop long, ou email déjà utilisé.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Rôle invalide: {role}. Attendu: {VALID_ROLES}")

    password_hash = hash_password(password)  # lève ValueError si > 72 octets

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO SCORING_USERS (EMAIL, PASSWORD_HASH, NOM, ROLE, ACTIF)
                VALUES (:email, :password_hash, :nom, :role, 1)
                """,
                {"email": email, "password_hash": password_hash, "nom": nom, "role": role},
            )
            conn.commit()

            cursor.execute(
                "SELECT USER_ID, EMAIL, NOM, ROLE, ACTIF FROM SCORING_USERS WHERE LOWER(EMAIL) = LOWER(:email)",
                {"email": email},
            )
            row = cursor.fetchone()
            cursor.close()
            return _row_to_user_dict(row)
    except Exception as e:
        # ORA-00001 = violation de contrainte unique (email déjà utilisé)
        if "ORA-00001" in str(e):
            raise ValueError(f"L'email '{email}' est déjà utilisé.")
        logger.error(f"Erreur création utilisateur: {e}")
        raise


def update_user(
    user_id: int,
    nom: Optional[str] = None,
    role: Optional[str] = None,
    actif: Optional[bool] = None,
    password: Optional[str] = None,
) -> Optional[dict]:
    """Met à jour un utilisateur existant (champs fournis uniquement).

    Returns:
        Le dict utilisateur mis à jour, ou None si l'utilisateur n'existe pas.

    Raises:
        ValueError: rôle invalide ou mot de passe trop long.
    """
    if role is not None and role not in VALID_ROLES:
        raise ValueError(f"Rôle invalide: {role}. Attendu: {VALID_ROLES}")

    set_clauses = ["DATE_MODIFICATION = SYSTIMESTAMP"]
    params = {"user_id": user_id}

    if nom is not None:
        set_clauses.append("NOM = :nom")
        params["nom"] = nom
    if role is not None:
        set_clauses.append("ROLE = :role")
        params["role"] = role
    if actif is not None:
        set_clauses.append("ACTIF = :actif")
        params["actif"] = 1 if actif else 0
    if password is not None:
        set_clauses.append("PASSWORD_HASH = :password_hash")
        params["password_hash"] = hash_password(password)  # lève ValueError si > 72 octets

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE SCORING_USERS SET {', '.join(set_clauses)} WHERE USER_ID = :user_id",
                params,
            )
            if cursor.rowcount == 0:
                conn.rollback()
                cursor.close()
                return None
            conn.commit()

            cursor.execute(
                "SELECT USER_ID, EMAIL, NOM, ROLE, ACTIF FROM SCORING_USERS WHERE USER_ID = :user_id",
                {"user_id": user_id},
            )
            row = cursor.fetchone()
            cursor.close()
            return _row_to_user_dict(row) if row else None
    except Exception as e:
        logger.error(f"Erreur mise à jour utilisateur {user_id}: {e}")
        raise


def deactivate_user(user_id: int) -> bool:
    """Désactive un utilisateur (soft delete — jamais de suppression physique,
    pour conserver la traçabilité des actions passées).

    Returns:
        True si l'utilisateur a été désactivé, False s'il n'existait pas.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE SCORING_USERS
                SET ACTIF = 0, DATE_MODIFICATION = SYSTIMESTAMP
                WHERE USER_ID = :user_id
                """,
                {"user_id": user_id},
            )
            updated = cursor.rowcount > 0
            conn.commit()
            cursor.close()
            return updated
    except Exception as e:
        logger.error(f"Erreur désactivation utilisateur {user_id}: {e}")
        raise


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authentifie un utilisateur par email/mot de passe.

    Returns:
        Le dict utilisateur si les identifiants sont valides ET le compte
        est actif, sinon None (ne distingue jamais "email inconnu" de
        "mot de passe incorrect" pour éviter l'énumération de comptes).
    """
    user = get_user_by_email(email)
    if user is None:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    if not user["actif"]:
        return None
    return user


# ============================================================================
# DÉPENDANCES FASTAPI
# ============================================================================
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserOut:
    """Dépendance FastAPI : extrait et valide l'utilisateur courant depuis le JWT.

    Raises:
        HTTPException 401: token invalide, expiré, ou utilisateur introuvable/inactif.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants invalides ou expirés",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    user = get_user_by_id(user_id)
    if user is None or not user["actif"]:
        raise credentials_exception

    return UserOut(
        user_id=user["user_id"],
        email=user["email"],
        nom=user["nom"],
        role=user["role"],
        actif=user["actif"],
    )


async def require_admin(current_user: UserOut = Depends(get_current_user)) -> UserOut:
    """Dépendance FastAPI : exige que l'utilisateur courant soit ADMIN.

    Raises:
        HTTPException 403: si le rôle n'est pas ADMIN.
    """
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user
