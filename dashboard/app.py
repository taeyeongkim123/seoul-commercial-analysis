"""서울시 상권분석 대시보드.

데이터 수집(scripts/fetch_seoul_data.py) 및 dbt run 이후 실행하세요:
    streamlit run dashboard/app.py
"""
from pathlib import Path

import duckdb
import pydeck as pdk
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "seoul_commercial.duckdb"

RISK_COLOR = {
    "watch": [220, 80, 80, 180],
    "normal": [60, 140, 200, 160],
}

st.set_page_config(page_title="서울시 상권분석", layout="wide")
st.title("서울시 상권분석 대시보드")

if not DB_PATH.exists():
    st.warning(
        "DuckDB 파일이 없습니다. 먼저 `python scripts/fetch_seoul_data.py`와 "
        "`dbt run`(dbt/ 디렉토리에서)을 실행하세요."
    )
    st.stop()

con = duckdb.connect(str(DB_PATH), read_only=True)
table_names = [t[0] for t in con.execute("SHOW TABLES").fetchall()]

map_tab, data_tab = st.tabs(["지도", "데이터 미리보기"])

with map_tab:
    if "mart_district_map" not in table_names:
        st.warning("mart_district_map 테이블이 없습니다. dbt/ 디렉토리에서 `dbt run`을 실행하세요.")
    else:
        geo_df = con.execute("SELECT * FROM mart_district_map").fetchdf()

        st.sidebar.header("지도 필터")
        gu_options = ["전체"] + sorted(geo_df["gu_name"].dropna().unique().tolist())
        selected_gu = st.sidebar.selectbox("자치구", gu_options)
        risk_only = st.sidebar.checkbox("위험(watch) 상권만 보기", value=False)

        filtered = geo_df
        if selected_gu != "전체":
            filtered = filtered[filtered["gu_name"] == selected_gu]
        if risk_only:
            filtered = filtered[filtered["heuristic_risk_flag"] == "watch"]

        filtered = filtered.copy()
        filtered["color"] = filtered["heuristic_risk_flag"].map(RISK_COLOR).apply(
            lambda c: c if isinstance(c, list) else [150, 150, 150, 140]
        )
        filtered["radius"] = (
            filtered["total_monthly_sales_amount"].fillna(0).clip(lower=0) ** 0.5 / 40
        ).clip(lower=30, upper=400)

        st.caption(f"{len(filtered)}개 상권 표시 중 (전체 {len(geo_df)}개)")

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=filtered,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius="radius",
            pickable=True,
            opacity=0.7,
        )
        view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10.5)
        tooltip = {
            "html": (
                "<b>{district_name}</b> ({district_type_name})<br/>"
                "자치구: {gu_name}<br/>"
                "상권변화지표: {change_index_name}<br/>"
                "유동인구 QoQ: {qoq_footfall_growth_pct}%<br/>"
                "위험 플래그: {heuristic_risk_flag}<br/>"
                "당분기 매출: {total_monthly_sales_amount}"
            )
        }
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip))

        legend_cols = st.columns(2)
        legend_cols[0].markdown("🔴 **watch** — 상권변화지표 LL/HH + 유동인구 감소")
        legend_cols[1].markdown("🔵 **normal** — 그 외")

with data_tab:
    st.sidebar.header("데이터 미리보기")
    selected = st.sidebar.selectbox("테이블 선택", table_names)
    if selected:
        df = con.execute(f"SELECT * FROM {selected} LIMIT 500").fetchdf()
        st.subheader(f"{selected} ({len(df)}행 미리보기)")
        st.dataframe(df, use_container_width=True)
