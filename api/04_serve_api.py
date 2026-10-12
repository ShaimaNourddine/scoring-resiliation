"""
API de Scoring Résiliation - FastAPI + MLflow
==============================================
Expose le modèle de scoring comme une API REST.

Prérequis:
    pip install fastapi uvicorn mlflow pandas oracledb

Lancement:
    uvicorn 04_serve_api:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
    GET  /health         → Vérification de santé
    POST /predict        → Score un seul contrat (features déjà encodées)
    POST /predict_batch  → Score tout le portefeuille (vectorisé)
    GET  /dashboard/stats → Statistiques agrégées + top contrats scorés
    GET  /portefeuille/moyennes → Moyennes du portefeuille (cache 24h)
    GET  /scoring/contrat/{id}/explication → Facteurs explicatifs d'un contrat scoré
    GET  /scoring/contrat/{id} → Score un contrat depuis Oracle (données réelles)
"""

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Dict, List, Optional
import pandas as pd
import mlflow.pyfunc
import numpy as np
from datetime import datetime, timedelta
import logging

from shap_calculator import SHAPCalculator
from cache_moyennes import CacheMoyennes
from realtime_preprocessor import RealtimePreprocessor
from oracle_connector import (
    get_contrat_brut,
    get_contrat_preprocessed,
    get_all_contrats_preprocessed,
    extraire_features,
    test_connection,
)
import auth
from auth import UserOut, TokenResponse, get_current_user, require_admin

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================
MODEL_NAME = "scoring-resiliation"
MODEL_STAGE = "Production"

# Pointer MLflow vers le registry local (SQLite) créé par le notebook
# d'entraînement. Sans cette ligne, mlflow cherche sur un serveur distant
# et échoue avec "Registered Model not found", forçant le fallback pickle.
import os as _os
_mlflow_db = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "mlflow.db")
if _os.path.exists(_mlflow_db):
    mlflow.set_tracking_uri(f"sqlite:///{_mlflow_db}")
    print(f"MLflow tracking URI : sqlite:///{_mlflow_db}")

app = FastAPI(
    title="API Scoring Résiliation Assurance-Vie",
    description="Prédit le risque de résiliation anticipée des contrats d'assurance-vie",
    version="1.0.0"
)

# CORS : nécessaire pour les appels cross-origin depuis l'app Angular
# (localhost:4200 en développement). À restreindre à l'origine réelle du
# frontend déployé en production plutôt que d'élargir davantage.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chargement du modèle au démarrage
print(f"Chargement du modèle : {MODEL_NAME}/{MODEL_STAGE}...")
try:
    model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{MODEL_STAGE}")
    print("✓ Modèle chargé avec succès")
except Exception as e:
    print(f"⚠️  Impossible de charger depuis MLflow Registry: {e}")
    print("   Tentative de chargement depuis fichier pickle...")
    import pickle
    import glob
    pkl_files = glob.glob("best_model_*.pkl")
    if pkl_files:
        with open(pkl_files[0], 'rb') as f:
            model = pickle.load(f)
        print(f"✓ Modèle chargé depuis {pkl_files[0]}")
    else:
        model = None
        print("❌ Aucun modèle disponible")

# ============================================================================
# INITIALISATION CACHE
# ============================================================================
# Cache des moyennes du portefeuille (TTL 24h)
cache_moyennes = CacheMoyennes()

# ============================================================================
# INITIALISATION PREPROCESSOR TEMPS RÉEL
# ============================================================================
# Charge les artefacts de preprocessing pour scorer un contrat depuis Oracle
realtime_preprocessor: Optional[RealtimePreprocessor] = None
oracle_available = False

try:
    realtime_preprocessor = RealtimePreprocessor('artifacts')
    print("✓ RealtimePreprocessor initialisé (artefacts chargés)")
except FileNotFoundError as e:
    print(f"⚠️  RealtimePreprocessor non disponible: {e}")
    print("   L'endpoint GET /scoring/contrat/{{id}} ne fonctionnera pas.")
    print("   Exécutez: python save_preprocessing_artifacts.py")
except Exception as e:
    print(f"⚠️  Erreur initialisation RealtimePreprocessor: {e}")

