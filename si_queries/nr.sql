select
    cast(nr.name as int) as n,
    case
	    when string_agg(distinct nr.status, ',') like '%network%' then 'network'
	    else 'project'
	end as statut,
    string_agg(distinct cast(ne.owner as varchar), ',') as ne,
    string_agg(distinct z.name, ',') as zone,
    string_agg(distinct a.nom, ',') as agence
from network nr
left join nano_entrepreneur ne 
	on nr.id = ne.network_id
	and ne.end_date is null
left join zone z
	on nr.zone_id = z.id
left join agence a
    on z.agence_id = a.id
group by nr.name