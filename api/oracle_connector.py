"""
Module de connexion Oracle pour le scoring résiliation
=======================================================

Fournit :
- Connexion à la base Oracle (oracledb)
- Requête pour récupérer les données brutes d'un seul contrat
- Requête pour récupérer tout le portefeuille (batch)
- Requête de rafraîchissement de DATASET_SCORING_ENRICHI_V3

Configuration Oracle :
    Host: 172.25.72.29
    Port: 1522
    Service: MSCFO2D1.LDSA.COM
    User: d_fortis

Prérequis:
    pip install oracledb
"""

import oracledb
import pandas as pd
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION ORACLE
# Lues depuis les variables d'environnement (Docker / .env)
# Fallback sur les valeurs de développement local si non définies
# ============================================================================
import os as _os_oracle
ORACLE_CONFIG = {
    'user':         _os_oracle.environ.get('ORACLE_USER',         'd_fortis'),
    'password':     _os_oracle.environ.get('ORACLE_PASSWORD',     'd_fortis'),
    'host':         _os_oracle.environ.get('ORACLE_HOST',         '172.25.72.29'),
    'port':         int(_os_oracle.environ.get('ORACLE_PORT',     '1522')),
    'service_name': _os_oracle.environ.get('ORACLE_SERVICE',      'MSCFO2D1.LDSA.COM'),
}

# Chemin vers le client Oracle Instant Client
# En mode thin (oracledb >= 1.0), aucun client Oracle n'est requis.
# ORACLE_CLIENT_LIB est conservé pour la compatibilité avec le mode thick
# (Windows local uniquement). Dans le container Docker, on reste en mode thin.
import os as _os_connector
ORACLE_CLIENT_LIB = _os_connector.environ.get(
    "ORACLE_CLIENT_LIB",
    r"C:\oracle\instantclient-basiclite-windows.x64-23.26.1.0.0\instantclient_23_0"
)

# Initialisation du client Oracle (une seule fois)
_client_initialized = False


def _init_oracle_client():
    """Initialise le client Oracle (une seule fois au premier appel)."""
    global _client_initialized
    if not _client_initialized:
        try:
            oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_LIB)
            _client_initialized = True
            logger.info("Oracle client initialisé")
        except Exception as e:
            # Déjà initialisé ou erreur
            if "already been called" in str(e).lower():
                _client_initialized = True
            else:
                logger.error(f"Erreur initialisation Oracle client: {e}")
                raise


@contextmanager
def get_connection():
    """Context manager pour une connexion Oracle.
    
    Usage:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
    """
    _init_oracle_client()
    conn = None
    try:
        conn = oracledb.connect(
            user=ORACLE_CONFIG['user'],
            password=ORACLE_CONFIG['password'],
            host=ORACLE_CONFIG['host'],
            port=ORACLE_CONFIG['port'],
            service_name=ORACLE_CONFIG['service_name']
        )
        yield conn
    finally:
        if conn:
            conn.close()


# ============================================================================
# REQUÊTE POUR UN SEUL CONTRAT (données brutes depuis tables sources)
# ============================================================================