# Tester la connexion Oracle
try:
    oracle_info = test_connection()
    if oracle_info['status'] == 'connected':
        oracle_available = True
        print(f"✓ Connexion Oracle OK")
    else:
        print(f"⚠️  Oracle non disponible: {oracle_info.get('error', 'inconnu')}")
        print("   L'endpoint GET /scoring/contrat/{{id}} utilisera le fallback PREPROCESSED.")
except Exception as e:
    print(f"⚠️  Oracle non accessible: {e}")

# Cache en mémoire des contrats récemment scorés (pour l'endpoint /explication)
# En production, cela serait remplacé par une lookup en base de données.
_scored_contrats: Dict[str, pd.DataFrame] = {}
_MAX_SCORED_CACHE = 1500  # Nombre max de contrats gardés en cache (couvre l'échantillon Dashboard de 1000)


def _cache_contrat(contrat_id: str, features_df: pd.DataFrame) -> None:
    """Met en cache les features d'un contrat scoré (FIFO, taille bornée).

    Utilisé par tous les chemins de scoring (predict_single,
    score_contrat, predict_batch, dashboard_stats) pour que l'endpoint
    /scoring/contrat/{id}/explication puisse toujours retrouver un
    contrat récemment scoré, quel que soit l'endpoint qui l'a scoré.
    """
    if len(_scored_contrats) >= _MAX_SCORED_CACHE:
        oldest_key = next(iter(_scored_contrats))
        del _scored_contrats[oldest_key]
    _scored_contrats[contrat_id] = features_df.copy()


# ============================================================================
# MODÈLES DE DONNÉES (Pydantic)
# ============================================================================
class ContratInput(BaseModel):
    """Données d'un contrat pour le scoring"""
    contrat_id: str
    # Variables produit
    produit: Optional[float] = 0
    tarif: Optional[float] = 0
    cadre_fiscal: Optional[float] = 0
    periodicite: Optional[float] = 0
    mode_reglement: Optional[float] = 0
    # Variables temporelles
    duree_annees: Optional[float] = 0
    duree_mois: Optional[float] = 0
    # Variables financières
    versement_initial: Optional[float] = 0
    total_primes: Optional[float] = 0
    total_rachats: Optional[float] = 0
    nb_mouvements: Optional[float] = 0
    nb_mouvements_annules: Optional[float] = 0
    # Variables avenants
    nb_avt_risque_eleve: Optional[float] = 0
    nb_avt_arret_annulation: Optional[float] = 0
    nb_avt_arbitrage: Optional[float] = 0
    nb_avt_versement: Optional[float] = 0
    nb_avt_modif_admin_motif: Optional[float] = 0
    # Flags
    flag_rachat_programme: Optional[float] = 0
    flag_renonciation: Optional[float] = 0
    flag_deces: Optional[float] = 0
    # Variables tiers
    sexe: Optional[float] = 0
    csp: Optional[float] = 0
    situation_famille: Optional[float] = 0
    # Variables dérivées
    age_souscripteur: Optional[float] = 0
    ratio_rachats_primes: Optional[float] = 0

    class Config:
        json_schema_extra = {
            "example": {
                "contrat_id": "CNT000123",
                "total_primes": 50000,
                "total_rachats": 10000,
                "nb_avt_risque_eleve": 2,
                "nb_mouvements": 15,
                "age_souscripteur": 55
            }
        }


class PredictionOutput(BaseModel):
    """Résultat du scoring"""
    contrat_id: str
    score_risque: float
    classe_predite: int
    niveau_risque: str
    timestamp: str





class FacteurExplicatifResponse(BaseModel):
    """Un facteur explicatif dans la réponse API."""
    nom_variable: str
    shap_value: float
    valeur_contrat: float
    moyenne_portefeuille: float


class ExplicationResponse(BaseModel):
    """Réponse de l'endpoint d'explication."""
    contrat_id: str
    facteurs_explicatifs: List[FacteurExplicatifResponse]
    explication_disponible: bool = True
    timestamp: str


