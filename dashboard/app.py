"""서울시 상권분석 대시보드.

데이터 수집(scripts/fetch_seoul_data.py) 및 dbt run 이후 실행하세요:
    streamlit run dashboard/app.py
"""
from pathlib import Path

import altair as alt
import duckdb
import pydeck as pdk
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "seoul_commercial.duckdb"

BLUE = "#2a78d6"
CRITICAL_RED = "#d03b3b"

RISK_COLOR = {
    "watch": [208, 59, 59, 190],
    "normal": [42, 120, 214, 140],
}

# 카테고리컬 팔레트 (고정 순서 — CVD-safe로 검증된 순서를 그대로 사용)
CLUSTER_PALETTE = [
    [42, 120, 214, 190],   # blue
    [27, 175, 122, 190],   # aqua
    [237, 161, 0, 190],    # yellow
    [0, 131, 0, 190],      # green
    [74, 58, 167, 190],    # violet
    [227, 73, 72, 190],    # red
    [232, 123, 164, 190],  # magenta
    [235, 104, 52, 190],   # orange
]
CLUSTER_HEX = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]

SALES_TREND_SQL = """
select
    std_yyqu,
    substr(std_yyqu, 1, 4) || ' Q' || substr(std_yyqu, 5, 1) as quarter_label,
    sum(monthly_sales_amount) as total_sales_amount
from stg_sales
group by 1, 2
order by 1
"""

FOOTFALL_TREND_SQL = """
select
    std_yyqu,
    substr(std_yyqu, 1, 4) || ' Q' || substr(std_yyqu, 5, 1) as quarter_label,
    sum(total_footfall_count) as total_footfall_count
from stg_footfall
group by 1, 2
order by 1
"""

TOP_INDUSTRIES_SQL = """
with latest as (
    select max(std_yyqu) as std_yyqu from stg_sales
)
select
    s.industry_name,
    sum(s.monthly_sales_amount) as total_sales_amount
from stg_sales s
inner join latest l on s.std_yyqu = l.std_yyqu
join stg_district_areas a on s.district_code = a.district_code
where (? = '전체' or a.gu_name = ?)
group by 1
order by 2 desc
limit 10
"""

FOOTFALL_BY_GU_SQL = """
with latest as (
    select max(std_yyqu) as std_yyqu from stg_footfall
)
select
    a.gu_name,
    sum(f.total_footfall_count) as total_footfall_count
from stg_footfall f
inner join latest l on f.std_yyqu = l.std_yyqu
join stg_district_areas a on f.district_code = a.district_code
group by 1
order by 2 desc
"""

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

if "mart_district_map" in table_names:
    kpi = con.execute(
        """
        select
            count(*) as district_count,
            sum(case when heuristic_risk_flag = 'watch' then 1 else 0 end) as watch_count,
            sum(total_monthly_sales_amount) as total_sales_amount
        from mart_district_map
        """
    ).fetchone()
    latest_footfall = con.execute(
        "select sum(total_footfall_count) from stg_footfall "
        "where std_yyqu = (select max(std_yyqu) from stg_footfall)"
    ).fetchone()[0]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("전체 상권 수", f"{kpi[0]:,}")
    k2.metric("위험(watch) 상권", f"{kpi[1]:,}", f"{kpi[1] / kpi[0] * 100:.1f}%")
    k3.metric("당분기 합산 매출", f"{kpi[2] / 1e8:,.0f}억원")
    k4.metric("당분기 합산 유동인구", f"{latest_footfall / 1e6:,.1f}백만명")

map_tab, trend_tab, data_tab = st.tabs(["지도", "트렌드", "데이터 미리보기"])

with map_tab:
    if "mart_district_map" not in table_names:
        st.warning("mart_district_map 테이블이 없습니다. dbt/ 디렉토리에서 `dbt run`을 실행하세요.")
    else:
        geo_df = con.execute("SELECT * FROM mart_district_map").fetchdf()

        st.sidebar.header("지도 필터")
        color_mode = st.sidebar.radio("색상 기준", ["상권 유형(군집)", "위험도"], index=0)
        gu_options = ["전체"] + sorted(geo_df["gu_name"].dropna().unique().tolist())
        selected_gu = st.sidebar.selectbox("자치구", gu_options)
        risk_only = st.sidebar.checkbox("위험(watch) 상권만 보기", value=False)

        filtered = geo_df
        if selected_gu != "전체":
            filtered = filtered[filtered["gu_name"] == selected_gu]
        if risk_only:
            filtered = filtered[filtered["heuristic_risk_flag"] == "watch"]

        filtered = filtered.copy()
        cluster_label_by_id: dict[int, str] = {}
        if color_mode == "위험도":
            filtered["color"] = filtered["heuristic_risk_flag"].map(RISK_COLOR).apply(
                lambda c: c if isinstance(c, list) else [150, 150, 150, 140]
            )
        else:
            cluster_ids = sorted(filtered["cluster_id"].dropna().unique().tolist())
            palette_by_id = {
                cid: CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)] for i, cid in enumerate(cluster_ids)
            }
            cluster_label_by_id = (
                filtered.dropna(subset=["cluster_id"])
                .drop_duplicates("cluster_id")
                .set_index("cluster_id")["cluster_label"]
                .to_dict()
            )
            filtered["color"] = filtered["cluster_id"].map(palette_by_id).apply(
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
                "상권 유형: {cluster_label}<br/>"
                "상권변화지표: {change_index_name}<br/>"
                "유동인구 QoQ: {qoq_footfall_growth_pct}%<br/>"
                "위험 플래그: {heuristic_risk_flag}<br/>"
                "당분기 매출: {total_monthly_sales_amount}"
            )
        }
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip))

        if color_mode == "위험도":
            legend_cols = st.columns(2)
            legend_cols[0].markdown("🔴 **watch** — 상권변화지표 LL/HH + 유동인구 감소")
            legend_cols[1].markdown("🔵 **normal** — 그 외")
        else:
            st.caption("상권 특성(매출·유동인구·점포구조 등) 기준 K-means 군집 — 위치가 아니라 성격이 비슷한 상권끼리 묶은 결과입니다.")
            legend_cols = st.columns(len(cluster_label_by_id) or 1)
            for col, (cid, label) in zip(legend_cols, sorted(cluster_label_by_id.items())):
                hex_color = CLUSTER_HEX[cluster_ids.index(cid) % len(CLUSTER_HEX)]
                col.markdown(
                    f"<span style='color:{hex_color}'>●</span> **군집 {int(cid)}**<br/>{label}",
                    unsafe_allow_html=True,
                )

