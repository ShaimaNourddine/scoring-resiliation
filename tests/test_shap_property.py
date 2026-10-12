"""
Property-based tests pour les facteurs SHAP.

Feature: scoring-explicabilite
Property 1: Top-N sélection et tri par importance décroissante
Property 2: Complétude structurelle des facteurs explicatifs

Validates: Requirements 1.2, 1.3
"""

import sys
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Mock le module shap avant l'import de shap_calculator
# car shap n'est pas installé dans l'environnement de test
mock_shap = MagicMock()
sys.modules["shap"] = mock_shap

from shap_calculator import SHAPCalculator, FacteurExplicatif


# --- Strategies ---

# Génère une liste de noms de features uniques (entre 1 et 30 features)
feature_names_strategy = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu"), whitelist_characters="_"),
        min_size=1,
        max_size=20,
    ),
    min_size=1,
    max_size=30,
    unique=True,
)

# Génère un top_n raisonnable
top_n_strategy = st.integers(min_value=1, max_value=10)

# Génère des valeurs SHAP (floats non-NaN, non-Inf)
shap_value_strategy = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)


@st.composite
def shap_scenario(draw):
    """Génère un scénario complet: feature_names, shap_values, contrat_values, moyennes, top_n."""
    feature_names = draw(feature_names_strategy)
    n_features = len(feature_names)

    shap_values = draw(
        st.lists(shap_value_strategy, min_size=n_features, max_size=n_features)
    )
    contrat_values = draw(
        st.lists(
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=n_features,
            max_size=n_features,
        )
    )
    moyennes_values = draw(
        st.lists(
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=n_features,
            max_size=n_features,
        )
    )
    top_n = draw(top_n_strategy)

    return {
        "feature_names": feature_names,
        "shap_values": shap_values,
        "contrat_values": contrat_values,
        "moyennes_values": moyennes_values,
        "top_n": top_n,
    }


def _build_calculator_and_call(scenario):
    """Helper: construit un SHAPCalculator mocké et appelle calculer_facteurs."""
    feature_names = scenario["feature_names"]
    shap_values = scenario["shap_values"]
    contrat_values = scenario["contrat_values"]
    moyennes_values = scenario["moyennes_values"]
    top_n = scenario["top_n"]

    # Créer le DataFrame du contrat
    contrat_data = pd.DataFrame([dict(zip(feature_names, contrat_values))])

    # Créer le dictionnaire de moyennes
    moyennes = dict(zip(feature_names, moyennes_values))

    # Mock le TreeExplainer via le module shap déjà mocké
    mock_explainer = MagicMock()
    mock_shap.TreeExplainer.return_value = mock_explainer

    # Configurer shap_values() pour retourner nos valeurs générées
    # Format: array 2D [1, n_features] (un seul échantillon)
    mock_explainer.shap_values.return_value = np.array([shap_values])

    mock_model = MagicMock()
    calculator = SHAPCalculator(mock_model, feature_names)
    result = calculator.calculer_facteurs(contrat_data, moyennes, top_n=top_n)

    return result, shap_values, feature_names, top_n


# --- Property Test ---


class TestTopNSelectionProperty:
    """
    Feature: scoring-explicabilite
    Property 1: Top-N sélection et tri par importance décroissante

    For any liste de valeurs SHAP associées aux variables d'un modèle,
    la fonction de sélection des top N facteurs SHALL retourner au plus N éléments,
    triés par valeur absolue de shap_value décroissante, et chaque élément du résultat
    a une |shap_value| supérieure ou égale à celle de tout élément non sélectionné.

    Validates: Requirements 1.2
    """

    @given(scenario=shap_scenario())
    @settings(max_examples=150, deadline=None)
    def test_property_top_n_selection_et_tri(self, scenario):
        """
        Property 1: Top-N sélection et tri par importance décroissante

        Vérifie les trois sous-propriétés:
        1. La taille du résultat est <= top_n ET <= nombre de features
        2. Les résultats sont triés par |shap_value| décroissant
        3. Chaque élément dans le résultat a |shap_value| >= tout élément hors résultat
        """
        result, shap_values, feature_names, top_n = _build_calculator_and_call(scenario)

        n_features = len(feature_names)

        # --- Sub-property 1: Taille du résultat ---
        assert len(result) <= top_n, (
            f"Le résultat contient {len(result)} éléments, attendu <= {top_n}"
        )
        assert len(result) <= n_features, (
            f"Le résultat contient {len(result)} éléments, attendu <= {n_features} features"
        )
        # La taille attendue est min(top_n, n_features)
        expected_size = min(top_n, n_features)
        assert len(result) == expected_size, (
            f"Le résultat contient {len(result)} éléments, attendu exactement {expected_size}"
        )

        # --- Sub-property 2: Tri par |shap_value| décroissant ---
        for i in range(len(result) - 1):
            assert abs(result[i].shap_value) >= abs(result[i + 1].shap_value), (
                f"Élément {i} (|shap|={abs(result[i].shap_value)}) < "
                f"élément {i+1} (|shap|={abs(result[i+1].shap_value)}). "
                f"Le tri par valeur absolue décroissante n'est pas respecté."
            )

        # --- Sub-property 3: Minimum du résultat >= maximum hors résultat ---
        if len(result) < n_features:
            # Identifier les noms de variables dans le résultat
            result_names = {f.nom_variable for f in result}

            # Trouver la plus petite |shap_value| dans le résultat
            min_abs_in_result = min(abs(f.shap_value) for f in result)

            # Trouver la plus grande |shap_value| hors du résultat
            excluded_abs_values = [
                abs(shap_values[i])
                for i, name in enumerate(feature_names)
                if name not in result_names
            ]
            if excluded_abs_values:
                max_abs_excluded = max(excluded_abs_values)
                assert min_abs_in_result >= max_abs_excluded, (
                    f"Un élément exclu a |shap|={max_abs_excluded} > "
                    f"min(|shap| dans résultat)={min_abs_in_result}. "
                    f"La sélection top-N n'est pas correcte."
                )