class PredictionAvecExplicationOutput(BaseModel):
    """Extension de PredictionOutput avec explicabilité."""
    contrat_id: str
    score_risque: float
    classe_predite: int
    niveau_risque: str
    facteurs_explicatifs: List[FacteurExplicatifResponse] = []
    explication_disponible: bool = True
    timestamp: str


class MoyennesResponse(BaseModel):
    """Réponse de l'endpoint des moyennes."""
    moyennes: Dict[str, float]
    nombre_contrats: int
    date_calcul: str
    cache_valide_jusqu_a: str


# ============================================================================
# INITIALISATION SHAP & CONSTANTES (après définition de ContratInput)
# ============================================================================
# Liste des features réellement attendues par le modèle XGBoost (Option C,
# 32 features). ContratInput ci-dessus est un schéma Pydantic obsolète
# (ancienne version à 25 champs génériques, ex: 'produit', 'tarif') conservé
# uniquement pour la validation du body de /predict ; il ne doit jamais
# servir de source pour la liste de features du modèle ou de SHAPCalculator,
# sous peine de KeyError lors du calcul des facteurs explicatifs.
FEATURE_NAMES = (
    realtime_preprocessor.get_features_list()
    if realtime_preprocessor is not None
    else [f for f in ContratInput.model_fields.keys() if f != 'contrat_id']
)

# TODO: En production, calculer depuis Oracle via cx_Oracle
# Moyennes par défaut pour le mode développement (valeurs typiques de contrats d'assurance-vie)
DEFAULT_MOYENNES: Dict[str, float] = {
    "produit": 2.0,
    "tarif": 1.5,
    "cadre_fiscal": 1.0,
    "periodicite": 2.0,
    "mode_reglement": 1.0,
    "duree_annees": 8.5,
    "duree_mois": 102.0,
    "versement_initial": 25000.0,
    "total_primes": 45000.0,
    "total_rachats": 8000.0,
    "nb_mouvements": 12.0,
    "nb_mouvements_annules": 1.5,
    "nb_avt_risque_eleve": 1.2,
    "nb_avt_arret_annulation": 0.3,
    "nb_avt_arbitrage": 2.1,
    "nb_avt_versement": 3.5,
    "nb_avt_modif_admin_motif": 1.8,
    "flag_rachat_programme": 0.15,
    "flag_renonciation": 0.05,
    "flag_deces": 0.02,
    "sexe": 0.55,
    "csp": 3.0,
    "situation_famille": 2.0,
    "age_souscripteur": 52.0,
    "ratio_rachats_primes": 0.18,
}

# Nombre de contrats utilisés pour le calcul des moyennes (mode dev)
DEFAULT_NOMBRE_CONTRATS = 1500

# Le calculateur SHAP - initialisé si le modèle est disponible
shap_calculator: Optional[SHAPCalculator] = None

if model is not None:
    try:
        shap_calculator = SHAPCalculator(model, FEATURE_NAMES)
        print("✓ SHAPCalculator initialisé avec succès")
    except Exception as e:
        shap_calculator = None
        print(f"⚠️  Impossible d'initialiser le SHAPCalculator: {e}")
        logger.warning(f"SHAPCalculator initialization failed: {e}")


# ============================================================================
# ENDPOINTS
# ============================================================================
@app.get("/health")
def health_check():
    """Vérification de santé de l'API"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "model_name": MODEL_NAME,
        "preprocessor_loaded": realtime_preprocessor is not None,
        "oracle_available": oracle_available,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# ENDPOINTS D'AUTHENTIFICATION
# ============================================================================
@app.post("/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authentifie un utilisateur et retourne un JWT.

    form_data.username porte l'email (convention OAuth2PasswordRequestForm).
    """
    user = auth.authenticate_user(form_data.username, form_data.password)
    if user is None:
        # Message volontairement générique : ne distingue jamais "email
        # inconnu" de "mot de passe incorrect" ni de "compte désactivé"
        # pour éviter l'énumération de comptes.
        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth.create_access_token(
        user_id=user["user_id"], email=user["email"], role=user["role"]
    )
    auth.update_last_login(user["user_id"])

    return TokenResponse(
        access_token=token,
        user=UserOut(
            user_id=user["user_id"],
            email=user["email"],
            nom=user["nom"],
            role=user["role"],
            actif=user["actif"],
        ),
    )


