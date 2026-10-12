-- ============================================================================
-- Script de création des tables persistées pour le scoring résiliation
-- Exécuter dans une SQL Window Oracle (SQL Developer, TOAD, PL/SQL Developer)
-- 
-- Ce script crée 2 tables :
-- 1. DATASET_SCORING_RESIL : Dataset de base (1 ligne par contrat)
-- 2. DATASET_SCORING_ENRICHI : Dataset avec variables dérivées
--
-- Modifications appliquées :
-- - Exclusion des contrats retraite collectifs (PRD_NATURE_PRODUIT = 'RC')
-- - Profils depuis CNT_PROFILS (plus de CNT_PROFIL)
-- - Ajout de nature_produit et multi_profils
-- ============================================================================

-- ============================================================================
-- ÉTAPE 1 : Suppression des tables si elles existent déjà (pour rafraîchir)
-- ============================================================================
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE DATASET_SCORING_ENRICHI';
EXCEPTION
    WHEN OTHERS THEN NULL;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE DATASET_SCORING_RESIL';
EXCEPTION
    WHEN OTHERS THEN NULL;
END;
/

-- ============================================================================
-- ÉTAPE 2 : Création de la table de base (1 ligne par contrat)
-- Basée sur dataset_scoring_resiliation.sql
-- ============================================================================
CREATE TABLE DATASET_SCORING_RESIL AS
WITH
-- ============================================================================
-- CTE 1 : contrats_base
-- Filtre les contrats éligibles et exclut les contrats RC
-- ============================================================================
contrats_base AS (
    SELECT
        c.CNT_CONTRAT                                           AS contrat_id,
        c.CNT_AVENANT                                           AS avenant,
        c.CNT_ETAT_CONTRAT                                      AS etat_contrat,
        CASE WHEN c.CNT_ETAT_CONTRAT = 'A' THEN 1 ELSE 0 END  AS variable_cible,
        c.CNT_DATE_CREATION                                     AS date_creation,
        c.CNT_DATE_EFFET_CONTRAT                                AS date_effet,
        c.CNT_DATE_RESILIATION                                  AS date_resiliation,
        c.CNT_ECHEANCE_CONTRAT                                  AS date_echeance,
        c.CNT_DATE_EFFET_AVT                                    AS date_effet_avenant,
        c.CNT_DUREE                                             AS duree_annees,
        c.CNT_DUREE_MOIS                                        AS duree_mois,
        c.CNT_PRODUIT                                           AS produit,
        c.CNT_TARIF                                             AS tarif,
        c.CNT_OPTION                                            AS option_contrat,
        c.CNT_CADRE_FISCAL                                      AS cadre_fiscal,
        c.CNT_MODE_REGLEMENT                                    AS mode_reglement,
        c.CNT_CODE_FRACTIONNEMT                                 AS periodicite,
        c.CNT_DEVISE                                            AS devise,
        c.CNT_MOTIF_RESILIATION                                 AS motif_resiliation,
        c.CNT_MOTIF_AVENANT                                     AS motif_avenant,
        c.CNT_VERSEMENT_INITIAL                                 AS versement_initial,
        c.CNT_SOUSCRIPTEUR                                      AS souscripteur_id,
        c.CNT_CPTR_MODIF_ADM                                    AS nb_modif_admin,
        c.POL_EXIST_PRIME                                       AS existe_prime,
        c.POL_EXIST_RAC                                         AS existe_rachat,
        c.POL_EXIST_AVAN                                        AS existe_avance,
        c.POL_EXIST_AVNT                                        AS existe_avenant,
        p.PRD_NATURE_PRODUIT                                    AS nature_produit,
        p.PRD_MULTI_PROFILS                                     AS multi_profils
    FROM CONTRAT c
    INNER JOIN PRODUITS p
        ON c.CNT_PRODUIT = p.PRD_CODE_PRODUIT
    WHERE c.CNT_DERNIER_AVT_O_N = 'O'
      AND c.CNT_ETAT_CONTRAT IN ('V', 'A')
      AND (   c.CNT_ETAT_CONTRAT = 'V'
           OR (c.CNT_ETAT_CONTRAT = 'A' AND c.CNT_MOTIF_AVENANT = 'RESIL'))
      AND p.PRD_NATURE_PRODUIT != 'RC'  -- Exclure les contrats retraite collectifs
),

