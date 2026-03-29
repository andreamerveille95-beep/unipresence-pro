-- ============================================================
--  UniPresence Pro — IUE Douala
--  Schéma MySQL complet + données de démonstration
--  Généré le 2026-03-20
-- ============================================================

SET NAMES 'utf8mb4';
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

CREATE DATABASE IF NOT EXISTS `unipresencepro`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `unipresencepro`;

-- Désactiver les contraintes FK pendant la création
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- TABLE 1 : admins
-- ============================================================
DROP TABLE IF EXISTS `admins`;
CREATE TABLE `admins` (
    `id`           INT            NOT NULL AUTO_INCREMENT,
    `nom`          VARCHAR(100)   NOT NULL,
    `prenom`       VARCHAR(100)   NOT NULL,
    `email`        VARCHAR(150)   NOT NULL,
    `mot_de_passe` VARCHAR(255)   NOT NULL,
    `created_at`   TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_admins_email` (`email`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Comptes administrateurs du système';

-- ============================================================
-- TABLE 2 : enseignants
-- ============================================================
DROP TABLE IF EXISTS `enseignants`;
CREATE TABLE `enseignants` (
    `id`             INT            NOT NULL AUTO_INCREMENT,
    `matricule`      VARCHAR(20)    NOT NULL,
    `nom`            VARCHAR(100)   NOT NULL,
    `prenom`         VARCHAR(100)   NOT NULL,
    `email`          VARCHAR(150)   NOT NULL,
    `telephone`      VARCHAR(20)    DEFAULT NULL,
    `specialite`     VARCHAR(150)   DEFAULT NULL,
    `departement`    ENUM('ESIT','EME','ADMIN') NOT NULL,
    `grade`          ENUM('Assistant','Chargé','Maître','Prof') NOT NULL,
    `photo`          VARCHAR(255)   NOT NULL DEFAULT '',
    `qr_code_path`   VARCHAR(255)   NOT NULL DEFAULT '',
    `qr_code_data`   TEXT                    DEFAULT '',
    `est_actif`      TINYINT(1)     NOT NULL DEFAULT 1,
    `date_inscription` DATE         DEFAULT NULL,
    `created_at`     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_enseignants_matricule` (`matricule`),
    KEY `idx_enseignants_departement` (`departement`),
    KEY `idx_enseignants_est_actif`   (`est_actif`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Enseignants enregistrés dans le système';

-- ============================================================
-- TABLE 3 : seances
-- ============================================================
DROP TABLE IF EXISTS `seances`;
CREATE TABLE `seances` (
    `id`            INT            NOT NULL AUTO_INCREMENT,
    `titre`         VARCHAR(200)   NOT NULL,
    `matiere`       VARCHAR(150)   DEFAULT NULL,
    `enseignant_id` INT            NOT NULL,
    `salle`         VARCHAR(50)    DEFAULT NULL,
    `date_seance`   DATE           NOT NULL,
    `heure_debut`   TIME           NOT NULL,
    `heure_fin`     TIME           NOT NULL,
    `type_seance`   ENUM('CM','TD','TP','Exam') NOT NULL DEFAULT 'CM',
    `statut`        ENUM('planifiee','en_cours','terminee','annulee') NOT NULL DEFAULT 'planifiee',
    `created_at`    TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_seances_enseignant`  (`enseignant_id`),
    KEY `idx_seances_date`        (`date_seance`),
    KEY `idx_seances_statut`      (`statut`),
    CONSTRAINT `fk_seances_enseignant`
        FOREIGN KEY (`enseignant_id`)
        REFERENCES `enseignants` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Séances de cours planifiées';

-- ============================================================
-- TABLE 4 : presences
-- ============================================================
DROP TABLE IF EXISTS `presences`;
CREATE TABLE `presences` (
    `id`              INT            NOT NULL AUTO_INCREMENT,
    `enseignant_id`   INT            NOT NULL,
    `seance_id`       INT                     DEFAULT NULL,
    `type_pointage`   ENUM('ARRIVEE','DEPART','PAUSE') NOT NULL DEFAULT 'ARRIVEE',
    `mode_pointage`   ENUM('QR_CODE','CAMERA','MANUEL') NOT NULL DEFAULT 'MANUEL',
    `heure_pointage`  TIME           NOT NULL,
    `date_pointage`   DATE           NOT NULL,
    `retard_minutes`  INT            NOT NULL DEFAULT 0,
    `statut`          ENUM('PRESENT','RETARD','ABSENT','EXCUSE') NOT NULL DEFAULT 'PRESENT',
    `commentaire`     TEXT                    DEFAULT NULL,
    `adresse_ip`      VARCHAR(45)             DEFAULT NULL,
    `created_at`      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_presences_enseignant`   (`enseignant_id`),
    KEY `idx_presences_seance`       (`seance_id`),
    KEY `idx_presences_date`         (`date_pointage`),
    KEY `idx_presences_statut`       (`statut`),
    CONSTRAINT `fk_presences_enseignant`
        FOREIGN KEY (`enseignant_id`)
        REFERENCES `enseignants` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT `fk_presences_seance`
        FOREIGN KEY (`seance_id`)
        REFERENCES `seances` (`id`)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Pointages de présence des enseignants';

-- ============================================================
-- TABLE 5 : sessions_admin
-- ============================================================
DROP TABLE IF EXISTS `sessions_admin`;
CREATE TABLE `sessions_admin` (
    `id`         INT          NOT NULL AUTO_INCREMENT,
    `admin_id`   INT          NOT NULL,
    `token`      VARCHAR(255) NOT NULL,
    `created_at` TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `expires_at` TIMESTAMP    NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL 8 HOUR),
    `adresse_ip` VARCHAR(45)           DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_sessions_token` (`token`),
    KEY `idx_sessions_admin`  (`admin_id`),
    KEY `idx_sessions_expires` (`expires_at`),
    CONSTRAINT `fk_sessions_admin`
        FOREIGN KEY (`admin_id`)
        REFERENCES `admins` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Sessions authentifiées des administrateurs';

-- Réactiver les contraintes FK
SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- DONNÉES DE DÉMONSTRATION
-- ============================================================

-- ---- Admin ----
-- Mot de passe : admin123 (bcrypt cost 12)
INSERT INTO `admins` (`nom`, `prenom`, `email`, `mot_de_passe`) VALUES
(
    'Admin',
    'IUE',
    'admin@iue.cm',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW'
    -- Mot de passe en clair : admin123
);

-- ---- Enseignants ----
INSERT INTO `enseignants`
    (`matricule`, `nom`, `prenom`, `email`, `telephone`, `specialite`,
     `departement`, `grade`, `est_actif`, `date_inscription`)
VALUES
(
    'IUE-2024-0001',
    'MBARGA',
    'Jean-Paul',
    'jp.mbarga@iue.cm',
    '+237691234567',
    'Informatique & Réseaux',
    'ESIT',
    'Maître',
    1,
    '2024-01-15'
),
(
    'IUE-2024-0002',
    'NNOMO',
    'Alice',
    'a.nnomo@iue.cm',
    '+237677890123',
    'Marketing Digital',
    'EME',
    'Chargé',
    1,
    '2024-01-20'
),
(
    'IUE-2024-0003',
    'BIYONG',
    'Stéphane',
    's.biyong@iue.cm',
    '+237655432109',
    'Génie Logiciel',
    'ESIT',
    'Prof',
    1,
    '2024-02-01'
),
(
    'IUE-2024-0004',
    'FOUDA',
    'Marie-Claire',
    'mc.fouda@iue.cm',
    '+237699876543',
    'Finance & Comptabilité',
    'EME',
    'Assistant',
    1,
    '2024-02-10'
),
(
    'IUE-2025-0005',
    'EKANI',
    'Robert',
    'r.ekani@iue.cm',
    '+237681234000',
    'Administration',
    'ADMIN',
    'Chargé',
    1,
    '2025-01-05'
);

-- ---- Séances (dates dynamiques = CURDATE()) ----
INSERT INTO `seances`
    (`titre`, `matiere`, `enseignant_id`, `salle`,
     `date_seance`, `heure_debut`, `heure_fin`, `type_seance`, `statut`)
VALUES
(
    'Algorithmique avancée',
    'Informatique',
    1,
    'B204',
    CURDATE(),
    '08:00:00',
    '10:00:00',
    'CM',
    'planifiee'
),
(
    'Marketing Stratégique',
    'Marketing',
    2,
    'A101',
    CURDATE(),
    '10:30:00',
    '12:30:00',
    'TD',
    'planifiee'
),
(
    'Base de données',
    'Informatique',
    3,
    'Labo Info',
    CURDATE(),
    '14:00:00',
    '16:00:00',
    'TP',
    'planifiee'
);

-- ---- Présences (3 entrées pour aujourd'hui) ----
INSERT INTO `presences`
    (`enseignant_id`, `seance_id`, `type_pointage`, `mode_pointage`,
     `heure_pointage`, `date_pointage`, `retard_minutes`, `statut`, `adresse_ip`)
VALUES
(
    -- Enseignant 1 arrivé 1 h avant maintenant — PRESENT, mode MANUEL
    1,
    1,
    'ARRIVEE',
    'MANUEL',
    SUBTIME(CURTIME(), '01:00:00'),
    CURDATE(),
    0,
    'PRESENT',
    '127.0.0.1'
),
(
    -- Enseignant 2 arrivé il y a 30 min — RETARD 15 min, mode QR_CODE
    2,
    2,
    'ARRIVEE',
    'QR_CODE',
    SUBTIME(CURTIME(), '00:30:00'),
    CURDATE(),
    15,
    'RETARD',
    '127.0.0.1'
),
(
    -- Enseignant 4 arrivé maintenant, sans séance associée — PRESENT
    4,
    NULL,
    'ARRIVEE',
    'MANUEL',
    CURTIME(),
    CURDATE(),
    0,
    'PRESENT',
    '127.0.0.1'
);

-- ============================================================
-- Vues utilitaires (optionnelles mais pratiques)
-- ============================================================

-- Vue : résumé présences du jour
CREATE OR REPLACE VIEW `v_presences_aujourd_hui` AS
SELECT
    p.id,
    p.enseignant_id,
    CONCAT(e.nom, ' ', e.prenom) AS enseignant,
    e.matricule,
    e.departement,
    s.titre              AS seance,
    p.type_pointage,
    p.mode_pointage,
    p.heure_pointage,
    p.retard_minutes,
    p.statut
FROM `presences` p
JOIN `enseignants` e ON e.id = p.enseignant_id
LEFT JOIN `seances` s ON s.id = p.seance_id
WHERE p.date_pointage = CURDATE()
ORDER BY p.heure_pointage DESC;

-- Vue : taux de ponctualité par enseignant
CREATE OR REPLACE VIEW `v_taux_ponctualite` AS
SELECT
    e.id,
    e.matricule,
    CONCAT(e.nom, ' ', e.prenom) AS enseignant,
    e.departement,
    COUNT(p.id)                  AS total_pointages,
    SUM(p.statut = 'PRESENT')    AS nb_presents,
    SUM(p.statut = 'RETARD')     AS nb_retards,
    SUM(p.statut = 'ABSENT')     AS nb_absents,
    ROUND(
        IF(COUNT(p.id) = 0, 0,
           SUM(p.statut = 'PRESENT') * 100.0 / COUNT(p.id)
        ), 2
    )                            AS taux_ponctualite
FROM `enseignants` e
LEFT JOIN `presences` p ON p.enseignant_id = e.id
WHERE e.est_actif = 1
GROUP BY e.id, e.matricule, e.nom, e.prenom, e.departement;

-- ============================================================
-- Fin du script SQL
-- ============================================================
