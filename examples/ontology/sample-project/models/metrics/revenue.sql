with orders as (
    select date_trunc('month', placed_at) as month, order_id, amount
    from {{ ref('fct_orders') }}
),

refunds as (
    select date_trunc('month', issued_at) as month, sum(refund_amount) as refunded
    from {{ ref('fct_refunds') }}
    group by 1
)

select
    o.month,
    sum(o.amount) as gross_revenue,
    sum(o.amount) - coalesce(max(r.refunded), 0) as net_revenue,
    avg(o.amount) as average_order_value
from orders as o
left join refunds as r using (month)
group by 1
