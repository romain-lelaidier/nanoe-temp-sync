WITH transactions_reussies AS (
    SELECT
        c.id AS id_client,
        t.date_creation::date - DATE '1970-01-01' as debut,
        t.amount as montant
    FROM customer c
    LEFT JOIN transaction t
        ON t.customer = c.id
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
    t.montant as montant
FROM transactions_reussies t
WHERE
    t.debut + 92*4*2 >= now()::date - DATE '1970-01-01'