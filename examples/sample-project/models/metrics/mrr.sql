select
    date_trunc('month', current_date) as month,
    sum(p.plan_price) as monthly_recurring_revenue
from {{ ref('fct_subscriptions') }} as s
join {{ ref('dim_plan') }} as p using (plan_id)
where s.subscription_status = 'active'
