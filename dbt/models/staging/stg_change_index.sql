select
    STDR_YYQU_CD as std_yyqu,
    TRDAR_SE_CD as district_type_code,
    TRDAR_SE_CD_NM as district_type_name,
    TRDAR_CD as district_code,
    TRDAR_CD_NM as district_name,
    TRDAR_CHNGE_IX as change_index_code,
    TRDAR_CHNGE_IX_NM as change_index_name,
    OPR_SALE_MT_AVRG as avg_operating_months_open,
    CLS_SALE_MT_AVRG as avg_operating_months_closed,
    SU_OPR_SALE_MT_AVRG as seoul_avg_operating_months_open,
    SU_CLS_SALE_MT_AVRG as seoul_avg_operating_months_closed
from {{ source('raw', 'raw_change_index') }}