@app.get("/auth/me", response_model=UserOut)
def read_current_user(current_user: UserOut = Depends(get_current_user)):
    """Retourne les informations de l'utilisateur authentifié."""
    return current_user


# ============================================================================
# ENDPOINTS CRUD UTILISATEURS (réservés aux administrateurs)
# ============================================================================
@app.get("/admin/users", response_model=List[UserOut])
def list_users_endpoint(current_user: UserOut = Depends(require_admin)):
    """Liste tous les utilisateurs. Réservé aux administrateurs."""
    users = auth.list_users()
    return [UserOut(**u) for u in users]


@app.post("/admin/users", response_model=UserOut, status_code=201)
def create_user_endpoint(
    user_in: auth.UserCreate, current_user: UserOut = Depends(require_admin)
):
    """Crée un nouvel utilisateur. Réservé aux administrateurs."""
    try:
        created = auth.create_user(
            email=user_in.email,
            password=user_in.password,
            nom=user_in.nom,
            role=user_in.role,
        )
        return UserOut(**created)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/admin/users/{user_id}", response_model=UserOut)
def update_user_endpoint(
    user_id: int,
    user_in: auth.UserUpdate,
    current_user: UserOut = Depends(require_admin),
):
    """Met à jour un utilisateur existant. Réservé aux administrateurs."""
    try:
        updated = auth.update_user(
            user_id=user_id,
            nom=user_in.nom,
            role=user_in.role,
            actif=user_in.actif,
            password=user_in.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if updated is None:
        raise HTTPException(status_code=404, detail=f"Utilisateur {user_id} non trouvé")
    return UserOut(**updated)


@app.delete("/admin/users/{user_id}", status_code=204)
def deactivate_user_endpoint(
    user_id: int, current_user: UserOut = Depends(require_admin)
):
    """Désactive un utilisateur (soft delete). Réservé aux administrateurs.

    Ne supprime jamais physiquement la ligne : conserve la traçabilité.
    """
    if current_user.user_id == user_id:
        raise HTTPException(
            status_code=400, detail="Impossible de désactiver son propre compte."
        )
    deactivated = auth.deactivate_user(user_id)
    if not deactivated:
        raise HTTPException(status_code=404, detail=f"Utilisateur {user_id} non trouvé")


@app.post("/predict", response_model=PredictionAvecExplicationOutput)
def predict_single(contrat: ContratInput):
    """Score un seul contrat avec explicabilité SHAP"""
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non disponible")

    # Conversion en DataFrame (exclure contrat_id)
    data = contrat.dict()
    contrat_id = data.pop('contrat_id')
    df = pd.DataFrame([data])

    # Prédiction
    try:
        if hasattr(model, 'predict_proba'):
            score = float(model.predict_proba(df)[0][1])
            classe = int(model.predict(df)[0])
        else:
            # MLflow pyfunc
            prediction = model.predict(df)
            score = float(prediction[0]) if len(prediction.shape) == 1 else float(prediction[0][1])
            classe = 1 if score >= 0.5 else 0
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur de prédiction: {str(e)}")

    # Classification du niveau de risque
    if score >= 0.75:
        niveau = "CRITIQUE"
    elif score >= 0.50:
        niveau = "ÉLEVÉ"
    elif score >= 0.25:
        niveau = "MODÉRÉ"
    else:
        niveau = "FAIBLE"

    # Mise en cache du contrat pour l'endpoint /explication
    _cache_contrat(contrat_id, df)

    # Calcul des facteurs explicatifs SHAP (dégradation gracieuse)
    facteurs_explicatifs = []
    explication_disponible = False

    if shap_calculator is not None:
        try:
            # Récupérer les moyennes du cache (dict vide si non disponible)
            moyennes = cache_moyennes.get() or {}

            # Calculer les top 5 facteurs
            facteurs = shap_calculator.calculer_facteurs(df, moyennes, top_n=5)
            facteurs_explicatifs = [
                FacteurExplicatifResponse(
                    nom_variable=f.nom_variable,
                    shap_value=f.shap_value,
                    valeur_contrat=f.valeur_contrat,
                    moyenne_portefeuille=f.moyenne_portefeuille
                )
                for f in facteurs
            ]
            explication_disponible = True
        except Exception as e:
            # Dégradation gracieuse : on retourne le score sans explication
            logger.warning(f"Erreur calcul SHAP pour contrat {contrat_id}: {e}")
            facteurs_explicatifs = []
            explication_disponible = False

    return PredictionAvecExplicationOutput(
        contrat_id=contrat_id,
        score_risque=round(score, 4),
        classe_predite=classe,
        niveau_risque=niveau,
        facteurs_explicatifs=facteurs_explicatifs,
        explication_disponible=explication_disponible,
        timestamp=datetime.now().isoformat()
    )


def _classify_risk(score: float) -> str:
    """Classification du niveau de risque, alignée sur les libellés attendus
    par le frontend Angular (type NiveauRisque : CRITIQUE/ÉLEVÉ/MOYEN/FAIBLE)."""
    if score >= 0.75:
        return "CRITIQUE"
    elif score >= 0.50:
        return "ÉLEVÉ"
    elif score >= 0.25:
        return "MOYEN"
    else:
        return "FAIBLE"


@app.post("/predict_batch")
def predict_batch(current_user: UserOut = Depends(get_current_user)):
    """Score tout le portefeuille depuis DATASET_SCORING_PREPROCESSED.

    Ne prend aucun body : récupère l'ensemble des contrats déjà
    preprocessed depuis Oracle et les score en une seule opération
    vectorisée (pas de boucle Python par contrat, cf. predict_single
    qui reste dédié au scoring à l'unité avec explicabilité SHAP).
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non disponible")

    try:
        df_raw = get_all_contrats_preprocessed()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erreur d'accès aux données Oracle: {e}")

    if df_raw.empty:
        return {
            "predictions": [],
            "summary": {
                "total_contrats": 0,
                "score_moyen": 0,
                "contrats_critiques": 0,
                "contrats_eleves": 0,
                "contrats_moderes": 0,
                "contrats_faibles": 0,
            },
        }

    contrat_ids = df_raw["contrat_id"].astype(str).tolist()

    features_list = realtime_preprocessor.get_features_list() if realtime_preprocessor else None
    if not features_list:
        raise HTTPException(status_code=503, detail="Liste des features indisponible")

    # Résolution explicite des noms de colonnes (troncature Oracle à 30
    # caractères, substitutions de l'import, casse). Lève si une feature
    # manque, plutôt que de la remplacer par 0 et fausser le score.
    try:
        df_features = extraire_features(df_raw, features_list)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        scores = model.predict_proba(df_features)[:, 1]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur de prédiction: {str(e)}")

    niveaux = [_classify_risk(float(s)) for s in scores]
    timestamp = datetime.now().isoformat()

    predictions = [
        {
            "contrat_id": contrat_ids[i],
            "score_risque": round(float(scores[i]), 4),
            "classe_predite": 1 if scores[i] >= 0.5 else 0,
            "niveau_risque": niveaux[i],
            "top_facteurs": [],
            "timestamp": timestamp,
        }
        for i in range(len(scores))
    ]

    summary = {
        "total_contrats": len(predictions),
        "score_moyen": round(float(np.mean(scores)), 4),
        "contrats_critiques": sum(1 for n in niveaux if n == "CRITIQUE"),
        "contrats_eleves": sum(1 for n in niveaux if n == "ÉLEVÉ"),
        "contrats_moderes": sum(1 for n in niveaux if n == "MOYEN"),
        "contrats_faibles": sum(1 for n in niveaux if n == "FAIBLE"),
    }

    return {"predictions": predictions, "summary": summary}


@app.get("/dashboard/stats")
def dashboard_stats(current_user: UserOut = Depends(get_current_user)):
    """Statistiques agrégées du portefeuille pour le Dashboard.

    Scoring vectorisé de tout le portefeuille (même principe que
    /predict_batch), puis tri par score décroissant pour alimenter le
    tableau "Contrats scorés" du Dashboard (filtrable/recherchable
    côté client).
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non disponible")

    try:
        df_raw = get_all_contrats_preprocessed()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erreur d'accès aux données Oracle: {e}")

    if df_raw.empty:
        return {
            "total_contrats": 0,
            "critique": 0,
            "eleve": 0,
            "moyen": 0,
            "faible": 0,
            "score_moyen": 0,
            "top10": [],
        }

    contrat_ids = df_raw["contrat_id"].astype(str).tolist()

    features_list = realtime_preprocessor.get_features_list() if realtime_preprocessor else None
    if not features_list:
        raise HTTPException(status_code=503, detail="Liste des features indisponible")

    try:
        df_features = extraire_features(df_raw, features_list)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        scores = model.predict_proba(df_features)[:, 1]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur de prédiction: {str(e)}")

    niveaux = [_classify_risk(float(s)) for s in scores]
    timestamp = datetime.now().isoformat()

    # Échantillon aléatoire (pas un "top" trié par score) : renvoyer tout
    # le portefeuille (potentiellement >80k lignes) alourdit inutilement la
    # réponse réseau et le rendu du tableau côté Angular, mais se limiter
    # aux scores les plus élevés ne montrerait que des contrats CRITIQUE.
    # Un échantillon aléatoire reste représentatif de tous les niveaux de
    # risque pour l'exploration dans le Dashboard.
    ECHANTILLON_DASHBOARD = 1000
    taille_echantillon = min(ECHANTILLON_DASHBOARD, len(scores))
    rng = np.random.default_rng()
    ordre = rng.choice(len(scores), size=taille_echantillon, replace=False)
    # Trié par score décroissant pour un affichage lisible dans le tableau.
    ordre = ordre[np.argsort(scores[ordre])[::-1]]

    top10 = []
    for i in ordre:
        contrat_id = contrat_ids[i]
        # Met en cache les features de ce contrat : sans ça, l'explication
        # SHAP (/scoring/contrat/{id}/explication) renvoie systématiquement
        # 404 pour tout contrat affiché depuis le Dashboard, puisque ce
        # scoring vectorisé ne passait jamais par le cache auparavant.
        _cache_contrat(contrat_id, df_features.iloc[[i]])
        top10.append({
            "contrat_id": contrat_id,
            "score_risque": round(float(scores[i]), 4),
            "classe_predite": 1 if scores[i] >= 0.5 else 0,
            "niveau_risque": niveaux[i],
            "top_facteurs": [],
            "timestamp": timestamp,
        })

    return {
        "total_contrats": len(scores),
        "critique": sum(1 for n in niveaux if n == "CRITIQUE"),
        "eleve": sum(1 for n in niveaux if n == "ÉLEVÉ"),
        "moyen": sum(1 for n in niveaux if n == "MOYEN"),
        "faible": sum(1 for n in niveaux if n == "FAIBLE"),
        # Pourcentage (0-100), cohérent avec l'affichage Angular
        # ({{ score_moyen | number:'1.1-1' }}%). Différent de /predict_batch
        # qui renvoie une proportion 0-1 pour chaque contrat individuel.
        "score_moyen": round(float(np.mean(scores)) * 100, 2),
        "top10": top10,
    }


@app.get("/model_info")
def model_info():
    """Informations sur le modèle en production"""
    info = {
        "model_name": MODEL_NAME,
        "stage": MODEL_STAGE,
        "model_type": type(model).__name__ if model else "None",
    }

    if model and hasattr(model, 'feature_names_in_'):
        info["n_features"] = len(model.feature_names_in_)

    return info


@app.get("/portefeuille/moyennes", response_model=MoyennesResponse)
def get_moyennes_portefeuille():
    """Retourne les moyennes du portefeuille (cache 24h)."""
    moyennes = cache_moyennes.get()
    nombre_contrats = DEFAULT_NOMBRE_CONTRATS

    if moyennes is None:
        # Calcul des vraies moyennes depuis Oracle. DEFAULT_MOYENNES (ancien
        # schéma à 25 champs génériques, ex: 'produit') ne correspond à
        # aucune des 32 features réelles du modèle Option C : l'utiliser
        # donnerait des moyennes à 0.0 pour toutes les variables.
        try:
            df_raw = get_all_contrats_preprocessed()
            df_features = extraire_features(df_raw, FEATURE_NAMES)
            moyennes = {nom: round(float(df_features[nom].mean()), 4) for nom in FEATURE_NAMES}
            nombre_contrats = len(df_features)
            cache_moyennes.set(moyennes)
        except Exception as e:
            logger.warning(f"Erreur calcul moyennes portefeuille depuis Oracle: {e}")
            moyennes = {nom: 0.0 for nom in FEATURE_NAMES}

    now = datetime.now()
    date_calcul = now.isoformat()
    cache_valide_jusqu_a = (now + timedelta(hours=CacheMoyennes.TTL_HEURES)).isoformat()

    return MoyennesResponse(
        moyennes=moyennes,
        nombre_contrats=nombre_contrats,
        date_calcul=date_calcul,
        cache_valide_jusqu_a=cache_valide_jusqu_a,
    )


@app.get("/scoring/contrat/{contrat_id}")
def scorer_contrat_oracle(contrat_id: str):
    """Score un contrat en temps réel depuis les données Oracle.

    Flux :
    1. Tente de récupérer les données brutes du contrat depuis les tables sources Oracle
       (requête V3 filtrée par contrat_id — données 100% à jour)
    2. Si Oracle n'est pas disponible, tente le fallback sur DATASET_SCORING_PREPROCESSED
    3. Applique le preprocessing temps réel (artefacts sauvegardés)
    4. Passe au modèle et retourne le score + explicabilité SHAP

    Args:
        contrat_id: Numéro du contrat (ex: '12345678')

    Returns:
        Score de risque, classe prédite, niveau de risque, facteurs explicatifs

    Raises:
        HTTPException 503: Modèle ou preprocessor non disponible
        HTTPException 404: Contrat non trouvé dans Oracle
        HTTPException 500: Erreur interne
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non disponible")

    contrat_df = None
    source = "unknown"
    needs_preprocessing = True

    # ========================================================================
    # Stratégie de récupération des données
    # ========================================================================

    # Option 1 : Requête temps réel sur les tables sources (données à jour)
    if realtime_preprocessor is not None and oracle_available:
        try:
            contrat_df = get_contrat_brut(contrat_id)
            if contrat_df is not None:
                source = "tables_sources"
                needs_preprocessing = True
        except Exception as e:
            logger.warning(f"Erreur requête tables sources pour {contrat_id}: {e}")
            contrat_df = None

    # Option 2 : Fallback sur DATASET_SCORING_PREPROCESSED (données déjà preprocessed)
    if contrat_df is None:
        try:
            contrat_df = get_contrat_preprocessed(contrat_id)
            if contrat_df is not None:
                source = "preprocessed_table"
                needs_preprocessing = False
        except Exception as e:
            logger.warning(f"Erreur fallback PREPROCESSED pour {contrat_id}: {e}")
            contrat_df = None

    # Contrat non trouvé nulle part
    if contrat_df is None:
        raise HTTPException(
            status_code=404,
            detail=f"Contrat '{contrat_id}' non trouvé dans la base de données"
        )

    # ========================================================================
    # Preprocessing + Prédiction
    # ========================================================================
    try:
        if needs_preprocessing:
            # Appliquer le preprocessing temps réel
            features_df = realtime_preprocessor.preprocess_to_dataframe(contrat_df)
        else:
            # Données déjà preprocessed — extraire les features via la
            # résolution de noms (l'ancienne version complétait à 0 les
            # colonnes non trouvées, ce qui faussait silencieusement le
            # score sur ce chemin de fallback).
            features_list = realtime_preprocessor.get_features_list() if realtime_preprocessor else None
            if features_list:
                features_df = extraire_features(contrat_df, features_list)
            else:
                # Pas de preprocessor — tenter avec les colonnes disponibles
                id_cols = ['contrat_id', 'etat_contrat', 'variable_cible']
                feature_cols = [c for c in contrat_df.columns if c not in id_cols]
                features_df = contrat_df[feature_cols].copy()

        # Prédiction
        if hasattr(model, 'predict_proba'):
            score = float(model.predict_proba(features_df)[0][1])
            classe = int(model.predict(features_df)[0])
        else:
            prediction = model.predict(features_df)
            score = float(prediction[0]) if len(prediction.shape) == 1 else float(prediction[0][1])
            classe = 1 if score >= 0.5 else 0

    except Exception as e:
        logger.error(f"Erreur scoring contrat {contrat_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du scoring: {str(e)}"
        )

    # Classification du niveau de risque
    if score >= 0.75:
        niveau = "CRITIQUE"
    elif score >= 0.50:
        niveau = "ÉLEVÉ"
    elif score >= 0.25:
        niveau = "MODÉRÉ"
    else:
        niveau = "FAIBLE"

    # Mise en cache pour l'endpoint /explication
    _cache_contrat(contrat_id, features_df)

    # ========================================================================
    # Explicabilité SHAP
    # ========================================================================
    facteurs_explicatifs = []
    explication_disponible = False

    if shap_calculator is not None:
        try:
            moyennes = cache_moyennes.get() or {}
            facteurs = shap_calculator.calculer_facteurs(features_df, moyennes, top_n=5)
            facteurs_explicatifs = [
                FacteurExplicatifResponse(
                    nom_variable=f.nom_variable,
                    shap_value=f.shap_value,
                    valeur_contrat=f.valeur_contrat,
                    moyenne_portefeuille=f.moyenne_portefeuille
                )
                for f in facteurs
            ]
            explication_disponible = True
        except Exception as e:
            logger.warning(f"Erreur SHAP pour contrat {contrat_id}: {e}")

    return {
        "contrat_id": contrat_id,
        "score_risque": round(score, 4),
        "classe_predite": classe,
        "niveau_risque": niveau,
        "facteurs_explicatifs": facteurs_explicatifs,
        "explication_disponible": explication_disponible,
        "source_donnees": source,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/scoring/contrat/{contrat_id}/explication", response_model=ExplicationResponse)
def get_explication(contrat_id: str):
    """Retourne les facteurs explicatifs d'un contrat déjà scoré.

    Recherche le contrat dans le cache en mémoire des contrats récemment scorés.
    En production, cette lookup serait effectuée depuis la base de données.

    Returns:
        ExplicationResponse avec les facteurs explicatifs ou explication_disponible=False
    Raises:
        HTTPException 503: Si le modèle ou le calculateur SHAP n'est pas disponible
        HTTPException 404: Si le contrat n'a pas été trouvé dans le cache
    """
    # Vérifier que le modèle et SHAP sont disponibles
    if model is None or shap_calculator is None:
        raise HTTPException(
            status_code=503,
            detail="Service d'explicabilité non disponible (modèle ou SHAP non initialisé)"
        )

    # Rechercher le contrat dans le cache en mémoire
    # En production, on ferait un SELECT depuis la base Oracle
    if contrat_id not in _scored_contrats:
        raise HTTPException(
            status_code=404,
            detail="Contrat non trouvé ou non scoré"
        )

    # Récupérer les données du contrat depuis le cache
    contrat_df = _scored_contrats[contrat_id]

    # Calcul des facteurs explicatifs SHAP
    try:
        # Récupérer les moyennes du cache (dict vide si non disponible)
        moyennes = cache_moyennes.get() or {}

        # Calculer les top 5 facteurs
        facteurs = shap_calculator.calculer_facteurs(contrat_df, moyennes, top_n=5)
        facteurs_explicatifs = [
            FacteurExplicatifResponse(
                nom_variable=f.nom_variable,
                shap_value=f.shap_value,
                valeur_contrat=f.valeur_contrat,
                moyenne_portefeuille=f.moyenne_portefeuille
            )
            for f in facteurs
        ]

        return ExplicationResponse(
            contrat_id=contrat_id,
            facteurs_explicatifs=facteurs_explicatifs,
            explication_disponible=True,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        # Dégradation gracieuse : retourner explication_disponible=False
        logger.warning(f"Erreur calcul SHAP pour explication contrat {contrat_id}: {e}")
        return ExplicationResponse(
            contrat_id=contrat_id,
            facteurs_explicatifs=[],
            explication_disponible=False,
            timestamp=datetime.now().isoformat()
        )


# ============================================================================
# LANCEMENT
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Lancement de l'API de scoring...")
    print("   Documentation : http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
