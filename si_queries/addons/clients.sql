select
    c.id as n,
    c.custom_number as n_client
from customer c
where c.custom_number is not null