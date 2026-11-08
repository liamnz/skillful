select
    id as customer_id,
    created_at as signed_up_at,
    terms_accepted_at,
    country_code,
    region
from {{ source('shop', 'customers') }}
where terms_accepted_at is not null
