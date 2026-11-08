select
    id as product_id,
    sku,
    name as product_name,
    category
from {{ source('shop', 'products') }}
where is_sellable
