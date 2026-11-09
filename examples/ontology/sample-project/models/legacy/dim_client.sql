-- Deprecated: replaced by marts/dim_customer.sql. Kept until the finance dashboards migrate.
select id as client_id, company_name
from {{ source('crm', 'clients') }}
