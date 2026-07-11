with sales as (
    select * from {{ ref('stg_sales') }}
),

trend as (
    select
        std_yyqu,
        district_type_code,
        district_type_name,
        district_code,
        district_name,
        industry_code,
        industry_name,
        monthly_sales_amount,
        monthly_sales_count,
        weekday_sales_amount,
        weekend_sales_amount,
        lag(monthly_sales_amount) over (
            partition by district_code, industry_code
            order by std_yyqu
        ) as prev_quarter_sales_amount
    from sales
)

select
    *,
    case
        when prev_quarter_sales_amount is null or prev_quarter_sales_amount = 0 then null
        else round((monthly_sales_amount - prev_quarter_sales_amount) / prev_quarter_sales_amount * 100, 1)
    end as qoq_sales_growth_pct
from trend