# Requête identique à create_tables_scoring_v3.sql mais filtrée par contrat_id
QUERY_SINGLE_CONTRAT = """
WITH
contrats_base AS (
    SELECT
        c.CNT_CONTRAT                                           AS contrat_id,
        c.CNT_ETAT_CONTRAT                                      AS etat_contrat,
        CASE WHEN c.CNT_ETAT_CONTRAT = 'A' THEN 1 ELSE 0 END  AS variable_cible,
        c.CNT_DATE_EFFET_CONTRAT                                AS date_effet,
        c.CNT_DATE_RESILIATION                                  AS date_resiliation,
        c.CNT_ECHEANCE_CONTRAT                                  AS date_echeance,
        c.CNT_DUREE                                             AS duree_annees,
        c.CNT_DUREE_MOIS                                        AS duree_mois,
        c.CNT_PRODUIT                                           AS produit,
        p.PRD_NATURE_PRODUIT                                    AS nature_produit,
        p.PRD_MULTI_PROFILS                                     AS multi_profils,
        c.CNT_SOUSCRIPTEUR                                      AS souscripteur_id
    FROM CONTRAT c
    INNER JOIN PRODUITS p ON c.CNT_PRODUIT = p.PRD_CODE_PRODUIT
    WHERE c.CNT_DERNIER_AVT_O_N = 'O'
      AND c.CNT_ETAT_CONTRAT IN ('V', 'A')
      AND (c.CNT_ETAT_CONTRAT = 'V'
           OR (c.CNT_ETAT_CONTRAT = 'A' AND c.CNT_MOTIF_AVENANT = 'RESIL'))
      AND p.PRD_NATURE_PRODUIT != 'RC'
      AND c.CNT_CONTRAT = :contrat_id
),
profils_actifs AS (
    SELECT
        cp.CNP_CONTRAT AS contrat_id,
        LISTAGG(cp.CNP_PROFIL, ',') WITHIN GROUP (ORDER BY cp.CNP_PROFIL) AS profils_actifs
    FROM CNT_PROFILS cp
    INNER JOIN CONTRAT c ON cp.CNP_CONTRAT = c.CNT_CONTRAT AND cp.CNP_AVENANT = c.CNT_AVENANT
    WHERE c.CNT_DERNIER_AVT_O_N = 'O'
      AND cp.CNP_POURCENTAGE > 0
      AND cp.CNP_CONTRAT = :contrat_id
    GROUP BY cp.CNP_CONTRAT
),
mouvements_agg AS (
    SELECT
        m.MVT_N_CONTRAT AS contrat_id,
        SUM(CASE WHEN m.MVT_CATEGORIE_MOUVEMENT = 'P'
                 THEN m.MVT_MONTANT_INVESTISSEMENT ELSE 0 END) AS total_primes,
        SUM(CASE WHEN m.MVT_CATEGORIE_MOUVEMENT = 'R'
                      AND m.MVT_ACTE_GESTION != 'RCT'
                 THEN m.MVT_MONTANT_INVESTISSEMENT ELSE 0 END) AS total_rachats,
        SUM(CASE WHEN m.MVT_ACTE_GESTION IN ('ARA','ARI','ARS','ARV','ABR','AGM','APR','ALK')
                 THEN m.MVT_MONTANT_INVESTISSEMENT ELSE 0 END) AS total_arbitre,
        SUM(CASE WHEN m.MVT_ACTE_GESTION != 'RCT' THEN 1 ELSE 0 END) AS nb_mouvements
    FROM MOUVEMENT m
    WHERE m.MVT_N_CONTRAT = :contrat_id
    GROUP BY m.MVT_N_CONTRAT
),
derniers_avenants AS (
    SELECT
        CNT_CONTRAT,
        MAX(CASE WHEN rn = 1 THEN CNT_MOTIF_AVENANT END) AS avenant_1_motif,
        MAX(CASE WHEN rn = 1 THEN CNT_DATE_EFFET_AVT END) AS avenant_1_date,
        MAX(CASE WHEN rn = 2 THEN CNT_MOTIF_AVENANT END) AS avenant_2_motif,
        MAX(CASE WHEN rn = 2 THEN CNT_DATE_EFFET_AVT END) AS avenant_2_date,
        MAX(CASE WHEN rn = 3 THEN CNT_MOTIF_AVENANT END) AS avenant_3_motif,
        MAX(CASE WHEN rn = 3 THEN CNT_DATE_EFFET_AVT END) AS avenant_3_date,
        MAX(CASE WHEN rn = 4 THEN CNT_MOTIF_AVENANT END) AS avenant_4_motif,
        MAX(CASE WHEN rn = 4 THEN CNT_DATE_EFFET_AVT END) AS avenant_4_date,
        MAX(CASE WHEN rn = 5 THEN CNT_MOTIF_AVENANT END) AS avenant_5_motif,
        MAX(CASE WHEN rn = 5 THEN CNT_DATE_EFFET_AVT END) AS avenant_5_date,
        MAX(CASE WHEN rn = 6 THEN CNT_MOTIF_AVENANT END) AS avenant_6_motif,
        MAX(CASE WHEN rn = 6 THEN CNT_DATE_EFFET_AVT END) AS avenant_6_date
    FROM (
        SELECT
            CNT_CONTRAT, CNT_MOTIF_AVENANT, CNT_DATE_EFFET_AVT,
            ROW_NUMBER() OVER (PARTITION BY CNT_CONTRAT ORDER BY CNT_AVENANT DESC) AS rn
        FROM CONTRAT
        WHERE CNT_MOTIF_AVENANT != 'RESIL'
          AND CNT_CONTRAT = :contrat_id
    )
    WHERE rn <= 6
    GROUP BY CNT_CONTRAT
)
SELECT
    cb.contrat_id,
    cb.etat_contrat,
    cb.variable_cible,
    cb.date_effet,
    cb.date_resiliation,
    cb.date_echeance,
    cb.duree_annees,
    cb.duree_mois,
    cb.produit,
    cb.nature_produit,
    cb.multi_profils,
    pa.profils_actifs,
    COALESCE(ma.total_primes, 0) AS total_primes,
    COALESCE(ma.total_rachats, 0) AS total_rachats,
    COALESCE(ma.total_arbitre, 0) AS total_arbitre,
    COALESCE(ma.nb_mouvements, 0) AS nb_mouvements,
    pp.P_P_SEXE AS sexe,
    pp.P_P_PROFESSION AS profession,
    adr.ADR_CODE_POSTAL AS code_postal,
    adr.ADR_PAYS AS pays,
    pp.P_P_DATE_NAISSANCE AS date_naissance_temp,
    avt.avenant_1_motif, avt.avenant_1_date,
    avt.avenant_2_motif, avt.avenant_2_date,
    avt.avenant_3_motif, avt.avenant_3_date,
    avt.avenant_4_motif, avt.avenant_4_date,
    avt.avenant_5_motif, avt.avenant_5_date,
    avt.avenant_6_motif, avt.avenant_6_date
FROM contrats_base cb
LEFT JOIN profils_actifs pa ON cb.contrat_id = pa.contrat_id
LEFT JOIN mouvements_agg ma ON cb.contrat_id = ma.contrat_id
LEFT JOIN derniers_avenants avt ON cb.contrat_id = avt.CNT_CONTRAT
LEFT JOIN PERSONNES_PHYSIQUES pp ON cb.souscripteur_id = pp.P_P_TIERS
LEFT JOIN ADRESSES adr ON pp.P_P_TIERS = adr.ADR_TIERS
                       AND pp.P_P_ADRESSE_PRINCIPALE = adr.ADR_ADRESSE
"""

