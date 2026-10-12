-- ============================================================================
-- Script de création des tables optimisées pour le scoring résiliation V3
-- Exécuter dans une SQL Window Oracle (SQL Developer, TOAD, PL/SQL Developer)
-- 
-- CORRECTIONS ANTI DATA-LEAKAGE par rapport à V2 :
-- 1. Mouvements : exclusion des rachats totaux (RCT) du total_rachats et nb_mouvements
-- 2. Avenants : exclusion du dernier avenant (RESIL) pour les résiliés
--    → avenant_1 = dernier avenant AVANT la résiliation
-- 3. Les colonnes date_resiliation, etat_contrat, duree_avant_resiliation,
--    resiliation_precoce sont conservées pour l'exploration/visualisation
--    mais NE DOIVENT PAS être passées au modèle ML
--
-- Tables créées :
-- 1. DATASET_SCORING_RESIL_V3 : Dataset de base anti-leakage
-- 2. DATASET_SCORING_ENRICHI_V3 : Dataset avec variables dérivées
-- ============================================================================

-- ============================================================================
-- ÉTAPE 1 : Suppression des tables si elles existent déjà
-- ============================================================================
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE DATASET_SCORING_ENRICHI_V3';
EXCEPTION
    WHEN OTHERS THEN NULL;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE DATASET_SCORING_RESIL_V3';
EXCEPTION
    WHEN OTHERS THEN NULL;
END;
/

-- ============================================================================
-- ÉTAPE 2 : Création de la table de base V3 (anti-leakage)
-- ============================================================================
CREATE TABLE DATASET_SCORING_RESIL_V3 AS
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
-- CORRECTION V3 : Exclusion des rachats totaux (RCT) pour éviter le leakage
--   - total_rachats : ne compte que les rachats partiels
--   - nb_mouvements : exclut les mouvements de type RCT
-- ============================================================================
mouvements_agg AS (
    SELECT
        m.MVT_N_CONTRAT                                                         AS contrat_id,
        SUM(CASE WHEN m.MVT_CATEGORIE_MOUVEMENT = 'P'
                 THEN m.MVT_MONTANT_INVESTISSEMENT ELSE 0 END)                  AS total_primes,
        -- V3 : Rachats PARTIELS uniquement (exclure RCT = rachat total)
        SUM(CASE WHEN m.MVT_CATEGORIE_MOUVEMENT = 'R'
                      AND m.MVT_ACTE_GESTION != 'RCT'
                 THEN m.MVT_MONTANT_INVESTISSEMENT ELSE 0 END)                  AS total_rachats_partiels,
        -- V3 : Total arbitré (proxy du PM — montant total des arbitrages)
        SUM(CASE WHEN m.MVT_ACTE_GESTION IN ('ARA','ARI','ARS','ARV','ABR','AGM','APR','ALK')
                 THEN m.MVT_MONTANT_INVESTISSEMENT ELSE 0 END)                  AS total_arbitre,
        -- V3 : Comptage hors rachats totaux
        SUM(CASE WHEN m.MVT_ACTE_GESTION != 'RCT' THEN 1 ELSE 0 END)           AS nb_mouvements
    FROM MOUVEMENT m
    GROUP BY m.MVT_N_CONTRAT
),

-- ============================================================================
-- CTE 4 : derniers_avenants
-- Récupère les 6 derniers avenants de chaque contrat (motif + date)
-- CORRECTION V3 : Pour les résiliés, on exclut le dernier avenant (RESIL)
--   en filtrant rn >= 2 quand le motif du rn=1 est 'RESIL'
--   → avenant_1 = dernier avenant AVANT la résiliation
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
            -- V3 : ROW_NUMBER après exclusion de RESIL
            -- Donc rn=1 = dernier avenant AVANT la résiliation
            ROW_NUMBER() OVER (
                PARTITION BY CNT_CONTRAT 
                ORDER BY CNT_AVENANT DESC
            ) AS rn
        FROM CONTRAT
        WHERE CNT_MOTIF_AVENANT != 'RESIL'  -- V3 : Exclure l'avenant de résiliation
    )
    WHERE rn <= 6
    GROUP BY CNT_CONTRAT
)

