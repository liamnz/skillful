select
    order_id,
    order_line_id,
    customer_id,
    placed_at,
    amount
from {{ ref('stg_orders') }}
