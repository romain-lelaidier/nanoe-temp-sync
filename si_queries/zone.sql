with nr_pas_supprimes as (
    select *
    from network nr
    where nr.deleted_at is null
)

select
    z.name as zone,
    string_agg(distinct a.nom, ',') as agence,
    string_agg(distinct zpp.name, ',') as commune,
    string_agg(distinct zppp.name, ',') as district,
    string_agg(distinct cast(ne.owner as varchar), ',') as ne
from zone z
left join agence a
    on z.agence_id = a.id
left join zone zp
    on z.parent_id = zp.id
left join zone zpp
    on zp.parent_id = zpp.id
left join zone zppp
    on zpp.parent_id = zppp.id
left join nr_pas_supprimes nr
    on nr.zone_id = z.id
left join nano_entrepreneur ne 
	on nr.id = ne.network_id
	and ne.end_date is null
where z.type = 'TYPE_ZONE'
    and z.deleted_at is null
group by z.name