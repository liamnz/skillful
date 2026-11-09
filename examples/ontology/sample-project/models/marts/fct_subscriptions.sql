select
    subscription_id,
    customer_id,
    plan_id,
    status as subscription_status,
    started_at,
    cancelled_at
from {{ ref('stg_subscriptions') }}