class TestCompleteStructurelleProperty:
    """
    Feature: scoring-explicabilite
    Property 2: Complétude structurelle des facteurs explicatifs

    For any FacteurExplicatif construit par le système, l'objet SHALL contenir
    les quatre champs requis (nom_variable, shap_value, valeur_contrat,
    moyenne_portefeuille) avec des valeurs non-null, et nom_variable est une
    chaîne non-vide.

    Validates: Requirements 1.3
    """

    @given(scenario=shap_scenario())
    @settings(max_examples=150, deadline=None)
    def test_property_completude_structurelle(self, scenario):
        """
        Property 2: Complétude structurelle des facteurs explicatifs

        Vérifie pour chaque FacteurExplicatif retourné:
        1. nom_variable est une chaîne non-vide (str, len > 0)
        2. shap_value est un float non-null (non-None, non-NaN)
        3. valeur_contrat est un float non-null (non-None, non-NaN)
        4. moyenne_portefeuille est un float non-null (non-None, non-NaN)
        5. Tous les quatre champs sont explicitement présents (dataclass validation)
        """
        result, shap_values, feature_names, top_n = _build_calculator_and_call(scenario)

        for facteur in result:
            # --- Check 1: nom_variable est une chaîne non-vide ---
            assert isinstance(facteur.nom_variable, str), (
                f"nom_variable devrait être un str, obtenu: {type(facteur.nom_variable)}"
            )
            assert len(facteur.nom_variable) > 0, (
                "nom_variable ne doit pas être une chaîne vide"
            )

            # --- Check 2: shap_value est un float non-null, non-NaN ---
            assert facteur.shap_value is not None, (
                "shap_value ne doit pas être None"
            )
            assert isinstance(facteur.shap_value, float), (
                f"shap_value devrait être un float, obtenu: {type(facteur.shap_value)}"
            )
            assert not np.isnan(facteur.shap_value), (
                f"shap_value ne doit pas être NaN, obtenu pour '{facteur.nom_variable}'"
            )

            # --- Check 3: valeur_contrat est un float non-null, non-NaN ---
            assert facteur.valeur_contrat is not None, (
                "valeur_contrat ne doit pas être None"
            )
            assert isinstance(facteur.valeur_contrat, float), (
                f"valeur_contrat devrait être un float, obtenu: {type(facteur.valeur_contrat)}"
            )
            assert not np.isnan(facteur.valeur_contrat), (
                f"valeur_contrat ne doit pas être NaN pour '{facteur.nom_variable}'"
            )

            # --- Check 4: moyenne_portefeuille est un float non-null, non-NaN ---
            assert facteur.moyenne_portefeuille is not None, (
                "moyenne_portefeuille ne doit pas être None"
            )
            assert isinstance(facteur.moyenne_portefeuille, float), (
                f"moyenne_portefeuille devrait être un float, obtenu: {type(facteur.moyenne_portefeuille)}"
            )
            assert not np.isnan(facteur.moyenne_portefeuille), (
                f"moyenne_portefeuille ne doit pas être NaN pour '{facteur.nom_variable}'"
            )

            # --- Check 5: Les quatre champs sont présents (dataclass garantit, mais vérifions) ---
            assert hasattr(facteur, 'nom_variable'), "Champ nom_variable manquant"
            assert hasattr(facteur, 'shap_value'), "Champ shap_value manquant"
            assert hasattr(facteur, 'valeur_contrat'), "Champ valeur_contrat manquant"
            assert hasattr(facteur, 'moyenne_portefeuille'), "Champ moyenne_portefeuille manquant"
