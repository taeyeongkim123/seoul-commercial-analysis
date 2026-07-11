with stores as (
    select * from {{ ref('stg_stores') }}
),

sales as (
    select
        std_yyqu,
        district_code,
        industry_code,
        monthly_sales_amount
    from {{ ref('stg_sales') }}
),

district_totals as (
    select
        std_yyqu,
        district_code,
        sum(store_count) as district_total_store_count
    from stores
    group by 1, 2
),

joined as (
    select
        s.std_yyqu,
        s.district_type_code,
        s.district_type_name,
        s.district_code,
        s.district_name,
        s.industry_code,
        s.industry_name,
        s.store_count,
        s.franchise_store_count,
        s.open_rate,
        s.close_rate,
        d.district_total_store_count,
        case
            when d.district_total_store_count > 0
            then round(s.store_count / d.district_total_store_count * 100, 1)
        end as industry_share_of_district_pct,
        sl.monthly_sales_amount,
        case
            when s.store_count > 0
            then round(sl.monthly_sales_amount / s.store_count, 0)
        end as sales_per_store_amount
    from stores s
    left join district_totals d
        on s.std_yyqu = d.std_yyqu and s.district_code = d.district_code
    left join sales sl
        on s.std_yyqu = sl.std_yyqu
        and s.district_code = sl.district_code
        and s.industry_code = sl.industry_code
)

select
    *,
    rank() over (
        partition by std_yyqu, district_code
        order by store_count desc
    ) as store_count_rank_in_district
from joined
