"""
Tests unitaires des endpoints de l'API de scoring (04_serve_api.py).
=====================================================================
Teste la structure des réponses JSON, les codes HTTP (200, 404, 503),
et la dégradation gracieuse quand SHAP échoue.

Validates: Requirements 1.4, 1.5, 7.1
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Nous devons mocker les dépendances AVANT d'importer le module API,
# car 04_serve_api.py exécute du code au niveau module (chargement modèle, SHAP, etc.)
# Créer un mock model qui se comporte comme un classifieur sklearn
_mock_model = MagicMock()
_mock_model.predict_proba = MagicMock(return_value=np.array([[0.3, 0.7]]))
_mock_model.predict = MagicMock(return_value=np.array([1]))

# Mock les modules problématiques à l'import
with patch.dict("sys.modules", {"mlflow": MagicMock(), "mlflow.pyfunc": MagicMock()}):
    with patch("mlflow.pyfunc.load_model", return_value=_mock_model):
        # Mocker shap pour éviter l'initialisation TreeExplainer réelle
        mock_shap_module = MagicMock()
        with patch.dict("sys.modules", {"shap": mock_shap_module}):
            from shap_calculator import SHAPCalculator, FacteurExplicatif
            import importlib

# Maintenant on peut importer l'app en mockant le chargement du modèle
# On re-patch pour que l'import du module API fonctionne sans MLflow/SHAP réels
_mock_shap_calculator = MagicMock(spec=SHAPCalculator)
_mock_shap_calculator.calculer_facteurs = MagicMock(return_value=[
    FacteurExplicatif(
        nom_variable="ratio_rachats_primes",
        shap_value=0.35,
        valeur_contrat=0.45,
        moyenne_portefeuille=0.18
    ),
    FacteurExplicatif(
        nom_variable="nb_avt_risque_eleve",
        shap_value=0.22,
        valeur_contrat=5.0,
        moyenne_portefeuille=1.2
    ),
    FacteurExplicatif(
        nom_variable="total_rachats",
        shap_value=-0.15,
        valeur_contrat=5000.0,
        moyenne_portefeuille=8000.0
    ),
])


@pytest.fixture
def client():
    """Crée un TestClient avec le modèle et shap_calculator mockés."""
    with patch.dict("sys.modules", {
        "mlflow": MagicMock(),
        "mlflow.pyfunc": MagicMock(),
        "shap": MagicMock(),
    }):
        with patch("mlflow.pyfunc.load_model", return_value=_mock_model):
            # Forcer le rechargement du module API avec nos mocks
            if "04_serve_api" in sys.modules:
                del sys.modules["04_serve_api"]

            # Importer le module API
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "serve_api",
                str(Path(__file__).parent.parent / "api" / "04_serve_api.py")
            )
            serve_api = importlib.util.module_from_spec(spec)

            # Patcher les variables globales pendant l'exécution du module
            with patch.object(serve_api, "__name__", "serve_api"):
                spec.loader.exec_module(serve_api)

            # Maintenant patcher les globales du module importé
            serve_api.model = _mock_model
            serve_api.shap_calculator = _mock_shap_calculator

            from fastapi.testclient import TestClient
            yield TestClient(serve_api.app), serve_api


@pytest.fixture
def client_no_model():
    """Crée un TestClient avec le modèle = None (indisponible)."""
    with patch.dict("sys.modules", {
        "mlflow": MagicMock(),
        "mlflow.pyfunc": MagicMock(),
        "shap": MagicMock(),
    }):
        with patch("mlflow.pyfunc.load_model", return_value=None):
            if "04_serve_api" in sys.modules:
                del sys.modules["04_serve_api"]

            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "serve_api_no_model",
                str(Path(__file__).parent.parent / "api" / "04_serve_api.py")
            )
            serve_api = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(serve_api)

            # Forcer model=None
            serve_api.model = None
            serve_api.shap_calculator = None

            from fastapi.testclient import TestClient
            yield TestClient(serve_api.app), serve_api


# ============================================================================
# Données de test
# ============================================================================
VALID_CONTRAT_PAYLOAD = {
    "contrat_id": "CNT_TEST_001",
    "produit": 2.0,
    "tarif": 1.5,
    "cadre_fiscal": 1.0,
    "periodicite": 2.0,
    "mode_reglement": 1.0,
    "duree_annees": 10.0,
    "duree_mois": 120.0,
    "versement_initial": 30000.0,
    "total_primes": 50000.0,
    "total_rachats": 15000.0,
    "nb_mouvements": 20.0,
    "nb_mouvements_annules": 2.0,
    "nb_avt_risque_eleve": 3.0,
    "nb_avt_arret_annulation": 1.0,
    "nb_avt_arbitrage": 4.0,
    "nb_avt_versement": 5.0,
    "nb_avt_modif_admin_motif": 2.0,
    "flag_rachat_programme": 0.0,
    "flag_renonciation": 0.0,
    "flag_deces": 0.0,
    "sexe": 1.0,
    "csp": 3.0,
    "situation_famille": 2.0,
    "age_souscripteur": 55.0,
    "ratio_rachats_primes": 0.30,
}


# ============================================================================
# Test 1: Structure de la réponse /predict (POST → 200)
# ============================================================================
class TestPredictEndpointStructure:
    """Teste la structure des réponses JSON de l'endpoint /predict."""

    def test_predict_returns_200_with_valid_contract(self, client):
        """POST /predict avec un contrat valide retourne 200."""
        test_client, _ = client
        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        assert response.status_code == 200

    def test_predict_response_contains_required_fields(self, client):
        """La réponse contient tous les champs requis du schéma PredictionAvecExplicationOutput."""
        test_client, _ = client
        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()

        required_fields = [
            "contrat_id",
            "score_risque",
            "classe_predite",
            "niveau_risque",
            "facteurs_explicatifs",
            "explication_disponible",
            "timestamp",
        ]
        for field in required_fields:
            assert field in data, f"Champ manquant: {field}"

    def test_predict_contrat_id_matches_input(self, client):
        """Le contrat_id retourné correspond à celui envoyé."""
        test_client, _ = client
        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()
        assert data["contrat_id"] == "CNT_TEST_001"

    def test_predict_facteurs_explicatifs_is_list(self, client):
        """facteurs_explicatifs est bien une liste."""
        test_client, _ = client
        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()
        assert isinstance(data["facteurs_explicatifs"], list)

    def test_predict_explication_disponible_is_boolean(self, client):
        """explication_disponible est un booléen."""
        test_client, _ = client
        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()
        assert isinstance(data["explication_disponible"], bool)

    def test_predict_score_risque_is_float_between_0_and_1(self, client):
        """score_risque est un float entre 0 et 1."""
        test_client, _ = client
        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()
        assert isinstance(data["score_risque"], float)
        assert 0.0 <= data["score_risque"] <= 1.0

    def test_predict_classe_predite_is_int(self, client):
        """classe_predite est un entier (0 ou 1)."""
        test_client, _ = client
        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()
        assert isinstance(data["classe_predite"], int)
        assert data["classe_predite"] in [0, 1]

    def test_predict_niveau_risque_is_valid(self, client):
        """niveau_risque est une des valeurs attendues."""
        test_client, _ = client
        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()
        valid_niveaux = ["CRITIQUE", "ÉLEVÉ", "MODÉRÉ", "FAIBLE"]
        assert data["niveau_risque"] in valid_niveaux

    def test_predict_facteurs_explicatifs_structure(self, client):
        """Chaque facteur explicatif contient les 4 champs requis."""
        test_client, _ = client
        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()

        for facteur in data["facteurs_explicatifs"]:
            assert "nom_variable" in facteur
            assert "shap_value" in facteur
            assert "valeur_contrat" in facteur
            assert "moyenne_portefeuille" in facteur