# ============================================================================
# REQUÊTE DEPUIS LA TABLE ENRICHIE (fallback rapide)
# ============================================================================
QUERY_FROM_ENRICHI = """
SELECT * FROM DATASET_SCORING_ENRICHI_V3
WHERE contrat_id = :contrat_id
"""

# ============================================================================
# REQUÊTE DEPUIS LA TABLE PREPROCESSED (données déjà prêtes)
# ============================================================================
# Le nom de colonne est encadré de guillemets doubles : la table a été
# créée avec des identifiants en minuscules (export pandas/Python), que
# Oracle stocke littéralement. Sans guillemets, Oracle met le nom en
# majuscules et la requête échoue avec ORA-00904 "CONTRAT_ID": invalid
# identifier — erreur jusqu'ici avalée par le try/except appelant, qui
# rendait ce fallback systématiquement inopérant.
QUERY_FROM_PREPROCESSED = """
SELECT * FROM DATASET_SCORING_PREPROCESSED
WHERE "contrat_id" = :contrat_id
"""


# ============================================================================
# FONCTIONS PUBLIQUES
# ============================================================================

def get_contrat_brut(contrat_id: str) -> Optional[pd.DataFrame]:
    """Récupère les données brutes d'un contrat depuis les tables sources.
    
    Exécute la requête V3 complète (jointures CONTRAT, MOUVEMENT, etc.)
    filtrée sur un seul contrat. Données 100% à jour.
    
    Args:
        contrat_id: Numéro du contrat (ex: '12345678')
    
    Returns:
        DataFrame avec 1 ligne contenant les données brutes du contrat,
        ou None si le contrat n'existe pas / n'est pas éligible.
    """
    try:
        with get_connection() as conn:
            df = pd.read_sql(
                QUERY_SINGLE_CONTRAT,
                conn,
                params={'contrat_id': contrat_id}
            )
            
            if df.empty:
                logger.warning(f"Contrat {contrat_id} non trouvé dans les tables sources")
                return None
            
            # Convertir les noms de colonnes en minuscules (Oracle retourne en majuscules)
            df.columns = [col.lower() for col in df.columns]
            
            logger.info(f"Contrat {contrat_id} récupéré depuis les tables sources")
            return df
            
    except Exception as e:
        logger.error(f"Erreur requête contrat brut {contrat_id}: {e}")
        raise


