-- ============================================================================
-- Script de création des tables optimisées pour le scoring résiliation V2
-- Exécuter dans une SQL Window Oracle (SQL Developer, TOAD, PL/SQL Developer)
-- 
-- Ce script crée 2 tables :
-- 1. DATASET_SCORING_RESIL_V2 : Dataset optimisé avec colonnes sélectionnées + 6 derniers avenants
-- 2. DATASET_SCORING_ENRICHI_V2 : Dataset avec variables dérivées
--
-- Colonnes conservées :
-- - Variables temporelles (dates, durées, saisonnalité)
-- - Type de contrat (produit, nature, profils)
-- - Variables financières (primes, rachats, ratio, nb mouvements)
-- - Caractéristiques tiers (âge, sexe, adresse, profession)
-- - Historique : 6 derniers avenants (motif + date)
-- ============================================================================

-- ============================================================================
-- ÉTAPE 1 : Suppression des tables si elles existent déjà
-- ============================================================================
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE DATASET_SCORING_ENRICHI_V2';
EXCEPTION
    WHEN OTHERS THEN NULL;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE DATASET_SCORING_RESIL_V2';
EXCEPTION
    WHEN OTHERS THEN NULL;
END;
/

-- ============================================================================
-- ÉTAPE 2 : Création de la table optimisée
-- ============================================================================
CREATE TABLE DATASET_SCORING_RESIL_V2 AS
WITH
-- ============================================================================
-- CTE 1 : contrats_base
-- Filtre les contrats éligibles et exclut les contrats RC
-- ============================================================================
contrats_base AS (
    SELECT
        c.CNT_CONTRAT                                           AS contrat_id,
        c.CNT_ETAT_CONTRAT                                      AS etat_contrat,
        CASE WHEN c.CNT_ETAT_CONTRAT = 'A' THEN 1 ELSE 0 END  AS variable_cible,
        
        -- Variables temporelles
        c.CNT_DATE_EFFET_CONTRAT                                AS date_effet,
        c.CNT_DATE_RESILIATION                                  AS date_resiliation,
        c.CNT_ECHEANCE_CONTRAT                                  AS date_echeance,
        c.CNT_DUREE                                             AS duree_annees,
        c.CNT_DUREE_MOIS                                        AS duree_mois,
        
        -- Variables produit
        c.CNT_PRODUIT                                           AS produit,
        p.PRD_NATURE_PRODUIT                                    AS nature_produit,
        p.PRD_MULTI_PROFILS                                     AS multi_profils,
        
        -- Identifiant souscripteur (pour jointure)
        c.CNT_SOUSCRIPTEUR                                      AS souscripteur_id
        
    FROM CONTRAT c
    INNER JOIN PRODUITS p
        ON c.CNT_PRODUIT = p.PRD_CODE_PRODUIT
    WHERE c.CNT_DERNIER_AVT_O_N = 'O'
      AND c.CNT_ETAT_CONTRAT IN ('V', 'A')
      AND (   c.CNT_ETAT_CONTRAT = 'V'
           OR (c.CNT_ETAT_CONTRAT = 'A' AND c.CNT_MOTIF_AVENANT = 'RESIL'))
      AND p.PRD_NATURE_PRODUIT != 'RC'
),

-- ============================================================================
-- CTE 2 : profils_actifs
-- Concatène tous les profils actifs depuis CNT_PROFILS
-- ============================================================================
profils_actifs AS (
    SELECT
        cp.CNP_CONTRAT                          AS contrat_id,
        LISTAGG(cp.CNP_PROFIL, ',') 
            WITHIN GROUP (ORDER BY cp.CNP_PROFIL) AS profils_actifs
    FROM CNT_PROFILS cp
    INNER JOIN CONTRAT c
        ON cp.CNP_CONTRAT = c.CNT_CONTRAT
        AND cp.CNP_AVENANT = c.CNT_AVENANT
    WHERE c.CNT_DERNIER_AVT_O_N = 'O'
      AND cp.CNP_POURCENTAGE > 0
    GROUP BY cp.CNP_CONTRAT
),

-- ============================================================================
-- CTE 3 : mouvements_agg
-- Agrège les mouvements financiers par contrat
-- ============================================================================
mouvements_agg AS (
    SELECT
        m.MVT_N_CONTRAT                                                         AS contrat_id,
        SUM(CASE WHEN m.MVT_CATEGORIE_MOUVEMENT = 'P'
                 THEN m.MVT_MONTANT_INVESTISSEMENT ELSE 0 END)                  AS total_primes,
        SUM(CASE WHEN m.MVT_CATEGORIE_MOUVEMENT = 'R'
                 THEN m.MVT_MONTANT_INVESTISSEMENT ELSE 0 END)                  AS total_rachats,
        COUNT(*)                                                                AS nb_mouvements
    FROM MOUVEMENT m
    GROUP BY m.MVT_N_CONTRAT
),