# ============================================================================
# Test 2: /predict avec modèle indisponible → 503
# ============================================================================
class TestPredictModelUnavailable:
    """Teste le comportement quand le modèle est None (503)."""

    def test_predict_returns_503_when_model_is_none(self, client_no_model):
        """POST /predict retourne 503 quand model=None."""
        test_client, _ = client_no_model
        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        assert response.status_code == 503

    def test_predict_503_has_detail_message(self, client_no_model):
        """La réponse 503 contient un message d'erreur."""
        test_client, _ = client_no_model
        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()
        assert "detail" in data


# ============================================================================
# Test 3: Endpoint /portefeuille/moyennes (GET → 200)
# ============================================================================
class TestMoyennesEndpoint:
    """Teste la structure de la réponse de GET /portefeuille/moyennes."""

    def test_moyennes_returns_200(self, client):
        """GET /portefeuille/moyennes retourne 200."""
        test_client, _ = client
        response = test_client.get("/portefeuille/moyennes")
        assert response.status_code == 200

    def test_moyennes_response_structure(self, client):
        """La réponse contient les champs requis."""
        test_client, _ = client
        response = test_client.get("/portefeuille/moyennes")
        data = response.json()

        assert "moyennes" in data
        assert "nombre_contrats" in data
        assert "date_calcul" in data
        assert "cache_valide_jusqu_a" in data

    def test_moyennes_is_dict(self, client):
        """moyennes est un dictionnaire."""
        test_client, _ = client
        response = test_client.get("/portefeuille/moyennes")
        data = response.json()
        assert isinstance(data["moyennes"], dict)

    def test_moyennes_contains_all_feature_names(self, client):
        """moyennes contient toutes les FEATURE_NAMES du modèle."""
        test_client, serve_api = client
        response = test_client.get("/portefeuille/moyennes")
        data = response.json()

        for feature_name in serve_api.FEATURE_NAMES:
            assert feature_name in data["moyennes"], (
                f"Variable manquante dans moyennes: {feature_name}"
            )

    def test_moyennes_nombre_contrats_is_positive_int(self, client):
        """nombre_contrats est un entier positif."""
        test_client, _ = client
        response = test_client.get("/portefeuille/moyennes")
        data = response.json()
        assert isinstance(data["nombre_contrats"], int)
        assert data["nombre_contrats"] > 0

    def test_moyennes_dates_are_iso_format(self, client):
        """date_calcul et cache_valide_jusqu_a sont en format ISO."""
        test_client, _ = client
        response = test_client.get("/portefeuille/moyennes")
        data = response.json()

        # Vérifier que les dates sont parsables en ISO format
        datetime.fromisoformat(data["date_calcul"])
        datetime.fromisoformat(data["cache_valide_jusqu_a"])