def get_contrat_enrichi(contrat_id: str) -> Optional[pd.DataFrame]:
    """Récupère un contrat depuis DATASET_SCORING_ENRICHI_V3.
    
    Plus rapide que get_contrat_brut() mais peut dater du dernier batch.
    
    Args:
        contrat_id: Numéro du contrat
    
    Returns:
        DataFrame avec 1 ligne, ou None si non trouvé.
    """
    try:
        with get_connection() as conn:
            df = pd.read_sql(
                QUERY_FROM_ENRICHI,
                conn,
                params={'contrat_id': contrat_id}
            )
            
            if df.empty:
                return None
            
            df.columns = [col.lower() for col in df.columns]
            return df
            
    except Exception as e:
        logger.error(f"Erreur requête contrat enrichi {contrat_id}: {e}")
        raise


def get_contrat_preprocessed(contrat_id: str) -> Optional[pd.DataFrame]:
    """Récupère un contrat depuis DATASET_SCORING_PREPROCESSED.
    
    Données déjà preprocessed, prêtes à passer au modèle directement.
    Utile comme fallback rapide si les artefacts ne sont pas disponibles.
    
    Args:
        contrat_id: Numéro du contrat
    
    Returns:
        DataFrame avec 1 ligne, ou None si non trouvé.
    """
    try:
        with get_connection() as conn:
            df = pd.read_sql(
                QUERY_FROM_PREPROCESSED,
                conn,
                params={'contrat_id': contrat_id}
            )
            
            if df.empty:
                return None

            # Pas de passage en minuscules ici : trois features du modèle
            # portent des majuscules significatives (nature_produit_AV,
            # nature_produit_BC, pays_F) et seraient rendues introuvables.
            # La correspondance avec les noms attendus par le modèle est
            # faite par extraire_features().
            return df

    except Exception as e:
        logger.error(f"Erreur requête contrat preprocessed {contrat_id}: {e}")
        raise


def get_all_contrats_preprocessed() -> pd.DataFrame:
    """Récupère tout le portefeuille depuis DATASET_SCORING_PREPROCESSED.

    Données déjà preprocessed pour l'ensemble des contrats, prêtes à
    passer au modèle directement (vectorisé, sans boucle). Utilisé par
    l'endpoint /predict_batch pour scorer tout le portefeuille en un
    seul appel.

    Returns:
        DataFrame avec une ligne par contrat.
    """
    try:
        with get_connection() as conn:
            df = pd.read_sql(
                "SELECT * FROM DATASET_SCORING_PREPROCESSED",
                conn
            )
            # Noms de colonnes conservés tels quels (cf. remarque dans
            # get_contrat_preprocessed) : la correspondance avec les
            # features du modèle est faite par extraire_features().
            logger.info(f"Portefeuille preprocessed chargé: {len(df)} contrats")
            return df

    except Exception as e:
        logger.error(f"Erreur chargement portefeuille preprocessed: {e}")
        raise


# ============================================================================
# CORRESPONDANCE COLONNES ORACLE <-> FEATURES DU MODÈLE
# ============================================================================
# La table DATASET_SCORING_PREPROCESSED a été alimentée par un import
# Python (import_preprocessed.py) qui altère les noms de colonnes de
# trois façons, et Oracle en ajoute une quatrième :
#
#   1. '-' remplacé par '_'        : tranche_age_30-40 -> tranche_age_30_40
#   2. '>' remplacé par 'SUP'      : tranche_age_>70   -> tranche_age_SUP70
#   3. '<' remplacé par 'INF'
#   4. troncature à 30 caractères  : avenant_1_motif_groupe_target_encoded
#                                    -> avenant_1_motif_groupe_target_
#
# Résoudre ces écarts explicitement évite le piège d'un reindex() avec
# fill_value=0, qui remplaçait silencieusement par des zéros les features
# non retrouvées et faussait les scores sans lever la moindre erreur.
ORACLE_MAX_IDENTIFIER_LENGTH = 30


