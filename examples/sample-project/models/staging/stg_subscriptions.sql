select
    id as subscription_id,
    customer_id,
    plan_id,
    status,
    started_at,
    cancelled_at
from {{ source('billing', 'subscriptions') }}
