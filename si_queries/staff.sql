select
    u.id as si_id,
    u.firstname as prenom,
    u.lastname as nom,
    u.username as email,
    u.enabled as actif,
    u.phone_number as telephone,
    u.flotte_phone_number as telephone_flotte,
    a.nom as agence,
	-- exists (select 1 from nano_entrepreneur ne where ne.owner = u.id) as is_ne,
    CASE 
        WHEN u.roles IS NULL THEN NULL
        ELSE trim(trailing ',' from
            regexp_replace(
                regexp_replace(u.roles, '^a:\d+:\{|\}$', '', 'g'),
                'i:\d+;s:\d+:"ROLE_([^"]*)";',
                '\1,',
                'g'
            )
        )
    END AS roles
from users as u
left join agence a on u.agence_id = a.id