def _variantes_nom(feature: str):
    """Génère les noms possibles d'une feature dans la table Oracle."""
    transforme = feature.replace("-", "_").replace(">", "SUP").replace("<", "INF")
    return [
        feature,
        transforme,
        transforme[:ORACLE_MAX_IDENTIFIER_LENGTH],
    ]


def resoudre_colonnes(features_list, colonnes_table) -> Dict[str, str]:
    """Associe chaque feature du modèle à son nom de colonne réel.

    La recherche est tentée d'abord à la casse exacte, puis en
    insensible à la casse, sur chacune des variantes de nom possibles.

    Args:
        features_list: Noms des features attendus par le modèle.
        colonnes_table: Noms de colonnes réellement présents dans la table.

    Returns:
        Dict {nom_feature: nom_colonne_reel}.

    Raises:
        ValueError: si au moins une feature reste introuvable. Mieux vaut
            refuser de scorer que produire un score calculé sur des zéros.
    """
    exact = {c: c for c in colonnes_table}
    insensible = {c.lower(): c for c in colonnes_table}

    correspondance: Dict[str, str] = {}
    introuvables = []

    for feature in features_list:
        trouve = None
        for variante in _variantes_nom(feature):
            if variante in exact:
                trouve = exact[variante]
                break
            if variante.lower() in insensible:
                trouve = insensible[variante.lower()]
                break
        if trouve is None:
            introuvables.append(feature)
        else:
            correspondance[feature] = trouve

    if introuvables:
        raise ValueError(
            "Features du modèle introuvables dans "
            f"DATASET_SCORING_PREPROCESSED : {introuvables}. "
            "Scoring interrompu : des features manquantes produiraient "
            "un score erroné. Vérifier que la table a été alimentée avec "
            "le dataset preprocessed courant (32 features)."
        )

    return correspondance


def extraire_features(df: pd.DataFrame, features_list) -> pd.DataFrame:
    """Extrait les features du modèle d'un DataFrame lu dans la table.

    Les colonnes sont sélectionnées via resoudre_colonnes(), renommées
    vers les noms attendus par le modèle, et ordonnées comme
    features_list.

    Args:
        df: DataFrame issu de get_contrat_preprocessed() ou
            get_all_contrats_preprocessed(), noms de colonnes bruts.
        features_list: Noms et ordre des features attendus par le modèle.

    Returns:
        DataFrame avec exactement les colonnes de features_list.

    Raises:
        ValueError: si une feature est introuvable (cf. resoudre_colonnes).
    """
    correspondance = resoudre_colonnes(features_list, list(df.columns))
    colonnes_source = [correspondance[f] for f in features_list]
    extrait = df[colonnes_source].copy()
    extrait.columns = list(features_list)
    return extrait.fillna(0)


def get_all_contrats_enrichis() -> pd.DataFrame:
    """Récupère tout le portefeuille depuis DATASET_SCORING_ENRICHI_V3.
    
    Utilisé par le batch mensuel pour preprocessing complet.
    
    Returns:
        DataFrame avec tout le portefeuille.
    """
    try:
        with get_connection() as conn:
            df = pd.read_sql(
                "SELECT * FROM DATASET_SCORING_ENRICHI_V3",
                conn
            )
            df.columns = [col.lower() for col in df.columns]
            logger.info(f"Portefeuille chargé: {len(df)} contrats")
            return df
            
    except Exception as e:
        logger.error(f"Erreur chargement portefeuille: {e}")
        raise


