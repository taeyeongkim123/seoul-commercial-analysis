-- TODO: fetch_seoul_data.py 실행 후 raw_sales 스키마를 확인하고
-- 실제 컬럼명(상권코드/상권명/업종/매출액 등)으로 명시적 select + rename 하도록 교체할 것.
select * from {{ source('raw', 'raw_sales') }}