-- ============================================================================
-- CTE 4 : derniers_avenants
-- Récupère les 6 derniers avenants de chaque contrat (motif + date)
-- ============================================================================
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
            CNT_CONTRAT,
            CNT_MOTIF_AVENANT,
            CNT_DATE_EFFET_AVT,
            ROW_NUMBER() OVER (PARTITION BY CNT_CONTRAT ORDER BY CNT_AVENANT DESC) AS rn
        FROM CONTRAT
    )
    WHERE rn <= 6
    GROUP BY CNT_CONTRAT
)

-- ============================================================================
-- Requête principale : Dataset optimisé V2
-- ============================================================================
SELECT
    -- Identification & variable cible
    cb.contrat_id,
    cb.etat_contrat,
    cb.variable_cible,
    
    -- ========================================================================
    -- Variables temporelles
    -- ========================================================================
    cb.date_effet,
    -- Pour les contrats résiliés, utiliser la date du dernier avenant si date_resiliation est NULL
    CASE 
        WHEN cb.variable_cible = 1 AND cb.date_resiliation IS NULL 
        THEN avt.avenant_1_date
        ELSE cb.date_resiliation
    END AS date_resiliation,
    cb.date_echeance,
    cb.duree_annees,
    cb.duree_mois,
    
    -- ========================================================================
    -- Type de contrat
    -- ========================================================================
    cb.produit,
    cb.nature_produit,
    cb.multi_profils,
    pa.profils_actifs,
    
    -- ========================================================================
    -- Variables financières
    -- ========================================================================
    COALESCE(ma.total_primes, 0)                AS total_primes,
    COALESCE(ma.total_rachats, 0)               AS total_rachats,
    COALESCE(ma.nb_mouvements, 0)               AS nb_mouvements,
    
    -- ========================================================================
    -- Caractéristiques tiers (souscripteur)
    -- ========================================================================
    pp.P_P_SEXE                                 AS sexe,
    pp.P_P_PROFESSION                           AS profession,
    adr.ADR_CODE_POSTAL                         AS code_postal,
    adr.ADR_PAYS                                AS pays,
    
    -- Date de naissance (utilisée uniquement pour calculer l'âge, sera supprimée après)
    pp.P_P_DATE_NAISSANCE                       AS date_naissance_temp,
    
    -- ========================================================================
    -- Historique : 6 derniers avenants
    -- ========================================================================
    avt.avenant_1_motif,
    avt.avenant_1_date,
    avt.avenant_2_motif,
    avt.avenant_2_date,
    avt.avenant_3_motif,
    avt.avenant_3_date,
    avt.avenant_4_motif,
    avt.avenant_4_date,
    avt.avenant_5_motif,
    avt.avenant_5_date,
    avt.avenant_6_motif,
    avt.avenant_6_date

FROM contrats_base cb
LEFT JOIN profils_actifs pa ON cb.contrat_id = pa.contrat_id
LEFT JOIN mouvements_agg ma ON cb.contrat_id = ma.contrat_id
LEFT JOIN derniers_avenants avt ON cb.contrat_id = avt.CNT_CONTRAT
LEFT JOIN PERSONNES_PHYSIQUES pp ON cb.souscripteur_id = pp.P_P_TIERS
LEFT JOIN ADRESSES adr ON pp.P_P_TIERS = adr.ADR_TIERS
                       AND pp.P_P_ADRESSE_PRINCIPALE = adr.ADR_ADRESSE
;

-- ============================================================================
-- ÉTAPE 3 : Création de la table enrichie avec variables dérivées
-- ============================================================================
CREATE TABLE DATASET_SCORING_ENRICHI_V2 AS
SELECT
    -- Sélection de toutes les colonnes sauf date_naissance_temp
    d.contrat_id,
    d.etat_contrat,
    d.variable_cible,
    d.date_effet,
    d.date_resiliation,
    d.date_echeance,
    d.duree_annees,
    d.duree_mois,
    d.produit,
    d.nature_produit,
    d.multi_profils,
    d.profils_actifs,
    d.total_primes,
    d.total_rachats,
    d.nb_mouvements,
    d.sexe,
    d.profession,
    d.code_postal,
    d.pays,
    d.avenant_1_motif,
    d.avenant_1_date,
    d.avenant_2_motif,
    d.avenant_2_date,
    d.avenant_3_motif,
    d.avenant_3_date,
    d.avenant_4_motif,
    d.avenant_4_date,
    d.avenant_5_motif,
    d.avenant_5_date,
    d.avenant_6_motif,
    d.avenant_6_date,

    -- ========================================================================
    -- Variables dérivées — Feature Engineering
    -- ========================================================================

    -- Ratio rachats / primes (NULL si aucune prime)
    CASE
        WHEN d.total_primes > 0
        THEN ROUND(d.total_rachats / d.total_primes, 4)
        ELSE NULL
    END AS ratio_rachats_primes,

    -- Âge du souscripteur à la date d'effet du contrat (en années)
    CASE
        WHEN d.date_naissance_temp IS NOT NULL AND d.date_effet IS NOT NULL
        THEN TRUNC(MONTHS_BETWEEN(TRUNC(d.date_effet), TRUNC(d.date_naissance_temp)) / 12)
        ELSE NULL
    END AS age_souscripteur,

    -- Mois d'effet (saisonnalité)
    EXTRACT(MONTH FROM d.date_effet) AS mois_effet,

    -- Année d'effet
    EXTRACT(YEAR FROM d.date_effet) AS annee_effet,

    -- Durée avant résiliation en jours (NULL si non résilié)
    CASE
        WHEN d.variable_cible = 1 AND d.date_resiliation IS NOT NULL
        THEN TRUNC(d.date_resiliation) - TRUNC(d.date_effet)
        ELSE NULL
    END AS duree_avant_resiliation_jours,

    -- Durée avant résiliation en mois (NULL si non résilié)
    CASE
        WHEN d.variable_cible = 1 AND d.date_resiliation IS NOT NULL
        THEN MONTHS_BETWEEN(TRUNC(d.date_resiliation), TRUNC(d.date_effet))
        ELSE NULL
    END AS duree_avant_resiliation_mois,

    -- Résiliation précoce (1 si < 365 jours, 0 sinon, NULL si non résilié)
    CASE
        WHEN d.variable_cible = 1 AND d.date_resiliation IS NOT NULL
        THEN CASE
                WHEN (TRUNC(d.date_resiliation) - TRUNC(d.date_effet)) < 365
                THEN 1
                ELSE 0
             END
        ELSE NULL
    END AS resiliation_precoce

FROM DATASET_SCORING_RESIL_V2 d
;

-- ============================================================================
-- ÉTAPE 4 : Création des index pour améliorer les performances
-- ============================================================================
CREATE INDEX IDX_SCORING_V2_CONTRAT ON DATASET_SCORING_RESIL_V2(contrat_id);
CREATE INDEX IDX_SCORING_V2_CIBLE ON DATASET_SCORING_RESIL_V2(variable_cible);
CREATE INDEX IDX_SCORING_V2_NATURE ON DATASET_SCORING_RESIL_V2(nature_produit);

CREATE INDEX IDX_SCORING_ENRICHI_V2_CONTRAT ON DATASET_SCORING_ENRICHI_V2(contrat_id);
CREATE INDEX IDX_SCORING_ENRICHI_V2_CIBLE ON DATASET_SCORING_ENRICHI_V2(variable_cible);

-- ============================================================================
-- ÉTAPE 5 : Statistiques et vérifications
-- ============================================================================

-- Nombre de lignes par table
SELECT 'DATASET_SCORING_RESIL_V2' AS table_name, COUNT(*) AS nb_lignes FROM DATASET_SCORING_RESIL_V2
UNION ALL
SELECT 'DATASET_SCORING_ENRICHI_V2', COUNT(*) FROM DATASET_SCORING_ENRICHI_V2;

-- Distribution de la variable cible
SELECT 
    variable_cible,
    CASE WHEN variable_cible = 1 THEN 'Résilié' ELSE 'En vigueur' END as statut,
    COUNT(*) as nb_contrats,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pourcentage
FROM DATASET_SCORING_RESIL_V2
GROUP BY variable_cible
ORDER BY variable_cible;

-- Vérification : aucun contrat RC ne doit être présent
SELECT 
    CASE 
        WHEN COUNT(*) = 0 THEN 'OK - Aucun contrat RC présent'
        ELSE 'ERREUR - ' || COUNT(*) || ' contrats RC trouvés !'
    END as verification_exclusion_rc
FROM DATASET_SCORING_RESIL_V2
WHERE nature_produit = 'RC';

-- Statistiques sur les valeurs NULL
SELECT
    COUNT(*) AS total_contrats,
    SUM(CASE WHEN profession IS NULL THEN 1 ELSE 0 END) AS null_profession,
    SUM(CASE WHEN code_postal IS NULL THEN 1 ELSE 0 END) AS null_code_postal,
    SUM(CASE WHEN profils_actifs IS NULL THEN 1 ELSE 0 END) AS null_profils_actifs
FROM DATASET_SCORING_ENRICHI_V2;

-- Aperçu des premières lignes
SELECT * FROM DATASET_SCORING_RESIL_V2 WHERE ROWNUM <= 5;
