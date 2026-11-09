with cohorts as (
    select customer_id, date_trunc('month', signed_up_at) as cohort_month
    from {{ ref('dim_customer') }}
)

select
    cohort_month,
    count(*) filter (where d.is_active) * 1.0 / count(*) as retention_rate
from cohorts
join {{ ref('dim_customer') }} as d using (customer_id)
group by 1