with trend_tab:
    st.subheader("서울 전체 분기별 매출 추이")
    sales_trend_df = con.execute(SALES_TREND_SQL).fetchdf()
    sales_chart = (
        alt.Chart(sales_trend_df)
        .mark_line(color=BLUE, strokeWidth=2, point=alt.OverlayMarkDef(color=BLUE, size=45))
        .encode(
            x=alt.X("quarter_label:N", title=None, sort=None),
            y=alt.Y("total_sales_amount:Q", title="분기 합산 매출(원)"),
            tooltip=[
                alt.Tooltip("quarter_label:N", title="분기"),
                alt.Tooltip("total_sales_amount:Q", title="매출", format=",.0f"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(sales_chart, use_container_width=True)

    st.subheader("서울 전체 분기별 유동인구 추이")
    st.caption("상권별 추정 유동인구를 단순 합산한 값으로, 여러 상권을 오간 인원이 중복 집계될 수 있는 추정치입니다.")
    footfall_trend_df = con.execute(FOOTFALL_TREND_SQL).fetchdf()
    footfall_chart = (
        alt.Chart(footfall_trend_df)
        .mark_line(color=BLUE, strokeWidth=2, point=alt.OverlayMarkDef(color=BLUE, size=45))
        .encode(
            x=alt.X("quarter_label:N", title=None, sort=None),
            y=alt.Y("total_footfall_count:Q", title="분기 합산 유동인구(명)"),
            tooltip=[
                alt.Tooltip("quarter_label:N", title="분기"),
                alt.Tooltip("total_footfall_count:Q", title="유동인구", format=",.0f"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(footfall_chart, use_container_width=True)

    st.subheader("자치구별 유동인구 (당분기)")
    footfall_gu_df = con.execute(FOOTFALL_BY_GU_SQL).fetchdf()
    footfall_gu_chart = (
        alt.Chart(footfall_gu_df)
        .mark_bar(color=BLUE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            x=alt.X("total_footfall_count:Q", title="유동인구(명)"),
            y=alt.Y("gu_name:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("gu_name:N", title="자치구"),
                alt.Tooltip("total_footfall_count:Q", title="유동인구", format=",.0f"),
            ],
        )
        .properties(height=560)
    )
    st.altair_chart(footfall_gu_chart, use_container_width=True)

    st.subheader("지역별 매출 상위 10개 업종 (당분기)")
    gu_list_df = con.execute(
        "select distinct gu_name from stg_district_areas where gu_name is not null order by 1"
    ).fetchdf()
    gu_options_trend = ["전체"] + gu_list_df["gu_name"].tolist()
    selected_gu_trend = st.selectbox("자치구 선택", gu_options_trend, key="trend_gu_filter")

    industry_df = con.execute(TOP_INDUSTRIES_SQL, [selected_gu_trend, selected_gu_trend]).fetchdf()
    if industry_df.empty:
        st.info("선택한 자치구에 해당하는 매출 데이터가 없습니다.")
    else:
        industry_chart = (
            alt.Chart(industry_df)
            .mark_bar(color=BLUE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("total_sales_amount:Q", title="매출(원)"),
                y=alt.Y("industry_name:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("industry_name:N", title="업종"),
                    alt.Tooltip("total_sales_amount:Q", title="매출", format=",.0f"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(industry_chart, use_container_width=True)

with data_tab:
    st.sidebar.header("데이터 미리보기")
    selected = st.sidebar.selectbox("테이블 선택", table_names)
    if selected:
        df = con.execute(f"SELECT * FROM {selected} LIMIT 500").fetchdf()
        st.subheader(f"{selected} ({len(df)}행 미리보기)")
        st.dataframe(df, use_container_width=True)