def refresh_enrichi_table(sql_script_path: str = None) -> bool:
    """Rafraîchit DATASET_SCORING_ENRICHI_V3 en ré-exécutant le SQL V3.
    
    Supprime et recrée la table à partir des tables sources.
    
    Args:
        sql_script_path: Chemin vers le fichier SQL (optionnel, utilise le SQL inline sinon)
    
    Returns:
        True si succès, False sinon.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Drop table existante
            try:
                cursor.execute("DROP TABLE DATASET_SCORING_ENRICHI_V3")
                logger.info("Table DATASET_SCORING_ENRICHI_V3 supprimée")
            except Exception:
                pass  # Table n'existait pas
            
            # Si un fichier SQL est fourni, le lire
            if sql_script_path:
                with open(sql_script_path, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
                # Extraire uniquement le CREATE TABLE DATASET_SCORING_ENRICHI_V3
                # (le script contient aussi d'autres instructions)
                # Pour simplifier, on exécute la partie enrichie
                statements = sql_content.split(';')
                for stmt in statements:
                    stmt = stmt.strip()
                    if stmt and 'DATASET_SCORING_ENRICHI_V3' in stmt and 'CREATE' in stmt.upper():
                        cursor.execute(stmt)
                        break
            
            conn.commit()
            
            # Vérification
            cursor.execute("SELECT COUNT(*) FROM DATASET_SCORING_ENRICHI_V3")
            count = cursor.fetchone()[0]
            logger.info(f"Table DATASET_SCORING_ENRICHI_V3 rafraîchie: {count} lignes")
            
            cursor.close()
            return True
            
    except Exception as e:
        logger.error(f"Erreur rafraîchissement table enrichie: {e}")
        return False


def import_preprocessed_to_oracle(df: pd.DataFrame, table_name: str = 'DATASET_SCORING_PREPROCESSED') -> bool:
    """Importe un DataFrame preprocessed dans Oracle.
    
    Supprime la table existante et la recrée avec les données.
    
    Args:
        df: DataFrame preprocessed à importer
        table_name: Nom de la table cible
    
    Returns:
        True si succès, False sinon.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Drop table existante
            try:
                cursor.execute(f"DROP TABLE {table_name}")
            except Exception:
                pass
            
            # Nettoyer les NaN et booléens
            df = df.fillna(0)
            for col in df.columns:
                if df[col].dtype == bool:
                    df[col] = df[col].astype(int)
            
            # Créer la table
            col_defs = []
            for col in df.columns:
                col_name = col.replace("-", "_").replace(">", "SUP").replace("<", "INF")
                # Oracle 12c limite les identifiants à 30 caractères
                col_name = col_name[:30]
                if df[col].dtype in ['int64', 'int32']:
                    col_defs.append(f'"{col_name}" NUMBER')
                elif df[col].dtype in ['float64', 'float32']:
                    col_defs.append(f'"{col_name}" NUMBER')
                else:
                    col_defs.append(f'"{col_name}" VARCHAR2(200)')
            
            create_sql = f"CREATE TABLE {table_name} ({', '.join(col_defs)})"
            cursor.execute(create_sql)
            
            # Renommer les colonnes du DataFrame
            df.columns = [col.replace("-", "_").replace(">", "SUP").replace("<", "INF")[:30] for col in df.columns]
            
            # Insertion par batch
            batch_size = 1000
            placeholders = ", ".join([f":{i+1}" for i in range(len(df.columns))])
            insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders})"
            
            total_inserted = 0
            for start in range(0, len(df), batch_size):
                batch = df.iloc[start:start + batch_size]
                rows = [tuple(row) for _, row in batch.iterrows()]
                cursor.executemany(insert_sql, rows)
                total_inserted += len(rows)
            
            conn.commit()
            cursor.close()
            
            logger.info(f"Table {table_name} importée: {total_inserted} lignes")
            return True
            
    except Exception as e:
        logger.error(f"Erreur import dans Oracle: {e}")
        return False


def test_connection() -> Dict[str, Any]:
    """Teste la connexion Oracle et retourne des infos.
    
    Returns:
        Dict avec status, version Oracle, nombre de contrats dans les tables.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Version Oracle
            cursor.execute("SELECT * FROM V$VERSION WHERE ROWNUM = 1")
            version = cursor.fetchone()[0]
            
            # Comptage tables
            counts = {}
            for table in ['DATASET_SCORING_ENRICHI_V3', 'DATASET_SCORING_PREPROCESSED']:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    counts[table] = cursor.fetchone()[0]
                except Exception:
                    counts[table] = None
            
            cursor.close()
            
            return {
                'status': 'connected',
                'oracle_version': version,
                'tables': counts
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# ============================================================================
# MAIN (pour test direct)
# ============================================================================
if __name__ == "__main__":
    print("Test de connexion Oracle...")
    result = test_connection()
    
    if result['status'] == 'connected':
        print(f"✓ Connexion OK")
        print(f"  Version: {result['oracle_version']}")
        print(f"  Tables:")
        for table, count in result['tables'].items():
            if count is not None:
                print(f"    - {table}: {count:,} lignes")
            else:
                print(f"    - {table}: N/A (table inexistante)")
    else:
        print(f"✗ Erreur: {result['error']}")