-- ============================================================================
-- Requête principale : Dataset V3 anti-leakage
-- ============================================================================
SELECT
    -- ========================================================================
    -- Identification & variable cible
    -- ========================================================================
    cb.contrat_id,
    cb.etat_contrat,          -- ⚠️ NE PAS passer au modèle (= variable_cible)
    cb.variable_cible,
    
    -- ========================================================================
    -- Variables temporelles
    -- ========================================================================
    cb.date_effet,
    cb.date_resiliation,      -- ⚠️ NE PAS passer au modèle (garder pour visu)
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
    -- Variables financières (CORRIGÉES V3 : sans rachat total + arbitrages)
    -- ========================================================================
    COALESCE(ma.total_primes, 0)                AS total_primes,
    COALESCE(ma.total_rachats_partiels, 0)      AS total_rachats,
    COALESCE(ma.total_arbitre, 0)               AS total_arbitre,
    COALESCE(ma.nb_mouvements, 0)               AS nb_mouvements,
    
    -- ========================================================================
    -- Caractéristiques tiers (souscripteur)
    -- ========================================================================
    pp.P_P_SEXE                                 AS sexe,
    pp.P_P_PROFESSION                           AS profession,
    adr.ADR_CODE_POSTAL                         AS code_postal,
    adr.ADR_PAYS                                AS pays,
    
    -- Date de naissance (pour calcul age, sera exclue du modèle)
    pp.P_P_DATE_NAISSANCE                       AS date_naissance_temp,
    
    -- ========================================================================
    -- Historique : 6 derniers avenants AVANT la résiliation (CORRIGÉ V3)
    -- Pour les résiliés : exclut l'avenant RESIL
    -- avenant_1 = le plus récent AVANT la résiliation
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
CREATE TABLE DATASET_SCORING_ENRICHI_V3 AS
SELECT
    -- Colonnes de base
    d.contrat_id,
    d.etat_contrat,           -- ⚠️ NE PAS passer au modèle
    d.variable_cible,
    d.date_effet,
    d.date_resiliation,       -- ⚠️ NE PAS passer au modèle
    d.date_echeance,
    d.duree_annees,
    d.duree_mois,
    d.produit,
    d.nature_produit,
    d.multi_profils,
    d.profils_actifs,
    d.total_primes,
    d.total_rachats,
    d.total_arbitre,
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

    -- Ratio rachats partiels / primes (NULL si aucune prime)
    -- V3 : basé sur rachats PARTIELS (sans rachat total)
    CASE
        WHEN d.total_primes > 0
        THEN ROUND(d.total_rachats / d.total_primes, 4)
        ELSE NULL
    END AS ratio_rachats_primes,

    -- Ratio arbitrages / primes investies (proxy du PM)
    -- V3 : combien a été arbitré par rapport à ce qui a été versé
    CASE
        WHEN d.total_primes > 0
        THEN ROUND(d.total_arbitre / d.total_primes, 4)
        ELSE NULL
    END AS ratio_arbitre_primes,

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

    -- ========================================================================
    -- Variables d'exploration UNIQUEMENT (⚠️ NE PAS passer au modèle)
    -- Conservées pour visualisation et analyse post-hoc
    -- ========================================================================

    -- Durée avant résiliation en jours (NULL si non résilié)
    CASE
        WHEN d.variable_cible = 1 AND d.date_resiliation IS NOT NULL
        THEN TRUNC(d.date_resiliation) - TRUNC(d.date_effet)
        ELSE NULL
    END AS duree_avant_resiliation_jours,   -- ⚠️ NE PAS passer au modèle

    -- Durée avant résiliation en mois (NULL si non résilié)
    CASE
        WHEN d.variable_cible = 1 AND d.date_resiliation IS NOT NULL
        THEN MONTHS_BETWEEN(TRUNC(d.date_resiliation), TRUNC(d.date_effet))
        ELSE NULL
    END AS duree_avant_resiliation_mois,    -- ⚠️ NE PAS passer au modèle

    -- Résiliation précoce (1 si < 365 jours, 0 sinon, NULL si non résilié)
    CASE
        WHEN d.variable_cible = 1 AND d.date_resiliation IS NOT NULL
        THEN CASE
                WHEN (TRUNC(d.date_resiliation) - TRUNC(d.date_effet)) < 365
                THEN 1
                ELSE 0
             END
        ELSE NULL
    END AS resiliation_precoce             -- ⚠️ NE PAS passer au modèle

FROM DATASET_SCORING_RESIL_V3 d
;

