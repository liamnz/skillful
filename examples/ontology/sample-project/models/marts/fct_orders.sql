select
    order_id,
    customer_id,
    placed_at,
    amount,
    discount
from {{ ref('stg_orders') }}
where status in ('paid', 'refunded')
