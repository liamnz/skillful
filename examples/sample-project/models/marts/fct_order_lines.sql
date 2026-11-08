select
    id as order_line_id,
    order_id,
    product_id,
    quantity,
    unit_price_cents / 100.0 as unit_price
from {{ source('shop', 'order_lines') }}
