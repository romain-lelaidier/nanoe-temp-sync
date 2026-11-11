WITH last_tension AS (
    SELECT DISTINCT ON (data_record_id)     -- Une seule ligne par RS
        data_record_id,
        min,    -- Tension minimale
        max,    -- Tension maximale
        day     -- Date de la mesure
    FROM f_tension_record_agg_network       -- Table des relevés de tension par RS
    ORDER BY data_record_id, day DESC       -- Tri pour obtenir la mesure la plus récente pour les valeurs de tension qui sont multiples dans la table PgAdmin
)

SELECT
    d.id as "id",
    -- d.record_date::date || '_' || n1_.name  AS "id",
    n1_.name AS "nr",
    d.owner_id AS "agent",
    d.record_date::date AS "date",
    d.previous_date AS "date_releve_precedente",
    d.rs_ok AS "rs_ok",
    d.rtc_ok AS "rtc_ok",
    d.heure_ok AS "heure_ok",
    d.time_delay AS "difference_heure",
    d.sd_ok AS "sd_ok",
    d.nb_unusual_start AS "nb_demarrages_anormaux",
    t.min AS "t_min",
    t.max AS "t_max"
FROM data_record d
INNER JOIN network n1_ ON d.network_id = n1_.id
LEFT JOIN last_tension t ON d.id = t.data_record_id
WHERE d.synthetical_record = true AND d.record_date::date >= '2026-07-01'