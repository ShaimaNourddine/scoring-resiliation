"""
Module de preprocessing temps réel pour un seul contrat — Option C
=====================================================================

Charge les artefacts sauvegardés par save_preprocessing_artifacts.py et
applique exactement les mêmes transformations (option C, 32 features :
nettoyage PROFESSION, correction virgule décimale, capping outliers,
regroupement pays rares, regroupement des motifs d'avenant par catégorie
de risque avant target encoding), mais sur une seule ligne (un seul contrat).

Usage:
    from realtime_preprocessor import RealtimePreprocessor

    preprocessor = RealtimePreprocessor('artifacts/')
    features_vector = preprocessor.preprocess(contrat_row_dict)
    # features_vector est un numpy array prêt pour model.predict_proba()

Prérequis:
    pip install pandas numpy scikit-learn
    + Avoir exécuté save_preprocessing_artifacts.py au moins une fois
"""

import logging
import os
import pickle
import sys
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# Nécessaire avec le Python embarqué (python-3.8.10-embed-amd64) utilisé sur
# le serveur préprod : contrairement à une installation Python standard, il
# n'ajoute pas automatiquement le dossier du script en cours d'exécution à
# sys.path (cf. python38._pth), donc les imports locaux (motif_groups,
# profession_utils) échouent avec ModuleNotFoundError sans cette ligne.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motif_groups import grouper_motif
from profession_utils import normalize_profession

logger = logging.getLogger(__name__)


