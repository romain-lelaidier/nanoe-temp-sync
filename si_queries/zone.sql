select
    z.name as zone,
    a.nom as agence,
    zpp.name as commune,
    zppp.name as district
from zone z
left join agence a
    on z.agence_id = a.id
left join zone zp
    on z.parent_id = zp.id
left join zone zpp
    on zp.parent_id = zpp.id
left join zone zppp
    on zpp.parent_id = zppp.id
where z.type = 'TYPE_ZONE'