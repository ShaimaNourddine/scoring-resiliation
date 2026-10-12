-- ============================================================================
-- Script de création de la table SCORING_USERS (authentification)
-- Exécuter dans une SQL Window Oracle (SQL Developer, TOAD, PL/SQL Developer)
--
-- Table utilisée par l'API FastAPI (auth.py / 04_serve_api.py) pour
-- l'authentification et le CRUD utilisateurs (réservé aux admins).
--
-- IMPORTANT SÉCURITÉ :
-- - PASSWORD_HASH ne contient JAMAIS de mot de passe en clair : uniquement
--   le hash bcrypt calculé côté API (module auth.py, passlib/bcrypt).
-- - Aucun mot de passe ne doit transiter ni être stocké autrement que hashé.
-- ============================================================================

-- ============================================================================
-- ÉTAPE 1 : Suppression de la table si elle existe déjà
-- ============================================================================
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE SCORING_USERS';
EXCEPTION
    WHEN OTHERS THEN NULL;
END;
/

-- ============================================================================
-- ÉTAPE 2 : Création de la table SCORING_USERS
-- ============================================================================
CREATE TABLE SCORING_USERS (
    USER_ID         NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    EMAIL           VARCHAR2(200) NOT NULL UNIQUE,
    PASSWORD_HASH   VARCHAR2(200) NOT NULL,
    NOM             VARCHAR2(200) NOT NULL,
    ROLE            VARCHAR2(20)  NOT NULL,
    ACTIF           NUMBER(1)     DEFAULT 1 NOT NULL,
    DATE_CREATION   TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
    DATE_MODIFICATION TIMESTAMP   DEFAULT SYSTIMESTAMP,
    DERNIERE_CONNEXION TIMESTAMP,
    CONSTRAINT CHK_USERS_ROLE CHECK (ROLE IN ('ADMIN', 'GESTIONNAIRE')),
    CONSTRAINT CHK_USERS_ACTIF CHECK (ACTIF IN (0, 1))
);

-- NB : pas besoin de créer un index séparé sur EMAIL : la contrainte
-- UNIQUE déclarée ci-dessus crée déjà automatiquement un index système
-- sur cette colonne (Oracle le fait pour toute contrainte UNIQUE/PRIMARY
-- KEY). Une tentative de CREATE INDEX supplémentaire échouerait avec
-- ORA-01408 (colonne déjà indexée).

-- ============================================================================
-- ÉTAPE 3 : Utilisateur admin initial
-- ============================================================================
-- Mot de passe initial : "ChangeMoi123!" (À CHANGER dès la première connexion)
-- Hash bcrypt généré côté Python via generate_admin_hash.py
INSERT INTO SCORING_USERS (EMAIL, PASSWORD_HASH, NOM, ROLE, ACTIF)
VALUES (
    'admin@scoring-resiliation.local',
    '$2b$12$RboJtGhkSJizEP97wE.nweKOV1QO5LnU8CV3KKpfMToneWVubhNOq',
    'Administrateur',
    'ADMIN',
    1
);

COMMIT;

-- ============================================================================
-- Vérification
-- ============================================================================
SELECT user_id, email, nom, role, actif, date_creation FROM SCORING_USERS;
