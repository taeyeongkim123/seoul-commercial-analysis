# marts

staging 모델의 실제 컬럼명을 확인한 뒤 다음 마트를 추가하세요.

- `mart_district_sales_trend.sql` — 상권×업종별 분기 매출 추이
- `mart_industry_competition.sql` — 상권 내 업종별 점포 밀도/경쟁도
- `mart_district_risk.sql` — 상권변화지표 기반 쇠퇴 위험 등급

컬럼명은 `stg_sales`, `stg_footfall`, `stg_change_index`, `stg_stores`를 `dbt run` 후
DuckDB에서 직접 조회(`duckdb data/processed/seoul_commercial.duckdb -c "DESCRIBE stg_sales"`)해서 확인하세요.
