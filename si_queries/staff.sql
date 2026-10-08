select
    u.id as si_id,
    u.firstname as prenom,
    u.lastname as nom,
    u.username as email,
    u.enabled as actif,
    u.phone_number as telephone,
    u.flotte_phone_number as telephone_flotte,
	exists (select 1 from nano_entrepreneur ne where ne.owner = u.id) as is_ne
from users u