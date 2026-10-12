"""
Diagnostic de l'écart de score entre le scoring individuel et le Dashboard
===========================================================================

Compare, pour un même contrat, les 32 features obtenues par les deux
chemins de données utilisés par l'API :

  Chemin A (scoring individuel, GET /scoring/contrat/{id}) :
      tables sources brutes  ->  RealtimePreprocessor  ->  modèle

  Chemin B (Dashboard et batch, /dashboard/stats, /predict_batch) :
      table DATASET_SCORING_PREPROCESSED  ->  reindex(features_list)  ->  modèle

Objectif : déterminer pourquoi le même contrat obtient deux scores
différents. Deux causes possibles, que ce script distingue explicitement :

  1. Colonnes manquantes dans la table PREPROCESSED. Le reindex utilisé
     par l'API remplit silencieusement à 0 toute feature absente, ce qui
     fausse le score sans lever d'erreur. Le script liste ces colonnes.

  2. Valeurs réellement différentes pour des colonnes présentes des deux
     côtés : la table a alors été générée par une version antérieure du
     preprocessing (avant corrections data leakage / virgule décimale /
     nature_produit AV).

Usage (depuis le dossier api/) :
    python diagnostic_ecart_scoring.py 2427018

Prérequis : mêmes dépendances que l'API (oracledb, pandas, xgboost,
artefacts présents dans api/artifacts/ et best_model_xgboost.pkl).
"""

import glob
import pickle
import sys

import pandas as pd

from oracle_connector import (
    get_connection,
    get_contrat_brut,
    extraire_features,
    resoudre_colonnes,
)
from realtime_preprocessor import RealtimePreprocessor

# Tolérance en dessous de laquelle deux valeurs de features sont
# considérées identiques (évite de signaler du bruit de flottants).
TOLERANCE = 1e-6


def charger_modele():
    """Charge le modèle XGBoost depuis le pickle, comme le fait l'API."""
    pkl_files = sorted(glob.glob("best_model_*.pkl"))
    if not pkl_files:
        raise FileNotFoundError(
            "Aucun fichier best_model_*.pkl trouvé. "
            "Lancer ce script depuis le dossier api/."
        )
    with open(pkl_files[0], "rb") as f:
        modele = pickle.load(f)
    print(f"Modèle chargé : {pkl_files[0]}")
    return modele


def scorer(modele, df_features: pd.DataFrame) -> float:
    """Retourne la probabilité de résiliation pour un DataFrame d'une ligne."""
    return float(modele.predict_proba(df_features)[0][1])


