select
    TRDAR_CD as district_code,
    TRDAR_CD_NM as district_name,
    TRDAR_SE_CD as district_type_code,
    TRDAR_SE_CD_NM as district_type_name,
    SIGNGU_CD as gu_code,
    SIGNGU_CD_NM as gu_name,
    ADSTRD_CD as dong_code,
    ADSTRD_CD_NM as dong_name,
    cast(RELM_AR as double) as area_sqm,
    LON as lon,
    LAT as lat
from {{ source('raw', 'raw_areas') }}
