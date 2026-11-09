select
    id as order_id,
    customer_id,
    status,
    placed_at,
    total_amount_cents / 100.0 as amount,
    discount_cents / 100.0 as discount
from {{ source('shop', 'orders') }}
