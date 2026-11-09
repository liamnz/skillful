select
    id as refund_id,
    order_id,
    issued_at,
    amount_cents / 100.0 as refund_amount
from {{ source('shop', 'refunds') }}
