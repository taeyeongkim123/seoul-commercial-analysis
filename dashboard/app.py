"""서울시 상권분석 대시보드 (스켈레톤).

데이터 수집(scripts/fetch_seoul_data.py) 및 dbt run 이후 실행하세요:
    streamlit run dashboard/app.py
"""
from pathlib import Path

import duckdb
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "seoul_commercial.duckdb"

st.set_page_config(page_title="서울시 상권분석", layout="wide")
st.title("서울시 상권분석 대시보드")

if not DB_PATH.exists():
    st.warning(
        "DuckDB 파일이 없습니다. 먼저 `python scripts/fetch_seoul_data.py`와 "
        "`dbt run`(dbt/ 디렉토리에서)을 실행하세요."
    )
    st.stop()

con = duckdb.connect(str(DB_PATH), read_only=True)
tables = con.execute("SHOW TABLES").fetchall()
table_names = [t[0] for t in tables]

st.sidebar.header("데이터 미리보기")
selected = st.sidebar.selectbox("테이블 선택", table_names)

if selected:
    df = con.execute(f"SELECT * FROM {selected} LIMIT 500").fetchdf()
    st.subheader(f"{selected} ({len(df)}행 미리보기)")
    st.dataframe(df, use_container_width=True)

st.info(
    "TODO: mart_district_sales_trend / mart_district_risk 모델이 준비되면 "
    "pydeck 지도 시각화와 업종별 매출·위험도 차트를 이 대시보드에 추가하세요."
)