class RealtimePreprocessor:
    """Applique le preprocessing option C à un seul contrat en temps réel.

    Charge les artefacts (scaler, encoders, maps, seuils) au démarrage et les
    réutilise pour chaque contrat. Le résultat est un vecteur de 32 features
    dans le même format que le dataset d'entraînement (dataset_train.csv).
    """

    def __init__(self, artifacts_dir: str = 'artifacts'):
        self.artifacts_dir = artifacts_dir
        self._load_artifacts()
        logger.info(f"RealtimePreprocessor initialisé ({len(self.features_list)} features, option C)")

    def _load_artifacts(self):
        required_files = [
            'medianes.pkl',
            'target_encodings.pkl',
            'frequency_encodings.pkl',
            'label_encoders.pkl',
            'scaler.pkl',
            'onehot_categories.pkl',
            'features_list.pkl',
            'global_mean.pkl',
            'pays_regroupement.pkl',
            'outlier_thresholds.pkl',
        ]

        for filename in required_files:
            filepath = os.path.join(self.artifacts_dir, filename)
            if not os.path.exists(filepath):
                raise FileNotFoundError(
                    f"Artefact manquant: {filepath}. "
                    f"Exécutez save_preprocessing_artifacts.py d'abord."
                )

        self.medianes = self._load('medianes.pkl')
        self.target_encodings = self._load('target_encodings.pkl')
        self.frequency_encodings = self._load('frequency_encodings.pkl')
        self.label_encoders = self._load('label_encoders.pkl')

        scaler_artifact = self._load('scaler.pkl')
        self.scaler_columns = scaler_artifact['columns']
        self.scaler_mean = scaler_artifact['mean']
        self.scaler_scale = scaler_artifact['scale']

        self.onehot_categories = self._load('onehot_categories.pkl')
        self.features_list = self._load('features_list.pkl')
        self.global_mean = self._load('global_mean.pkl')
        self.pays_rares = set(self._load('pays_regroupement.pkl'))
        self.outlier_thresholds = self._load('outlier_thresholds.pkl')

    def _load(self, filename: str) -> Any:
        filepath = os.path.join(self.artifacts_dir, filename)
        with open(filepath, 'rb') as f:
            return pickle.load(f)

    def preprocess(self, contrat_data: Dict[str, Any]) -> np.ndarray:
        """Preprocess un seul contrat et retourne le vecteur de 32 features.

        Applique dans l'ordre :
        1. Variables dérivées (si absentes)
        2. Conversion numérique (correction virgule décimale)
        3. Nettoyage PROFESSION
        4. Capping des outliers (seuils appris sur le train)
        5. Imputation
        6. Feature engineering (nb_profils_actifs, contrat_recent, groupes avenant)
        7. Label encoding, regroupement pays, tranche d'âge, one-hot
        8. Target encoding (PRODUIT + 6 groupes avenant), frequency encoding
        9. Normalisation
        10. Sélection et ordonnancement des 32 features

        Args:
            contrat_data: Dict avec les données brutes d'un contrat.

        Returns:
            numpy array 1D avec les features dans l'ordre attendu par le modèle.
        """
        if isinstance(contrat_data, pd.DataFrame):
            df = contrat_data.copy()
        else:
            df = pd.DataFrame([contrat_data])

        df.columns = [col.lower() for col in df.columns]

        df = self._fix_decimal_and_numeric(df)
        df = self._compute_derived_variables(df)
        df = self._clean_profession(df)
        df = self._cap_outliers(df)
        df = self._impute(df)
        df = self._feature_engineering(df)
        df = self._label_encode(df)
        df = self._regroup_pays(df)
        df = self._tranche_age(df)
        df = self._onehot_encode(df)
        df = self._target_encode(df)
        df = self._frequency_encode(df)
        df = self._normalize(df)

        vector = self._select_features(df)
        return vector

    def preprocess_to_dataframe(self, contrat_data: Dict[str, Any]) -> pd.DataFrame:
        """Même chose que preprocess() mais retourne un DataFrame (utile pour SHAP)."""
        vector = self.preprocess(contrat_data)
        return pd.DataFrame([vector], columns=self.features_list)

    # ------------------------------------------------------------------
    # Étapes du pipeline
    # ------------------------------------------------------------------

    def _compute_derived_variables(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcule les variables dérivées si elles ne sont pas déjà présentes."""
        if 'ratio_rachats_primes' not in df.columns:
            if 'total_primes' in df.columns and 'total_rachats' in df.columns:
                total_primes = df['total_primes'].iloc[0]
                total_rachats = df['total_rachats'].iloc[0]
                df['ratio_rachats_primes'] = (
                    total_rachats / total_primes if pd.notna(total_primes) and float(total_primes) > 0 else 0
                )
            else:
                df['ratio_rachats_primes'] = 0

        if 'ratio_arbitre_primes' not in df.columns:
            if 'total_primes' in df.columns and 'total_arbitre' in df.columns:
                total_primes = df['total_primes'].iloc[0]
                total_arbitre = df['total_arbitre'].iloc[0]
                df['ratio_arbitre_primes'] = (
                    total_arbitre / total_primes if pd.notna(total_primes) and float(total_primes) > 0 else 0
                )
            else:
                df['ratio_arbitre_primes'] = 0

        if 'age_souscripteur' not in df.columns:
            if 'date_naissance_temp' in df.columns and 'date_effet' in df.columns:
                try:
                    date_naissance = pd.to_datetime(df['date_naissance_temp'].iloc[0])
                    date_effet = pd.to_datetime(df['date_effet'].iloc[0])
                    if pd.notna(date_naissance) and pd.notna(date_effet):
                        df['age_souscripteur'] = int((date_effet - date_naissance).days / 365.25)
                    else:
                        df['age_souscripteur'] = None
                except Exception:
                    df['age_souscripteur'] = None
            else:
                df['age_souscripteur'] = None

        return df

    def _fix_decimal_and_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        """Corrige les virgules décimales françaises et force le type numérique.

        cf. save_preprocessing_artifacts.py section 2 : bug découvert dans le
        notebook original (pd.to_numeric direct sans remplacer la virgule).
        """
        numeric_cols = [
            'total_primes', 'total_rachats', 'total_arbitre', 'nb_mouvements',
            'ratio_rachats_primes', 'ratio_arbitre_primes', 'age_souscripteur',
            'duree_annees', 'duree_mois',
        ]
        for col in numeric_cols:
            if col not in df.columns:
                continue
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.strip().str.replace(',', '.', regex=False)
                df[col] = df[col].replace({'': np.nan, 'nan': np.nan})
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df

    def _clean_profession(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'profession' in df.columns:
            df['profession'] = df['profession'].apply(normalize_profession)
        return df

    def _cap_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applique les mêmes seuils de capping que ceux appris sur le train."""
        th = self.outlier_thresholds

        if 'total_primes' in df.columns:
            df['total_primes'] = df['total_primes'].clip(upper=th['q99_total_primes'])

        if 'total_rachats' in df.columns:
            df['total_rachats'] = df['total_rachats'].abs().clip(upper=th['q99_total_rachats'])

        if 'age_souscripteur' in df.columns:
            age = df['age_souscripteur'].iloc[0]
            if pd.isna(age) or age <= 0 or age > 100:
                df['age_souscripteur'] = th['median_age_valide']

        # Recalcul des ratios après capping
        if 'total_primes' in df.columns and 'total_rachats' in df.columns:
            total_primes = df['total_primes'].iloc[0]
            if pd.notna(total_primes) and total_primes > 0:
                df['ratio_rachats_primes'] = round(df['total_rachats'].iloc[0] / total_primes, 4)
            else:
                df['ratio_rachats_primes'] = 0

        if 'total_primes' in df.columns and 'total_arbitre' in df.columns:
            total_primes = df['total_primes'].iloc[0]
            if pd.notna(total_primes) and total_primes > 0:
                df['ratio_arbitre_primes'] = round(df['total_arbitre'].iloc[0] / total_primes, 4)
            else:
                df['ratio_arbitre_primes'] = 0

        return df

    def _impute(self, df: pd.DataFrame) -> pd.DataFrame:
        categorical_cols = ['produit', 'nature_produit', 'sexe', 'profession',
                            'code_postal', 'pays', 'profils_actifs',
                            'avenant_1_motif', 'avenant_2_motif', 'avenant_3_motif',
                            'avenant_4_motif', 'avenant_5_motif', 'avenant_6_motif']

        for col in categorical_cols:
            if col in df.columns:
                if df[col].isnull().any():
                    fill_val = 'AUCUN' if 'avenant' in col else 'INCONNU'
                    df[col] = df[col].fillna(fill_val)

        for col, median_val in self.medianes.items():
            if col in df.columns and df[col].isnull().any():
                df[col] = df[col].fillna(median_val)

        return df

    def _feature_engineering(self, df: pd.DataFrame) -> pd.DataFrame:
        # nb_profils_actifs
        if 'profils_actifs' in df.columns:
            val = str(df['profils_actifs'].iloc[0])
            if val not in ('INCONNU', 'nan', 'None', ''):
                df['nb_profils_actifs'] = len(val.split(','))
            else:
                df['nb_profils_actifs'] = 0
        else:
            df['nb_profils_actifs'] = 0

        # contrat_recent (< 2 ans d'ancienneté)
        if 'date_effet' in df.columns:
            try:
                date_effet = pd.to_datetime(df['date_effet'].iloc[0], errors='coerce')
                if pd.notna(date_effet):
                    anciennete_jours = (pd.Timestamp.now() - date_effet).days
                else:
                    anciennete_jours = 0
            except Exception:
                anciennete_jours = 0
        else:
            anciennete_jours = 0
        df['contrat_recent'] = int(anciennete_jours < 730)

        # Regroupement des motifs d'avenant par catégorie de risque métier
        avenant_motif_cols = [f'avenant_{i}_motif' for i in range(1, 7) if f'avenant_{i}_motif' in df.columns]
        for col in avenant_motif_cols:
            df[col + '_groupe'] = df[col].apply(grouper_motif)

        return df

    def _label_encode(self, df: pd.DataFrame) -> pd.DataFrame:
        for col, class_to_idx in self.label_encoders.items():
            if col in df.columns:
                val = str(df[col].iloc[0])
                if val in class_to_idx:
                    df[col + '_encoded'] = class_to_idx[val]
                else:
                    logger.warning(f"Label encoding: valeur '{val}' inconnue pour {col}")
                    df[col + '_encoded'] = 0
        return df

    def _regroup_pays(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'pays' in df.columns:
            val = df['pays'].iloc[0]
            if val in self.pays_rares:
                df['pays'] = 'AUTRE'
        return df

    def _tranche_age(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'age_souscripteur' in df.columns:
            age = df['age_souscripteur'].iloc[0]
            if pd.notna(age):
                if age < 30:
                    tranche = '<30'
                elif age < 40:
                    tranche = '30-40'
                elif age < 50:
                    tranche = '40-50'
                elif age < 60:
                    tranche = '50-60'
                elif age < 70:
                    tranche = '60-70'
                else:
                    tranche = '>70'
            else:
                tranche = 'INCONNU'
            df['tranche_age'] = tranche
        return df

    def _onehot_encode(self, df: pd.DataFrame) -> pd.DataFrame:
        for col, categories in self.onehot_categories.items():
            if col in df.columns:
                val = df[col].iloc[0]
                for cat in categories[1:]:  # drop_first (même ordre qu'au fit)
                    col_name = f"{col}_{cat}"
                    df[col_name] = 1 if val == cat else 0
            else:
                for cat in categories[1:]:
                    col_name = f"{col}_{cat}"
                    df[col_name] = 0
        return df

    def _target_encode(self, df: pd.DataFrame) -> pd.DataFrame:
        """Target encoding sur PRODUIT + les 6 groupes de motif d'avenant (option C)."""
        for col, encoding_map in self.target_encodings.items():
            source_col = col  # ex: 'produit' ou 'avenant_1_motif_groupe'
            if source_col in df.columns:
                val = df[source_col].iloc[0]
                encoded_val = encoding_map.get(val, self.global_mean)
                df[col + '_target_encoded'] = encoded_val
            else:
                df[col + '_target_encoded'] = self.global_mean
        return df

    def _frequency_encode(self, df: pd.DataFrame) -> pd.DataFrame:
        """Frequency encoding sur les motifs d'avenant bruts (anti-leakage sur avenant_1)."""
        if 'avenant_1_motif' in df.columns and df['avenant_1_motif'].iloc[0] == 'RESIL':
            df['avenant_1_motif'] = 'AUCUN'

        for col, freq_map in self.frequency_encodings.items():
            if col in df.columns:
                val = df[col].iloc[0]
                encoded_val = freq_map.get(val, 0.0)
                df[col + '_freq'] = encoded_val
            else:
                df[col + '_freq'] = 0.0
        return df

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        for i, col in enumerate(self.scaler_columns):
            if col in df.columns:
                raw_val = df[col].iloc[0]
                try:
                    val = float(raw_val)
                except (TypeError, ValueError):
                    val = 0.0
                df[col + '_scaled'] = (val - self.scaler_mean[i]) / self.scaler_scale[i]
            else:
                df[col + '_scaled'] = 0.0
        return df

    def _select_features(self, df: pd.DataFrame) -> np.ndarray:
        vector = []
        for feature in self.features_list:
            if feature in df.columns:
                val = df[feature].iloc[0]
                if pd.isna(val):
                    val = 0.0
                vector.append(float(val))
            else:
                logger.warning(f"Feature manquante: {feature}, valeur 0 utilisée")
                vector.append(0.0)
        return np.array(vector)

    def get_features_list(self) -> List[str]:
        return self.features_list.copy()

    def get_info(self) -> Dict[str, Any]:
        return {
            'artifacts_dir': self.artifacts_dir,
            'nb_features': len(self.features_list),
            'scaler_columns': self.scaler_columns,
            'target_encoding_vars': list(self.target_encodings.keys()),
            'frequency_encoding_vars': list(self.frequency_encodings.keys()),
            'label_encoding_vars': list(self.label_encoders.keys()),
            'onehot_vars': list(self.onehot_categories.keys()),
            'global_mean': self.global_mean,
            'outlier_thresholds': self.outlier_thresholds,
        }


# ============================================================================
# TEST STANDALONE
# ============================================================================
if __name__ == "__main__":
    print("Test du RealtimePreprocessor (option C)")
    print("=" * 60)

    artifacts_dir = 'artifacts'
    if not os.path.exists(artifacts_dir):
        print(f"✗ Dossier '{artifacts_dir}' introuvable.")
        print("  Exécutez d'abord: python save_preprocessing_artifacts.py")
        raise SystemExit(1)

    preprocessor = RealtimePreprocessor(artifacts_dir)
    info = preprocessor.get_info()

    print(f"✓ Preprocessor chargé")
    print(f"  - {info['nb_features']} features attendues")
    print(f"  - Scaler sur: {info['scaler_columns']}")
    print(f"  - Target encoding: {info['target_encoding_vars']}")
    print(f"  - Frequency encoding: {info['frequency_encoding_vars']}")
    print(f"  - Moyenne globale cible: {info['global_mean']:.4f}")
    print(f"  - Seuils outliers: {info['outlier_thresholds']}")

    print("\nTest avec un contrat fictif (virgule décimale française)...")
    contrat_test = {
        'contrat_id': 'TEST001',
        'etat_contrat': 'V',
        'variable_cible': 0,
        'date_effet': '2018-03-15',
        'date_resiliation': None,
        'date_echeance': '2026-03-15',
        'duree_annees': 8,
        'duree_mois': 96,
        'produit': 'MULTIS',
        'nature_produit': 'AV',
        'multi_profils': '1',
        'profils_actifs': 'EUR,UC1',
        'total_primes': '50000,0',
        'total_rachats': '5000,0',
        'total_arbitre': '12000,0',
        'nb_mouvements': 15,
        'sexe': 'M',
        'profession': 'Médecin généraliste',
        'code_postal': '75008',
        'pays': 'F',
        'date_naissance_temp': '1968-05-20',
        'avenant_1_motif': 'ARS',
        'avenant_1_date': '2023-11-01',
        'avenant_2_motif': 'VPR',
        'avenant_2_date': '2022-06-15',
        'avenant_3_motif': 'AUCUN',
        'avenant_3_date': None,
        'avenant_4_motif': 'AUCUN',
        'avenant_4_date': None,
        'avenant_5_motif': 'AUCUN',
        'avenant_5_date': None,
        'avenant_6_motif': 'AUCUN',
        'avenant_6_date': None,
    }

    try:
        vector = preprocessor.preprocess(contrat_test)
        print(f"  ✓ Vecteur de features généré: {len(vector)} valeurs")
        print(f"  ✓ Shape: {vector.shape}")
        print(f"  ✓ Premières valeurs: {vector[:5]}")
        print(f"  ✓ Pas de NaN: {not np.isnan(vector).any()}")
        assert len(vector) == len(preprocessor.get_features_list()), "Taille du vecteur incohérente"
        print("  ✓ Taille du vecteur cohérente avec features_list")
    except Exception as e:
        print(f"  ✗ Erreur: {e}")
        raise
