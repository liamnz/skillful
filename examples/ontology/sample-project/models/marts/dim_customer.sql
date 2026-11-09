with orders as (
    select customer_id, max(placed_at) as last_paid_order_at
    from {{ ref('stg_orders') }}
    where status = 'paid'
    group by 1
)

select
    c.customer_id,
    c.signed_up_at,
    c.region,
    o.last_paid_order_at,
    -- active: paid order in the last 30 days
    coalesce(o.last_paid_order_at >= current_date - interval '30 days', false) as is_active
from {{ ref('stg_customers') }} as c
left join orders as o using (customer_id)
