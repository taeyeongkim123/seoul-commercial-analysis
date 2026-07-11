select
    STDR_YYQU_CD as std_yyqu,
    TRDAR_SE_CD as district_type_code,
    TRDAR_SE_CD_NM as district_type_name,
    TRDAR_CD as district_code,
    TRDAR_CD_NM as district_name,
    SVC_INDUTY_CD as industry_code,
    SVC_INDUTY_CD_NM as industry_name,
    SIMILR_INDUTY_STOR_CO as similar_industry_store_count,
    STOR_CO as store_count,
    FRC_STOR_CO as franchise_store_count,
    OPBIZ_RT as open_rate,
    OPBIZ_STOR_CO as open_store_count,
    CLSBIZ_RT as close_rate,
    CLSBIZ_STOR_CO as close_store_count
from {{ source('raw', 'raw_stores') }}
