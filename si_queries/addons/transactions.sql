WITH transactions_reussies AS (
    SELECT
        c.id AS id_client,
        t.date_creation::date - DATE '1970-01-01' as debut,
        CASE gc.duration_unit
            WHEN 1 THEN gc.duration        -- jours
            WHEN 2 THEN gc.duration * 7    -- semaines
            WHEN 3 THEN gc.duration * 30   -- mois
            ELSE 0
        END AS duree
    FROM customer c
    LEFT JOIN transaction t
        ON t.customer = c.id
    INNER JOIN generated_code gc
        ON t.id = gc.transaction_id
    LEFT JOIN offers o
        ON o.id = c.offer
    WHERE
        t.status = 'success'
        AND (t.motif IS NULL OR t.motif <> 'Remplacement Arduino ou rectification')
        AND o.title <> 'Desactivation'
        AND t.date_creation >= c.date_join_network
        AND c.custom_number IS NOT NULL
)

SELECT
    t.id_client as id_client,
    t.debut as debut,
    t.debut + t.duree as fin
FROM transactions_reussies t
WHERE
    t.debut + t.duree + 366 >= now()::date - DATE '1970-01-01'