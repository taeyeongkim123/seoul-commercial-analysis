-- heuristic_risk_flag is an illustrative signal, not the official methodology:
-- it flags districts in the LL/HH change-index grades (Seoul's own docs note both
-- as "requires caution for entry") that also show a same-quarter footfall decline.
with change_index as (
    select * from {{ ref('stg_change_index') }}
),

footfall as (
    select
        std_yyqu,
        district_code,
        total_footfall_count,
        lag(total_footfall_count) over (
            partition by district_code order by std_yyqu
        ) as prev_quarter_footfall_count
    from {{ ref('stg_footfall') }}
),

joined as (
    select
        c.std_yyqu,
        c.district_type_code,
        c.district_type_name,
        c.district_code,
        c.district_name,
        c.change_index_code,
        c.change_index_name,
        c.avg_operating_months_open,
        c.avg_operating_months_closed,
        c.seoul_avg_operating_months_open,
        c.seoul_avg_operating_months_closed,
        f.total_footfall_count,
        f.prev_quarter_footfall_count,
        case
            when f.prev_quarter_footfall_count is null or f.prev_quarter_footfall_count = 0 then null
            else round(
                (f.total_footfall_count - f.prev_quarter_footfall_count)
                / f.prev_quarter_footfall_count * 100, 1
            )
        end as qoq_footfall_growth_pct
    from change_index c
    left join footfall f
        on c.std_yyqu = f.std_yyqu and c.district_code = f.district_code
)

select
    *,
    case
        when change_index_code in ('LL', 'HH')
            and (qoq_footfall_growth_pct is null or qoq_footfall_growth_pct < 0)
        then 'watch'
        else 'normal'
    end as heuristic_risk_flag
from joined
