select
    c.id as n,
    c.custom_number as n_client,
    c.status as statut,
    c.firstname as nom,
    trim(lower(c.job)) as metier,
    c.phone_number as telephone,
    z.name as zone,
    c.localization_lat as latitude,
    c.localization_long as longitude,
    nr.name as nr,
    c.date_join_network as date_raccordement
from customer c
left join zone z
    on z.id = c.zone
left join network nr
    on nr.id = c.network_id