-- ============================================================================
-- ÉTAPE 4 : Création des index
-- ============================================================================
CREATE INDEX IDX_SCORING_V3_CONTRAT ON DATASET_SCORING_RESIL_V3(contrat_id);
CREATE INDEX IDX_SCORING_V3_CIBLE ON DATASET_SCORING_RESIL_V3(variable_cible);
CREATE INDEX IDX_SCORING_V3_NATURE ON DATASET_SCORING_RESIL_V3(nature_produit);

CREATE INDEX IDX_SCORING_ENRICHI_V3_CONTRAT ON DATASET_SCORING_ENRICHI_V3(contrat_id);
CREATE INDEX IDX_SCORING_ENRICHI_V3_CIBLE ON DATASET_SCORING_ENRICHI_V3(variable_cible);

-- ============================================================================
-- ÉTAPE 5 : Vérifications
-- ============================================================================

-- Nombre de lignes
SELECT 'DATASET_SCORING_RESIL_V3' AS table_name, COUNT(*) AS nb_lignes FROM DATASET_SCORING_RESIL_V3
UNION ALL
SELECT 'DATASET_SCORING_ENRICHI_V3', COUNT(*) FROM DATASET_SCORING_ENRICHI_V3;

-- Distribution de la variable cible
SELECT 
    variable_cible,
    CASE WHEN variable_cible = 1 THEN 'Résilié' ELSE 'En vigueur' END AS statut,
    COUNT(*) AS nb_contrats,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pourcentage
FROM DATASET_SCORING_RESIL_V3
GROUP BY variable_cible
ORDER BY variable_cible;

-- Vérification anti-leakage : avenant_1_motif ne doit JAMAIS être 'RESIL'
SELECT 
    CASE 
        WHEN COUNT(*) = 0 THEN 'OK - Aucun avenant RESIL dans avenant_1_motif'
        ELSE 'ERREUR - ' || COUNT(*) || ' contrats avec RESIL en avenant_1 !'
    END AS verification_leakage_avenants
FROM DATASET_SCORING_RESIL_V3
WHERE avenant_1_motif = 'RESIL';

-- Vérification : aucun contrat RC
SELECT 
    CASE 
        WHEN COUNT(*) = 0 THEN 'OK - Aucun contrat RC présent'
        ELSE 'ERREUR - ' || COUNT(*) || ' contrats RC trouvés !'
    END AS verification_exclusion_rc
FROM DATASET_SCORING_RESIL_V3
WHERE nature_produit = 'RC';

-- Statistiques financières (vérifier que total_rachats ne contient plus les rachats totaux)
SELECT 
    variable_cible,
    COUNT(*) AS nb_contrats,
    ROUND(AVG(total_rachats), 2) AS moy_rachats_partiels,
    ROUND(AVG(total_primes), 2) AS moy_primes,
    ROUND(AVG(nb_mouvements), 1) AS moy_nb_mouvements
FROM DATASET_SCORING_RESIL_V3
GROUP BY variable_cible
ORDER BY variable_cible;

-- Distribution des motifs du premier avenant (doit être diversifié, pas juste RESIL)
SELECT 
    avenant_1_motif,
    COUNT(*) AS nb,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM DATASET_SCORING_RESIL_V3
WHERE avenant_1_motif IS NOT NULL
GROUP BY avenant_1_motif
ORDER BY nb DESC
FETCH FIRST 15 ROWS ONLY;

-- Aperçu
SELECT * FROM DATASET_SCORING_ENRICHI_V3 WHERE ROWNUM <= 5;

-- ============================================================================
-- RAPPEL : Colonnes à NE PAS passer au modèle ML
-- (garder pour exploration/visualisation uniquement)
-- ============================================================================
-- contrat_id              → identifiant
-- etat_contrat            → encode la variable cible
-- date_resiliation        → NULL/rempli encode la cible
-- date_naissance_temp     → utilisé uniquement pour calculer age_souscripteur
-- duree_avant_resiliation_jours  → n'existe que pour résiliés
-- duree_avant_resiliation_mois   → n'existe que pour résiliés
-- resiliation_precoce     → dérivé de date_resiliation
--
-- FEATURES POUR LE MODÈLE (clean, sans leakage) :
-- date_effet, date_echeance, duree_annees, duree_mois
-- produit, nature_produit, multi_profils, profils_actifs
-- total_primes, total_rachats (partiels), total_arbitre, nb_mouvements (hors RCT)
-- sexe, profession, code_postal, pays
-- avenant_1 à avenant_6 (motif + date) — AVANT la résiliation
-- ratio_rachats_primes, ratio_arbitre_primes, age_souscripteur, mois_effet, annee_effet
-- ============================================================================