# ============================================================================
# Test 4: Endpoint /scoring/contrat/{id}/explication (GET → 404, 200)
# ============================================================================
class TestExplicationEndpoint:
    """Teste l'endpoint GET /scoring/contrat/{id}/explication."""

    def test_explication_unknown_contrat_returns_404(self, client):
        """GET /scoring/contrat/{id}/explication retourne 404 pour un contrat inconnu."""
        test_client, _ = client
        response = test_client.get("/scoring/contrat/CONTRAT_INEXISTANT/explication")
        assert response.status_code == 404

    def test_explication_404_has_detail_message(self, client):
        """La réponse 404 contient un message d'erreur."""
        test_client, _ = client
        response = test_client.get("/scoring/contrat/CONTRAT_INEXISTANT/explication")
        data = response.json()
        assert "detail" in data

    def test_explication_after_predict_returns_200(self, client):
        """Après POST /predict, GET /scoring/contrat/{id}/explication retourne 200."""
        test_client, _ = client

        # D'abord scorer le contrat
        test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)

        # Ensuite demander l'explication
        response = test_client.get("/scoring/contrat/CNT_TEST_001/explication")
        assert response.status_code == 200

    def test_explication_response_structure(self, client):
        """La réponse d'explication a la structure attendue."""
        test_client, _ = client

        # Scorer d'abord
        test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)

        # Demander l'explication
        response = test_client.get("/scoring/contrat/CNT_TEST_001/explication")
        data = response.json()

        assert "contrat_id" in data
        assert "facteurs_explicatifs" in data
        assert "explication_disponible" in data
        assert "timestamp" in data
        assert data["contrat_id"] == "CNT_TEST_001"

    def test_explication_facteurs_is_list(self, client):
        """facteurs_explicatifs dans la réponse d'explication est une liste."""
        test_client, _ = client

        test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        response = test_client.get("/scoring/contrat/CNT_TEST_001/explication")
        data = response.json()

        assert isinstance(data["facteurs_explicatifs"], list)


# ============================================================================
# Test 5: Dégradation gracieuse (SHAP échoue → 200 + explication_disponible=False)
# ============================================================================
class TestGracefulDegradation:
    """Teste la dégradation gracieuse quand le calcul SHAP échoue."""

    def test_predict_returns_200_when_shap_fails(self, client):
        """POST /predict retourne 200 même si SHAP lève une exception."""
        test_client, serve_api = client

        # Faire échouer le shap_calculator
        failing_calculator = MagicMock()
        failing_calculator.calculer_facteurs.side_effect = RuntimeError(
            "SHAP calculation failed"
        )
        serve_api.shap_calculator = failing_calculator

        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        assert response.status_code == 200

    def test_predict_explication_disponible_false_when_shap_fails(self, client):
        """explication_disponible=False quand SHAP échoue."""
        test_client, serve_api = client

        failing_calculator = MagicMock()
        failing_calculator.calculer_facteurs.side_effect = RuntimeError(
            "SHAP calculation failed"
        )
        serve_api.shap_calculator = failing_calculator

        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()

        assert data["explication_disponible"] is False

    def test_predict_facteurs_empty_when_shap_fails(self, client):
        """facteurs_explicatifs est vide quand SHAP échoue."""
        test_client, serve_api = client

        failing_calculator = MagicMock()
        failing_calculator.calculer_facteurs.side_effect = RuntimeError(
            "SHAP calculation failed"
        )
        serve_api.shap_calculator = failing_calculator

        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()

        assert data["facteurs_explicatifs"] == []

    def test_predict_still_has_score_when_shap_fails(self, client):
        """Le score est toujours présent même quand SHAP échoue."""
        test_client, serve_api = client

        failing_calculator = MagicMock()
        failing_calculator.calculer_facteurs.side_effect = RuntimeError(
            "SHAP calculation failed"
        )
        serve_api.shap_calculator = failing_calculator

        response = test_client.post("/predict", json=VALID_CONTRAT_PAYLOAD)
        data = response.json()

        assert "score_risque" in data
        assert "classe_predite" in data
        assert "niveau_risque" in data
        assert isinstance(data["score_risque"], float)
