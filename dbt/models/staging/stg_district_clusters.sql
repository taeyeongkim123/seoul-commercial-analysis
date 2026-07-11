select
    district_code,
    cast(cluster_id as integer) as cluster_id,
    cluster_label,
    total_footfall_count,
    total_sales_amount,
    industry_count,
    total_store_count,
    franchise_ratio,
    avg_open_rate,
    avg_close_rate,
    avg_operating_months_open,
    avg_operating_months_closed
from {{ source('raw', 'raw_district_clusters') }}