-- ============================================================================
-- CTE 2 : mouvements_agg
-- Agrège les mouvements financiers par contrat
-- ============================================================================
mouvements_agg AS (
    SELECT
        m.MVT_N_CONTRAT                                                         AS contrat_id,
        SUM(CASE WHEN m.MVT_CATEGORIE_MOUVEMENT = 'P'
                 THEN m.MVT_MONTANT_INVESTISSEMENT ELSE 0 END)                  AS total_primes,
        SUM(CASE WHEN m.MVT_CATEGORIE_MOUVEMENT = 'R'
                 THEN m.MVT_MONTANT_INVESTISSEMENT ELSE 0 END)                  AS total_rachats,
        COUNT(*)                                                                AS nb_mouvements,
        SUM(CASE WHEN m.MVT_MOUVEMENT_ANNULE IS NOT NULL THEN 1 ELSE 0 END)    AS nb_mouvements_annules,
        MIN(m.MVT_DATE_EFFET)                                                   AS date_premier_mouvement,
        MAX(m.MVT_DATE_EFFET)                                                   AS date_dernier_mouvement
    FROM MOUVEMENT m
    GROUP BY m.MVT_N_CONTRAT
),

-- ============================================================================
-- CTE 3 : avenants_par_motif
-- Compte les avenants par catégorie de risque et type d'opération
-- Capture l'historique comportemental complet du contrat
-- ============================================================================
avenants_par_motif AS (
    SELECT
        ca.CNT_CONTRAT                          AS contrat_id,

        -- Risque élevé : sorties définitives du contrat
        COUNT(DISTINCT CASE WHEN ca.CNT_MOTIF_AVENANT IN (
            'RESIL',    -- Résiliation
            'REN',      -- Renonciation
            'DECES',    -- Décès assuré
            'DC1ER',    -- Décès 1er rang
            'ADC1ER',   -- Avenant décès 1er rang
            'RPR',      -- Rachat programmé
            'RRP',      -- Résiliation rachat programmé
            'RECHRP',   -- Réactivation rachat programmé
            'RAA',      -- Rachat automatique avance
            'RESGAR'    -- Résiliation garantie
        ) THEN ca.CNT_AVENANT END)              AS nb_avt_risque_eleve,

        -- Arrêts / annulations d'opérations automatiques
        COUNT(DISTINCT CASE WHEN ca.CNT_MOTIF_AVENANT IN (
            'ARP',      -- Arrêt rachat programmé
            'ARRARL',   -- Arrêt arbitrage auto par durée
            'ARRASL',   -- Arrêt arbitrage auto sur supports
            'ARRAPV',   -- Arrêt arbitrage auto versement
            'ARRARE',   -- Arrêt arbitrage auto revalorisation
            'ARRGDE',   -- Arrêt arbitrage gestion déléguée
            'ANALK',    -- Annulation arbitrage lock
            'ANARS',    -- Annulation arbitrage supports
            'ANAPR',    -- Annulation arbitrage profil
            'ANNARL'    -- Annulation arbitrage auto durée
        ) THEN ca.CNT_AVENANT END)              AS nb_avt_arret_annulation,

        -- Arbitrages (mouvements entre supports)
        COUNT(DISTINCT CASE WHEN ca.CNT_MOTIF_AVENANT IN (
            'ARA',      -- Arbitrage automatique
            'ARI',      -- Arbitrage initial
            'ARS',      -- Arbitrage sur supports
            'ARV',      -- Arbitrage versement
            'ACA',      -- Arbitrage changement allocation
            'ABR',      -- Arbitrage
            'AGM',      -- Arbitrage gestion mandat
            'APR',      -- Arbitrage profil
            'ALK',      -- Arbitrage lock
            'CORTAR',   -- Correction arbitrage
            'EDR'       -- Arbitrage fin affectation provisoire
        ) THEN ca.CNT_AVENANT END)              AS nb_avt_arbitrage,

        -- Versements programmés
        COUNT(DISTINCT CASE WHEN ca.CNT_MOTIF_AVENANT IN (
            'VPR',      -- Versement programmé
            'MVP',      -- Modification versement programmé
            'MODAPV'    -- Modification allocation versement programmé
        ) THEN ca.CNT_AVENANT END)              AS nb_avt_versement,

        -- Modifications administratives / profil
        COUNT(DISTINCT CASE WHEN ca.CNT_MOTIF_AVENANT IN (
            'PRO',      -- Modification profil
            'PROFIN',   -- Profil fin
            'CADFIS',   -- Changement cadre fiscal
            'CLBENF',   -- Changement clause bénéficiaire
            'PAYEUR',   -- Modification tiers payeur
            'MODADS',   -- Modification adresse
            'USUPRO'    -- Usufruit protection
        ) THEN ca.CNT_AVENANT END)              AS nb_avt_modif_admin,

        -- Créations d'opérations automatiques
        COUNT(DISTINCT CASE WHEN ca.CNT_MOTIF_AVENANT IN (
            'CRTARL',   -- Création arbitrage auto durée
            'CRTASL',   -- Création arbitrage auto supports
            'CRTAPV',   -- Création arbitrage auto versement
            'CRTARE',   -- Création arbitrage auto revalorisation
            'CRTGDE'    -- Création arbitrage gestion déléguée
        ) THEN ca.CNT_AVENANT END)              AS nb_avt_creation_auto,

        -- Avenants techniques
        COUNT(DISTINCT CASE WHEN ca.CNT_MOTIF_AVENANT IN (
            'AOT',      -- Avenant technique
            'ACN',      -- Avenant technique
            'ACR',      -- Avenant technique
            'ACOMBT',   -- Avenant technique
            'SCHEMC',   -- Avenant technique
            'DFS',      -- Avenant technique
            'MER'       -- Avenant technique
        ) THEN ca.CNT_AVENANT END)              AS nb_avt_technique,

        -- ----------------------------------------------------------------
        -- Flags binaires (signaux forts individuels)
        -- ----------------------------------------------------------------
        MAX(CASE WHEN ca.CNT_MOTIF_AVENANT = 'RPR'    THEN 1 ELSE 0 END) AS flag_rachat_programme,
        MAX(CASE WHEN ca.CNT_MOTIF_AVENANT = 'REN'    THEN 1 ELSE 0 END) AS flag_renonciation,
        MAX(CASE WHEN ca.CNT_MOTIF_AVENANT IN ('DECES','DC1ER','ADC1ER')
                                                      THEN 1 ELSE 0 END) AS flag_deces,
        MAX(CASE WHEN ca.CNT_MOTIF_AVENANT = 'ARP'    THEN 1 ELSE 0 END) AS flag_arret_rachat_prog,
        MAX(CASE WHEN ca.CNT_MOTIF_AVENANT = 'RAA'    THEN 1 ELSE 0 END) AS flag_rachat_auto_avance,
        MAX(CASE WHEN ca.CNT_MOTIF_AVENANT = 'RESGAR' THEN 1 ELSE 0 END) AS flag_resil_garantie,
        MAX(CASE WHEN ca.CNT_MOTIF_AVENANT = 'CADFIS' THEN 1 ELSE 0 END) AS flag_changement_fiscal,
        MAX(CASE WHEN ca.CNT_MOTIF_AVENANT = 'CLBENF' THEN 1 ELSE 0 END) AS flag_changement_beneficiaire

    FROM CONTRAT ca
    GROUP BY ca.CNT_CONTRAT
),

