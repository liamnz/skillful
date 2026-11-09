-- New in this sprint: accounts whose last subscription ended more than 60 days ago.
with last_sub as (
    select customer_id, max(coalesce(cancelled_at, current_date)) as last_subscription_end
    from {{ ref('fct_subscriptions') }}
    group by 1
)

select
    customer_id,
    last_subscription_end,
    last_subscription_end < current_date - interval '60 days' as is_churned
from last_sub
