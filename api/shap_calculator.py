"""
Module SHAP Calculator - Explicabilité XAI
==========================================
Calcule les valeurs SHAP pour un modèle XGBoost et retourne
les facteurs explicatifs les plus importants pour un contrat donné.

Utilise TreeExplainer de la librairie SHAP, optimisé pour les modèles
à base d'arbres (XGBoost, LightGBM, etc.).
"""

from dataclasses import dataclass
from typing import List
import shap
import numpy as np
import pandas as pd


@dataclass
class FacteurExplicatif:
    """Un facteur explicatif avec sa contribution SHAP.

    Attributes:
        nom_variable: Nom technique de la variable
        shap_value: Valeur SHAP (+ = pousse vers risque, - = réduit risque)
        valeur_contrat: Valeur réelle de la variable pour ce contrat
        moyenne_portefeuille: Moyenne de cette variable sur le portefeuille
    """
    nom_variable: str
    shap_value: float
    valeur_contrat: float
    moyenne_portefeuille: float


class SHAPCalculator:
    """Calcule les valeurs SHAP pour un modèle XGBoost.

    Instancie un TreeExplainer une seule fois à la création pour performance.
    La méthode calculer_facteurs() retourne les top N facteurs explicatifs
    triés par valeur absolue de shap_value décroissante.
    """

    def __init__(self, model, feature_names: List[str]):
        """Initialise le calculateur SHAP.

        Args:
            model: Modèle XGBoost (ou compatible TreeExplainer)
            feature_names: Liste des noms de variables du modèle
        """
        self.model = model
        self.feature_names = feature_names
        self.explainer = shap.TreeExplainer(model)

    def calculer_facteurs(
        self,
        contrat_data: pd.DataFrame,
        moyennes: dict,
        top_n: int = 5
    ) -> List[FacteurExplicatif]:
        """Calcule les top N facteurs explicatifs pour un contrat.

        Préconditions:
        - contrat_data est un DataFrame avec une seule ligne
        - moyennes contient une entrée pour chaque feature_name
        - top_n >= 1

        Postconditions:
        - Retourne au plus top_n facteurs
        - Les facteurs sont triés par |shap_value| décroissant
        - Chaque facteur a tous les champs remplis

        Args:
            contrat_data: DataFrame avec une seule ligne contenant les données du contrat
            moyennes: Dictionnaire {nom_variable: moyenne_portefeuille}
            top_n: Nombre maximum de facteurs à retourner (défaut: 5)

        Returns:
            Liste de FacteurExplicatif triés par importance décroissante
        """
        shap_values = self.explainer.shap_values(contrat_data)

        # Pour classification binaire, prendre la classe positive
        if isinstance(shap_values, list):
            shap_values = shap_values[1]

        values = shap_values[0]  # Premier (seul) échantillon

        # Créer la liste complète des facteurs
        facteurs = []
        for i, nom in enumerate(self.feature_names):
            facteurs.append(FacteurExplicatif(
                nom_variable=nom,
                shap_value=float(values[i]),
                valeur_contrat=float(contrat_data.iloc[0][nom]),
                moyenne_portefeuille=moyennes.get(nom, 0.0)
            ))

        # Trier par valeur absolue décroissante et prendre top N
        facteurs.sort(key=lambda f: abs(f.shap_value), reverse=True)
        return facteurs[:top_n]