-- ============================================================================
-- CTE 4 : profils_actifs
-- Concatène tous les profils actifs depuis CNT_PROFILS
-- ============================================================================
profils_actifs AS (
    SELECT
        cp.CNP_CONTRAT                          AS contrat_id,
        LISTAGG(cp.CNP_PROFIL, ',') 
            WITHIN GROUP (ORDER BY cp.CNP_PROFIL) AS profils
    FROM CNT_PROFILS cp
    INNER JOIN CONTRAT c
        ON cp.CNP_CONTRAT = c.CNT_CONTRAT
        AND cp.CNP_AVENANT = c.CNT_AVENANT
    WHERE c.CNT_DERNIER_AVT_O_N = 'O'
      AND cp.CNP_POURCENTAGE > 0
    GROUP BY cp.CNP_CONTRAT
)

-- ============================================================================
-- Requête principale : Dataset de base
-- ============================================================================
SELECT
    cb.contrat_id,
    cb.etat_contrat,
    cb.variable_cible,
    cb.date_creation,
    cb.date_effet,
    cb.date_resiliation,
    cb.date_echeance,
    cb.date_effet_avenant,
    cb.duree_annees,
    cb.duree_mois,
    cb.produit,
    cb.nature_produit,
    cb.multi_profils,
    cb.tarif,
    cb.option_contrat,
    pa.profils                                  AS profils_actifs,
    cb.cadre_fiscal,
    cb.mode_reglement,
    cb.periodicite,
    cb.devise,
    cb.motif_resiliation,
    cb.motif_avenant,
    cb.versement_initial,
    COALESCE(ma.total_primes, 0)                AS total_primes,
    COALESCE(ma.total_rachats, 0)               AS total_rachats,
    COALESCE(ma.nb_mouvements, 0)               AS nb_mouvements,
    COALESCE(ma.nb_mouvements_annules, 0)       AS nb_mouvements_annules,
    ma.date_premier_mouvement,
    ma.date_dernier_mouvement,
    pp.P_P_SEXE                                 AS sexe,
    pp.P_P_DATE_NAISSANCE                       AS date_naissance,
    pp.P_P_CODE_PROFESSION                      AS code_profession,
    pp.P_P_CSP                                  AS csp,
    pp.P_P_SITUATION_FAMILLE                    AS situation_famille,
    pp.P_P_REGIME_SOCIAL                        AS regime_social,
    adr.ADR_CODE_POSTAL                         AS code_postal,
    adr.ADR_PAYS                                AS pays,
    adr.ADR_LOCALITE                            AS localite,
    COALESCE(avm.nb_avt_risque_eleve, 0)        AS nb_avt_risque_eleve,
    COALESCE(avm.nb_avt_arret_annulation, 0)    AS nb_avt_arret_annulation,
    COALESCE(avm.nb_avt_arbitrage, 0)           AS nb_avt_arbitrage,
    COALESCE(avm.nb_avt_versement, 0)           AS nb_avt_versement,
    COALESCE(avm.nb_avt_modif_admin, 0)         AS nb_avt_modif_admin_motif,
    COALESCE(avm.nb_avt_creation_auto, 0)       AS nb_avt_creation_auto,
    COALESCE(avm.nb_avt_technique, 0)           AS nb_avt_technique,
    COALESCE(avm.flag_rachat_programme, 0)      AS flag_rachat_programme,
    COALESCE(avm.flag_renonciation, 0)          AS flag_renonciation,
    COALESCE(avm.flag_deces, 0)                 AS flag_deces,
    COALESCE(avm.flag_arret_rachat_prog, 0)     AS flag_arret_rachat_prog,
    COALESCE(avm.flag_rachat_auto_avance, 0)    AS flag_rachat_auto_avance,
    COALESCE(avm.flag_resil_garantie, 0)        AS flag_resil_garantie,
    COALESCE(avm.flag_changement_fiscal, 0)     AS flag_changement_fiscal,
    COALESCE(avm.flag_changement_beneficiaire, 0) AS flag_changement_beneficiaire,
    cb.nb_modif_admin,
    cb.existe_prime,
    cb.existe_rachat,
    cb.existe_avance,
    cb.existe_avenant
