with nr_pas_supprimes as (
    select *
    from network nr
    where nr.deleted_at is null
),

materiel as (
    select
        nrd.network_id as nr_id,
        nrd.device_count as quantite,
        d.name as article,
        concat(
            replace(replace(replace(d.name, ';', ','), '[', '('), ']', ')'),
            ' [',
            nrd.device_count,
            ']'
        ) as description
    from network_device nrd
    left join device d
        on d.id = nrd.device_id
    where nrd.date_deletion is null
)

select
    cast(nr.name as int) as n,
    case
	    when string_agg(distinct nr.status, ',') like '%%network%%' then 'en service'
	    else 'projet'
	end as statut,
    string_agg(distinct cast(ne.owner as varchar), ',') as ne,
    string_agg(distinct z.name, ',') as zone,
    string_agg(distinct a.nom, ',') as agence,
    string_agg(distinct nr.cryptage, ',') as cryptage,
    max(nr.date_start_service) as date_mes,
    max(nr.total_cost) as cout_total,
    max(nr.localization_lat) as latitude,
    max(nr.localization_long) as longitude,
    max(nr.total_power) as puissance,
    string_agg(m.description, ' ; ') as materiel
from nr_pas_supprimes nr
left join nano_entrepreneur ne 
	on nr.id = ne.network_id
	and ne.end_date is null
left join zone z
	on nr.zone_id = z.id
left join agence a
    on z.agence_id = a.id
left join materiel m
    on nr.id = m.nr_id
group by nr.name