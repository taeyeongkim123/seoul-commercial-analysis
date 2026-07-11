with latest_quarter as (
    select max(std_yyqu) as std_yyqu from {{ ref('mart_district_risk') }}
),

risk as (
    select r.*
    from {{ ref('mart_district_risk') }} r
    inner join latest_quarter lq on r.std_yyqu = lq.std_yyqu
),

sales_by_district as (
    select
        std_yyqu,
        district_code,
        sum(monthly_sales_amount) as total_monthly_sales_amount
    from {{ ref('mart_district_sales_trend') }}
    group by 1, 2
),

sales_latest as (
    select s.*
    from sales_by_district s
    inner join latest_quarter lq on s.std_yyqu = lq.std_yyqu
)

select
    a.district_code,
    a.district_name,
    a.district_type_name,
    a.gu_name,
    a.dong_name,
    a.area_sqm,
    a.lon,
    a.lat,
    risk.change_index_code,
    risk.change_index_name,
    risk.heuristic_risk_flag,
    risk.qoq_footfall_growth_pct,
    sales_latest.total_monthly_sales_amount,
    c.cluster_id,
    c.cluster_label
from {{ ref('stg_district_areas') }} a
left join risk on a.district_code = risk.district_code
left join sales_latest on a.district_code = sales_latest.district_code
left join {{ ref('stg_district_clusters') }} c on a.district_code = c.district_code
where a.lon is not null and a.lat is not null