FROM contrats_base cb
LEFT JOIN mouvements_agg ma   ON cb.contrat_id = ma.contrat_id
LEFT JOIN avenants_par_motif avm ON cb.contrat_id = avm.contrat_id
LEFT JOIN profils_actifs pa ON cb.contrat_id = pa.contrat_id
LEFT JOIN PERSONNES_PHYSIQUES pp ON cb.souscripteur_id = pp.P_P_TIERS
LEFT JOIN ADRESSES adr        ON pp.P_P_TIERS = adr.ADR_TIERS
                              AND pp.P_P_ADRESSE_PRINCIPALE = adr.ADR_ADRESSE
;

-- ============================================================================
-- ÉTAPE 3 : Création de la table enrichie avec variables dérivées
-- Basée sur feature_engineering_derive.sql
-- ============================================================================
CREATE TABLE DATASET_SCORING_ENRICHI AS
SELECT
    d.*,

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

    -- Ratio rachats / primes (NULL si aucune prime)
    CASE
        WHEN d.total_primes > 0
        THEN ROUND(d.total_rachats / d.total_primes, 4)
        ELSE NULL
    END AS ratio_rachats_primes,

    -- Âge du souscripteur à la date d'effet (en années)
    CASE
        WHEN d.date_naissance IS NOT NULL AND d.date_effet IS NOT NULL
        THEN TRUNC(MONTHS_BETWEEN(TRUNC(d.date_effet), TRUNC(d.date_naissance)) / 12)
        ELSE NULL
    END AS age_souscripteur,

    -- Mois de création (saisonnalité)
    EXTRACT(MONTH FROM d.date_creation) AS mois_creation,

    -- Année de création
    EXTRACT(YEAR FROM d.date_creation) AS annee_creation,

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

