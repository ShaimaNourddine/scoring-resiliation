"""
Regroupement des motifs d'avenant par catégorie de risque métier
==================================================================

Module partagé (source unique) utilisé par :
  - save_preprocessing_artifacts.py (génération des artefacts + dataset d'entraînement)
  - realtime_preprocessor.py (scoring temps réel d'un seul contrat)
  - scoring_batch_timer.py (scoring batch mensuel du portefeuille)

Contexte : cf. AUDIT_TARGET_ENCODING_AVENANTS.md. Le target encoding des motifs
d'avenant bruts (~50-60 codes par variable) est statistiquement instable
(catégories trop peu peuplées). Le regroupement en 8-9 catégories de risque
homogènes stabilise l'encodage tout en préservant le sens métier de
l'historique comportemental des 6 derniers avenants (option C, 32 features,
AUC nested CV = 0.9454).
"""

MOTIF_GROUPS = {
    # Risque élevé : sorties définitives
    'RESIL': 'RISQUE_ELEVE', 'REN': 'RISQUE_ELEVE', 'DECES': 'RISQUE_ELEVE',
    'DC1ER': 'RISQUE_ELEVE', 'ADC1ER': 'RISQUE_ELEVE', 'RPR': 'RISQUE_ELEVE',
    'RRP': 'RISQUE_ELEVE', 'RECHRP': 'RISQUE_ELEVE', 'RAA': 'RISQUE_ELEVE',
    'RESGAR': 'RISQUE_ELEVE',
    # Arrêt / annulation d'opérations automatiques
    'ARP': 'ARRET_ANNULATION', 'ARRARL': 'ARRET_ANNULATION', 'ARRASL': 'ARRET_ANNULATION',
    'ARRAPV': 'ARRET_ANNULATION', 'ARRARE': 'ARRET_ANNULATION', 'ARRGDE': 'ARRET_ANNULATION',
    'ANALK': 'ARRET_ANNULATION', 'ANARS': 'ARRET_ANNULATION', 'ANAPR': 'ARRET_ANNULATION',
    'ANNARL': 'ARRET_ANNULATION',
    # Arbitrage entre supports
    'ARA': 'ARBITRAGE', 'ARI': 'ARBITRAGE', 'ARS': 'ARBITRAGE', 'ARV': 'ARBITRAGE',
    'ACA': 'ARBITRAGE', 'ABR': 'ARBITRAGE', 'AGM': 'ARBITRAGE', 'APR': 'ARBITRAGE',
    'ALK': 'ARBITRAGE', 'CORTAR': 'ARBITRAGE', 'EDR': 'ARBITRAGE',
    # Versement programmé
    'VPR': 'VERSEMENT', 'MVP': 'VERSEMENT', 'MODAPV': 'VERSEMENT',
    # Modification administrative
    'PRO': 'MODIF_ADMIN', 'PROFIN': 'MODIF_ADMIN', 'CADFIS': 'MODIF_ADMIN',
    'CLBENF': 'MODIF_ADMIN', 'PAYEUR': 'MODIF_ADMIN', 'MODADS': 'MODIF_ADMIN',
    'USUPRO': 'MODIF_ADMIN',
    # Création d'opérations automatiques
    'CRTARL': 'CREATION_AUTO', 'CRTASL': 'CREATION_AUTO', 'CRTAPV': 'CREATION_AUTO',
    'CRTARE': 'CREATION_AUTO', 'CRTGDE': 'CREATION_AUTO',
    # Avenant technique
    'AOT': 'TECHNIQUE', 'ACN': 'TECHNIQUE', 'ACR': 'TECHNIQUE', 'ACOMBT': 'TECHNIQUE',
    'SCHEMC': 'TECHNIQUE', 'DFS': 'TECHNIQUE', 'MER': 'TECHNIQUE',
}


def grouper_motif(motif):
    """Regroupe un motif d'avenant brut en catégorie de risque métier.

    Args:
        motif: code motif brut (ex: 'ARS', 'RESIL', 'PRO'...), ou NaN/vide/'AUCUN'.

    Returns:
        'AUCUN' si pas d'avenant, sinon le groupe de risque, ou 'AUTRE' si le
        code n'est pas répertorié dans MOTIF_GROUPS.
    """
    if motif is None:
        return 'AUCUN'
    try:
        import pandas as pd
        if pd.isna(motif):
            return 'AUCUN'
    except Exception:
        pass
    motif = str(motif).strip()
    if motif == '' or motif.upper() == 'AUCUN' or motif.lower() == 'nan':
        return 'AUCUN'
    return MOTIF_GROUPS.get(motif.upper(), 'AUTRE')
