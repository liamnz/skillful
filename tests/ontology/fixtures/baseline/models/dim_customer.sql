select
    customer_id,
    region,
    last_paid_order_at >= current_date - interval '90 days' as is_active
from {{ ref('stg_customers') }}