FROM DATASET_SCORING_RESIL d
;

-- ============================================================================
-- ÉTAPE 4 : Création des index pour améliorer les performances
-- ============================================================================
CREATE INDEX IDX_SCORING_RESIL_CONTRAT ON DATASET_SCORING_RESIL(contrat_id);
CREATE INDEX IDX_SCORING_RESIL_CIBLE ON DATASET_SCORING_RESIL(variable_cible);
CREATE INDEX IDX_SCORING_RESIL_NATURE ON DATASET_SCORING_RESIL(nature_produit);
CREATE INDEX IDX_SCORING_RESIL_MULTI ON DATASET_SCORING_RESIL(multi_profils);

CREATE INDEX IDX_SCORING_ENRICHI_CONTRAT ON DATASET_SCORING_ENRICHI(contrat_id);
CREATE INDEX IDX_SCORING_ENRICHI_CIBLE ON DATASET_SCORING_ENRICHI(variable_cible);

-- ============================================================================
-- ÉTAPE 5 : Statistiques et vérifications
-- ============================================================================

-- Nombre de lignes par table
SELECT 'DATASET_SCORING_RESIL' AS table_name, COUNT(*) AS nb_lignes FROM DATASET_SCORING_RESIL
UNION ALL
SELECT 'DATASET_SCORING_ENRICHI', COUNT(*) FROM DATASET_SCORING_ENRICHI;

-- Distribution de la variable cible
SELECT 
    variable_cible,
    CASE WHEN variable_cible = 1 THEN 'Résilié' ELSE 'En vigueur' END as statut,
    COUNT(*) as nb_contrats,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pourcentage
FROM DATASET_SCORING_RESIL
GROUP BY variable_cible
ORDER BY variable_cible;

-- Distribution par nature de produit
SELECT 
    nature_produit,
    COUNT(*) as nb_contrats,
    SUM(variable_cible) as nb_resilies,
    ROUND(AVG(variable_cible) * 100, 2) as taux_resiliation_pct
FROM DATASET_SCORING_RESIL
GROUP BY nature_produit
ORDER BY nb_contrats DESC;

-- Distribution mono vs multiprofils
SELECT 
    multi_profils,
    CASE 
        WHEN multi_profils = '1' THEN 'Multiprofils'
        WHEN multi_profils = '0' THEN 'Monoprofils'
        ELSE 'Inconnu'
    END as type_profil,
    COUNT(*) as nb_contrats,
    SUM(variable_cible) as nb_resilies,
    ROUND(AVG(variable_cible) * 100, 2) as taux_resiliation_pct
FROM DATASET_SCORING_RESIL
GROUP BY multi_profils
ORDER BY multi_profils;

-- Vérification : aucun contrat RC ne doit être présent
SELECT 
    CASE 
        WHEN COUNT(*) = 0 THEN 'OK - Aucun contrat RC présent'
        ELSE 'ERREUR - ' || COUNT(*) || ' contrats RC trouvés !'
    END as verification_exclusion_rc
FROM DATASET_SCORING_RESIL
WHERE nature_produit = 'RC';

-- Aperçu des premières lignes
SELECT * FROM DATASET_SCORING_RESIL WHERE ROWNUM <= 5;