def inspecter_colonnes_table() -> list:
    """Retourne les noms de colonnes réels de DATASET_SCORING_PREPROCESSED.

    Nécessaire car la table peut avoir été créée avec des noms en
    minuscules entre guillemets (cas d'un export pandas.to_sql) : Oracle
    les stocke alors littéralement et un WHERE contrat_id non quoté
    échoue avec ORA-00904.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM DATASET_SCORING_PREPROCESSED WHERE ROWNUM <= 1")
        noms = [d[0] for d in cursor.description]
        cursor.close()
    return noms


def lire_contrat_preprocessed(contrat_id: str, colonne_id: str):
    """Lit un contrat dans la table PREPROCESSED en citant le nom de colonne.

    Le nom est encadré de guillemets doubles pour respecter la casse
    réelle telle que stockée par Oracle.
    """
    requete = (
        f'SELECT * FROM DATASET_SCORING_PREPROCESSED '
        f'WHERE "{colonne_id}" = :contrat_id'
    )
    with get_connection() as conn:
        df = pd.read_sql(requete, conn, params={"contrat_id": contrat_id})
    if df.empty:
        return None
    # Noms de colonnes conservés tels quels : la correspondance avec les
    # features du modèle est faite par extraire_features().
    return df


def classer(score: float) -> str:
    if score >= 0.75:
        return "CRITIQUE"
    if score >= 0.50:
        return "ÉLEVÉ"
    if score >= 0.25:
        return "MOYEN"
    return "FAIBLE"


def main(contrat_id: str) -> int:
    modele = charger_modele()
    preprocessor = RealtimePreprocessor("artifacts")
    features_list = preprocessor.get_features_list()
    print(f"Features attendues par le modèle : {len(features_list)}")
    print(f"Contrat analysé : {contrat_id}")
    print()

    # ------------------------------------------------------------------
    # Chemin A : tables sources + preprocessing temps réel
    # ------------------------------------------------------------------
    print("=" * 78)
    print("CHEMIN A - tables sources brutes + RealtimePreprocessor")
    print("=" * 78)

    df_brut = get_contrat_brut(contrat_id)
    if df_brut is None:
        print("Contrat introuvable dans les tables sources. Chemin A indisponible.")
        features_a = None
        score_a = None
    else:
        print(f"Colonnes brutes récupérées : {len(df_brut.columns)}")
        features_a = preprocessor.preprocess_to_dataframe(df_brut)
        score_a = scorer(modele, features_a)
        print(f"Score : {score_a:.4f}  ->  {classer(score_a)}")
    print()

    # ------------------------------------------------------------------
    # Chemin B : table PREPROCESSED + reindex (logique actuelle du Dashboard)
    # ------------------------------------------------------------------
    print("=" * 78)
    print("CHEMIN B - table DATASET_SCORING_PREPROCESSED + extraire_features")
    print("=" * 78)

    # Inspection des noms de colonnes réels : indispensable pour savoir
    # comment interroger la table (casse exacte).
    noms_reels = inspecter_colonnes_table()
    print(f"Colonnes réelles dans la table : {len(noms_reels)}")

    print()
    print("Noms de colonnes réels de la table :")
    for nom in noms_reels:
        print(f"    {nom}")
    print()

    # Rapprochement via la fonction utilisée par l'API : vérifie que
    # chaque feature du modèle est bien résolue vers une colonne réelle,
    # malgré les renommages de l'import et la troncature Oracle.
    print("Rapprochement features du modèle <-> colonnes de la table :")
    try:
        correspondance = resoudre_colonnes(features_list, noms_reels)
    except ValueError as e:
        print(f"    ÉCHEC : {e}")
        return 1

    nb_renommees = 0
    for feature, colonne in correspondance.items():
        if colonne != feature:
            nb_renommees += 1
            print(f"    {feature}  ->  {colonne!r}")
    print()
    print(f"    résolues à l'identique : {len(correspondance) - nb_renommees}")
    print(f"    résolues par renommage : {nb_renommees}")
    print(f"    introuvables           : 0")
    print()

    candidats_id = [n for n in noms_reels if n.lower() == "contrat_id"]
    if not candidats_id:
        print()
        print("Aucune colonne 'contrat_id' dans la table. Noms réels :")
        for nom in noms_reels:
            print(f"    {nom!r}")
        print()
        print("Chemin B indisponible : impossible d'identifier les contrats.")
        return 1

    colonne_id = candidats_id[0]
    if colonne_id != "CONTRAT_ID":
        print(
            f"Nom de colonne identifiant stocké en casse littérale : {colonne_id!r}"
        )
        print(
            "  -> impose des guillemets doubles dans la clause WHERE, "
            "sinon ORA-00904 (corrigé dans QUERY_FROM_PREPROCESSED)."
        )
    print()

    df_prep = lire_contrat_preprocessed(contrat_id, colonne_id)
    if df_prep is None:
        print("Contrat introuvable dans DATASET_SCORING_PREPROCESSED.")
        print("Chemin B indisponible : la table ne contient pas ce contrat.")
        features_b = None
        score_b = None
        colonnes_manquantes = list(features_list)
    else:
        print(f"Colonnes présentes dans la table : {len(df_prep.columns)}")

        # Extraction via la fonction de l'API : résout les renommages et
        # lève si une feature manque réellement.
        colonnes_manquantes = []
        features_b = extraire_features(df_prep, features_list)
        score_b = scorer(modele, features_b)
        print()
        print(f"Score : {score_b:.4f}  ->  {classer(score_b)}")
    print()

    # ------------------------------------------------------------------
    # Comparaison feature par feature
    # ------------------------------------------------------------------
    if features_a is None or features_b is None:
        print("Comparaison impossible : un des deux chemins n'a pas abouti.")
        return 1

    print("=" * 78)
    print("COMPARAISON FEATURE PAR FEATURE")
    print("=" * 78)
    print(f"{'Feature':<45} {'Chemin A':>13} {'Chemin B':>13}  Écart")
    print("-" * 78)

    manquantes_set = set(colonnes_manquantes)
    diff_absentes = []   # features absentes de la table ET dont la valeur diffère
    diff_presentes = []  # features présentes des deux côtés mais valeurs différentes

    for nom in features_list:
        val_a = float(features_a.iloc[0][nom])
        val_b = float(features_b.iloc[0][nom])
        ecart = abs(val_a - val_b)

        marqueur = ""
        if ecart > TOLERANCE:
            if nom in manquantes_set:
                diff_absentes.append(nom)
                marqueur = "  <-- ABSENTE DE LA TABLE (forcée à 0)"
            else:
                diff_presentes.append(nom)
                marqueur = "  <-- DIFFÈRE"
        print(f"{nom:<45} {val_a:>13.4f} {val_b:>13.4f}{marqueur}")

    nb_differentes = len(diff_absentes) + len(diff_presentes)

    # ------------------------------------------------------------------
    # Synthèse
    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print("SYNTHÈSE")
    print("=" * 78)
    print(f"Features différentes : {nb_differentes} / {len(features_list)}")
    print(f"  absentes de la table et forcées à 0 : {len(diff_absentes)}")
    print(f"  présentes mais valeur différente    : {len(diff_presentes)}")
    print(
        f"Features absentes de la table au total : {len(colonnes_manquantes)} "
        f"(dont {len(colonnes_manquantes) - len(diff_absentes)} dont la vraie "
        f"valeur était déjà 0, donc sans impact)"
    )
    print()
    print(f"Score chemin A (temps réel) : {score_a:.4f}  ->  {classer(score_a)}")
    print(f"Score chemin B (table)      : {score_b:.4f}  ->  {classer(score_b)}")
    print(f"Écart de score              : {abs(score_a - score_b):.4f}")
    print()

    if diff_absentes:
        print("Diagnostic : CAUSE 1 - colonnes manquantes.")
        print(f"{len(diff_absentes)} feature(s) du modèle sont absentes de la table")
        print("PREPROCESSED et forcées à 0 par le reindex, alors que leur vraie")
        print("valeur est non nulle. Le Dashboard score sur des données partielles.")
        if diff_presentes:
            print()
            print(f"S'y ajoute CAUSE 2 : {len(diff_presentes)} feature(s) présentes")
            print("des deux côtés mais avec des valeurs différentes (table périmée).")
        print()
        print("Correction : régénérer la table PREPROCESSED avec le preprocessing")
        print("courant, et faire échouer explicitement le scoring batch quand des")
        print("colonnes manquent, au lieu de les remplir silencieusement à 0.")
    elif diff_presentes:
        print("Diagnostic : CAUSE 2 - table périmée.")
        print("Toutes les features du modèle sont présentes dans la table, mais")
        print(f"{len(diff_presentes)} valeur(s) diffèrent du preprocessing courant.")
        print("La table a été générée par une version antérieure du pipeline")
        print("(avant corrections data leakage / virgule décimale / nature_produit).")
        print()
        print("Correction : régénérer la table PREPROCESSED.")
    else:
        print("Diagnostic : les deux chemins sont alignés.")
        print("Les 32 features et les scores concordent. Si l'application")
        print("affiche malgré tout des valeurs divergentes, la cause est")
        print("ailleurs : cache côté API non rafraîchi, ou API non redémarrée.")

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("Erreur : fournir un numéro de contrat.")
        print("Exemple : python diagnostic_ecart_scoring.py 2427018")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
