select
    id as plan_id,
    name as plan_name,
    billing_interval,
    price_cents / 100.0 as plan_price
from {{ source('billing', 'plans') }}
