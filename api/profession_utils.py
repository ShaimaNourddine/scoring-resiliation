"""
Nettoyage de la variable PROFESSION
====================================

Module partagé (source unique), reproduit fidèlement la cellule de
normalisation présente dans le notebook réel (C:\\Users\\SBenNourddin\\preprocessing.ipynb) :
normalisation Unicode (accents supprimés, majuscules) puis regroupement de
quelques variantes orthographiques fréquentes.

Utilisé par :
  - save_preprocessing_artifacts.py
  - realtime_preprocessor.py
  - scoring_batch_timer.py
"""

import unicodedata

import pandas as pd

PROFESSION_MAPPING = {
    '': 'INCONNU', '.': 'INCONNU', 'NON RENSEIGNE': 'INCONNU',
    'RETRAITES': 'RETRAITE', 'RETRAITEE': 'RETRAITE', 'RETRAITEES': 'RETRAITE',
    'ETUDIANTE': 'ETUDIANT', 'ETUDIANTES': 'ETUDIANT', 'ETUDIANTS': 'ETUDIANT',
    'SANS PROFESSION': 'SANS ACTIVITE',
}


def normalize_profession(x):
    """Normalise une valeur brute de PROFESSION.

    - NaN → 'INCONNU'
    - Sinon : strip + upper + suppression des accents (NFD) + regroupement
      des variantes orthographiques fréquentes (cf. PROFESSION_MAPPING).
    """
    if pd.isna(x):
        return 'INCONNU'
    x = str(x).strip().upper()
    x = ''.join(c for c in unicodedata.normalize('NFD', x)
                if unicodedata.category(c) != 'Mn')
    return PROFESSION_MAPPING.get(x, x)
