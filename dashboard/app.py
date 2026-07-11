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

SALES_BY_GU_SQL = """
with latest as (
    select max(std_yyqu) as std_yyqu from stg_sales
)
select
    a.gu_name,
    sum(s.monthly_sales_amount) as total_sales_amount
from stg_sales s
inner join latest l on s.std_yyqu = l.std_yyqu
join stg_district_areas a on s.district_code = a.district_code
group by 1
order by 2 desc
"""

STORE_STRUCTURE_TREND_SQL = """
select
    std_yyqu,
    substr(std_yyqu, 1, 4) || ' Q' || substr(std_yyqu, 5, 1) as quarter_label,
    sum(franchise_store_count) / nullif(sum(store_count), 0) * 100 as franchise_ratio_pct,
    avg(open_rate) as avg_open_rate,
    avg(close_rate) as avg_close_rate
from stg_stores
group by 1, 2
order by 1
"""

GENDER_SALES_SQL = """
with latest as (select max(std_yyqu) as std_yyqu from stg_sales),
s as (select * from stg_sales where std_yyqu = (select std_yyqu from latest))
select '남성' as gender, sum(male_sales_amount) as sales_amount from s
union all
select '여성', sum(female_sales_amount) from s
"""

AGE_SALES_SQL = """
with latest as (select max(std_yyqu) as std_yyqu from stg_sales),
s as (select * from stg_sales where std_yyqu = (select std_yyqu from latest))
select '10대' as age_group, sum(age_10s_sales_amount) as sales_amount from s
union all select '20대', sum(age_20s_sales_amount) from s
union all select '30대', sum(age_30s_sales_amount) from s
union all select '40대', sum(age_40s_sales_amount) from s
union all select '50대', sum(age_50s_sales_amount) from s
union all select '60대 이상', sum(age_60s_plus_sales_amount) from s
"""

WEEKDAY_SALES_SQL = """
with latest as (select max(std_yyqu) as std_yyqu from stg_sales),
s as (select * from stg_sales where std_yyqu = (select std_yyqu from latest))
select '월' as weekday, sum(mon_sales_amount) as sales_amount from s
union all select '화', sum(tue_sales_amount) from s
union all select '수', sum(wed_sales_amount) from s
union all select '목', sum(thu_sales_amount) from s
union all select '금', sum(fri_sales_amount) from s
union all select '토', sum(sat_sales_amount) from s
union all select '일', sum(sun_sales_amount) from s
"""

TIME_SLOT_SALES_SQL = """
with latest as (select max(std_yyqu) as std_yyqu from stg_sales),
s as (select * from stg_sales where std_yyqu = (select std_yyqu from latest))
select '00-06시' as time_slot, sum(time_00_06_sales_amount) as sales_amount from s
union all select '06-11시', sum(time_06_11_sales_amount) from s
union all select '11-14시', sum(time_11_14_sales_amount) from s
union all select '14-17시', sum(time_14_17_sales_amount) from s
union all select '17-21시', sum(time_17_21_sales_amount) from s
union all select '21-24시', sum(time_21_24_sales_amount) from s
"""

CHANGE_INDEX_DIST_SQL = """
with latest as (select max(std_yyqu) as std_yyqu from stg_change_index)
select change_index_name, count(*) as district_count
from stg_change_index
where std_yyqu = (select std_yyqu from latest)
group by 1
order by 2 desc
"""

INDUSTRY_CLOSE_RATE_SQL = """
with latest as (select max(std_yyqu) as std_yyqu from stg_stores)
select
    industry_name,
    avg(close_rate) as avg_close_rate,
    sum(store_count) as total_store_count
from stg_stores
where std_yyqu = (select std_yyqu from latest)
group by 1
having sum(store_count) >= 50
order by 2 desc
limit 10
"""

INDUSTRY_SALES_PER_STORE_SQL = """
with latest as (select max(std_yyqu) as std_yyqu from mart_industry_competition)
select
    industry_name,
    avg(sales_per_store_amount) as avg_sales_per_store_amount,
    count(*) as district_count
from mart_industry_competition
where std_yyqu = (select std_yyqu from latest) and sales_per_store_amount is not null
group by 1
having count(*) >= 20
order by 2 desc
limit 10
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

        # 군집 id -> (라벨, 색상) 매핑은 전체 데이터 기준으로 한 번만 고정한다.
        # 필터링 후 남은 군집만으로 다시 계산하면, 필터를 바꿀 때마다 같은 군집이
        # 다른 색으로 보이는 문제(색상이 개체가 아니라 순위를 따라가는 문제)가 생긴다.
        all_cluster_ids = sorted(geo_df["cluster_id"].dropna().unique().tolist())
        palette_by_id = {
            cid: CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)] for i, cid in enumerate(all_cluster_ids)
        }
        hex_by_id = {cid: CLUSTER_HEX[i % len(CLUSTER_HEX)] for i, cid in enumerate(all_cluster_ids)}
        label_by_id = (
            geo_df.dropna(subset=["cluster_id"])
            .drop_duplicates("cluster_id")
            .set_index("cluster_id")["cluster_label"]
            .to_dict()
        )

        st.sidebar.header("지도 필터")
        color_mode = st.sidebar.radio("색상 기준", ["상권 유형(군집)", "위험도"], index=0)
        gu_options = ["전체"] + sorted(geo_df["gu_name"].dropna().unique().tolist())
        selected_gu = st.sidebar.selectbox("자치구", gu_options)
        risk_only = st.sidebar.checkbox("위험(watch) 상권만 보기", value=False)
        cluster_options = [f"군집 {int(cid)}: {label_by_id[cid]}" for cid in all_cluster_ids]
        selected_cluster_labels = st.sidebar.multiselect(
            "상권 유형(군집) 선택", cluster_options, default=cluster_options
        )
        selected_cluster_ids = {
            all_cluster_ids[cluster_options.index(opt)] for opt in selected_cluster_labels
        }

        filtered = geo_df
        if selected_gu != "전체":
            filtered = filtered[filtered["gu_name"] == selected_gu]
        if risk_only:
            filtered = filtered[filtered["heuristic_risk_flag"] == "watch"]
        filtered = filtered[filtered["cluster_id"].isin(selected_cluster_ids)]

        filtered = filtered.copy()
        if color_mode == "위험도":
            filtered["color"] = filtered["heuristic_risk_flag"].map(RISK_COLOR).apply(
                lambda c: c if isinstance(c, list) else [150, 150, 150, 140]
            )
        else:
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
            legend_cols = st.columns(len(all_cluster_ids) or 1)
            for col, cid in zip(legend_cols, all_cluster_ids):
                col.markdown(
                    f"<span style='color:{hex_by_id[cid]}'>●</span> **군집 {int(cid)}**<br/>{label_by_id[cid]}",
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

    st.divider()
    st.subheader("상권 운영 특성 추이")
    st.caption("franchise_ratio는 전체 점포 대비 프랜차이즈 점포 비중(가중평균), 창업률·폐업률은 상권×업종별 비율의 단순평균입니다 — 계산 기준이 달라 세 지표를 한 축에 같이 그리지 않았습니다.")
    store_trend_df = con.execute(STORE_STRUCTURE_TREND_SQL).fetchdf()
    op_col1, op_col2, op_col3 = st.columns(3)
    with op_col1:
        franchise_chart = (
            alt.Chart(store_trend_df)
            .mark_line(color=BLUE, strokeWidth=2, point=alt.OverlayMarkDef(color=BLUE, size=35))
            .encode(
                x=alt.X("quarter_label:N", title=None, sort=None),
                y=alt.Y("franchise_ratio_pct:Q", title="프랜차이즈 비율(%)"),
                tooltip=[alt.Tooltip("quarter_label:N", title="분기"), alt.Tooltip("franchise_ratio_pct:Q", title="비율(%)", format=".2f")],
            )
            .properties(height=240, title="프랜차이즈 비율")
        )
        st.altair_chart(franchise_chart, use_container_width=True)
    with op_col2:
        open_chart = (
            alt.Chart(store_trend_df)
            .mark_line(color=BLUE, strokeWidth=2, point=alt.OverlayMarkDef(color=BLUE, size=35))
            .encode(
                x=alt.X("quarter_label:N", title=None, sort=None),
                y=alt.Y("avg_open_rate:Q", title="평균 창업률(%)"),
                tooltip=[alt.Tooltip("quarter_label:N", title="분기"), alt.Tooltip("avg_open_rate:Q", title="창업률(%)", format=".2f")],
            )
            .properties(height=240, title="평균 창업률")
        )
        st.altair_chart(open_chart, use_container_width=True)
    with op_col3:
        close_chart = (
            alt.Chart(store_trend_df)
            .mark_line(color=BLUE, strokeWidth=2, point=alt.OverlayMarkDef(color=BLUE, size=35))
            .encode(
                x=alt.X("quarter_label:N", title=None, sort=None),
                y=alt.Y("avg_close_rate:Q", title="평균 폐업률(%)"),
                tooltip=[alt.Tooltip("quarter_label:N", title="분기"), alt.Tooltip("avg_close_rate:Q", title="폐업률(%)", format=".2f")],
            )
            .properties(height=240, title="평균 폐업률")
        )
        st.altair_chart(close_chart, use_container_width=True)

    st.divider()
    st.subheader("지역별 매출·유동인구 (당분기)")
    gu_col1, gu_col2 = st.columns(2)
    with gu_col1:
        sales_gu_df = con.execute(SALES_BY_GU_SQL).fetchdf()
        sales_gu_chart = (
            alt.Chart(sales_gu_df)
            .mark_bar(color=BLUE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("total_sales_amount:Q", title="매출(원)"),
                y=alt.Y("gu_name:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("gu_name:N", title="자치구"),
                    alt.Tooltip("total_sales_amount:Q", title="매출", format=",.0f"),
                ],
            )
            .properties(height=560, title="자치구별 매출")
        )
        st.altair_chart(sales_gu_chart, use_container_width=True)
    with gu_col2:
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
            .properties(height=560, title="자치구별 유동인구")
        )
        st.altair_chart(footfall_gu_chart, use_container_width=True)

    st.divider()
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

    st.divider()
    st.subheader("업종 리스크·효율 랭킹 (당분기)")
    st.caption("표본이 너무 작은 업종의 노이즈를 줄이기 위해, 전체 점포 수 50개 이상(폐업률) / 관측 상권 수 20개 이상(점포당 매출) 업종만 포함했습니다.")
    risk_col1, risk_col2 = st.columns(2)
    with risk_col1:
        close_rate_df = con.execute(INDUSTRY_CLOSE_RATE_SQL).fetchdf()
        close_rate_chart = (
            alt.Chart(close_rate_df)
            .mark_bar(color=CRITICAL_RED, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("avg_close_rate:Q", title="평균 폐업률(%)"),
                y=alt.Y("industry_name:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("industry_name:N", title="업종"),
                    alt.Tooltip("avg_close_rate:Q", title="폐업률(%)", format=".2f"),
                    alt.Tooltip("total_store_count:Q", title="전체 점포 수", format=",.0f"),
                ],
            )
            .properties(height=320, title="폐업률 상위 10개 업종")
        )
        st.altair_chart(close_rate_chart, use_container_width=True)
    with risk_col2:
        sales_per_store_df = con.execute(INDUSTRY_SALES_PER_STORE_SQL).fetchdf()
        sales_per_store_chart = (
            alt.Chart(sales_per_store_df)
            .mark_bar(color=BLUE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("avg_sales_per_store_amount:Q", title="점포당 매출(원)"),
                y=alt.Y("industry_name:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("industry_name:N", title="업종"),
                    alt.Tooltip("avg_sales_per_store_amount:Q", title="점포당 매출", format=",.0f"),
                    alt.Tooltip("district_count:Q", title="관측 상권 수", format=",.0f"),
                ],
            )
            .properties(height=320, title="점포당 매출 상위 10개 업종")
        )
        st.altair_chart(sales_per_store_chart, use_container_width=True)

    st.divider()
    st.subheader("고객층 구성 (당분기 매출 기준)")
    demo_col1, demo_col2 = st.columns(2)
    with demo_col1:
        gender_df = con.execute(GENDER_SALES_SQL).fetchdf()
        gender_chart = (
            alt.Chart(gender_df)
            .mark_bar(color=BLUE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("sales_amount:Q", title="매출(원)"),
                y=alt.Y("gender:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("gender:N", title="성별"),
                    alt.Tooltip("sales_amount:Q", title="매출", format=",.0f"),
                ],
            )
            .properties(height=160, title="성별 매출 비중")
        )
        st.altair_chart(gender_chart, use_container_width=True)
    with demo_col2:
        age_df = con.execute(AGE_SALES_SQL).fetchdf()
        age_order = ["10대", "20대", "30대", "40대", "50대", "60대 이상"]
        age_chart = (
            alt.Chart(age_df)
            .mark_bar(color=BLUE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("age_group:N", title=None, sort=age_order),
                y=alt.Y("sales_amount:Q", title="매출(원)"),
                tooltip=[
                    alt.Tooltip("age_group:N", title="연령대"),
                    alt.Tooltip("sales_amount:Q", title="매출", format=",.0f"),
                ],
            )
            .properties(height=280, title="연령대별 매출 비중")
        )
        st.altair_chart(age_chart, use_container_width=True)

    st.divider()
    st.subheader("매출 시간 패턴 (당분기)")
    time_col1, time_col2 = st.columns(2)
    with time_col1:
        weekday_df = con.execute(WEEKDAY_SALES_SQL).fetchdf()
        weekday_order = ["월", "화", "수", "목", "금", "토", "일"]
        weekday_chart = (
            alt.Chart(weekday_df)
            .mark_bar(color=BLUE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("weekday:N", title=None, sort=weekday_order),
                y=alt.Y("sales_amount:Q", title="매출(원)"),
                tooltip=[
                    alt.Tooltip("weekday:N", title="요일"),
                    alt.Tooltip("sales_amount:Q", title="매출", format=",.0f"),
                ],
            )
            .properties(height=280, title="요일별 매출")
        )
        st.altair_chart(weekday_chart, use_container_width=True)
    with time_col2:
        time_slot_df = con.execute(TIME_SLOT_SALES_SQL).fetchdf()
        time_slot_order = ["00-06시", "06-11시", "11-14시", "14-17시", "17-21시", "21-24시"]
        time_slot_chart = (
            alt.Chart(time_slot_df)
            .mark_bar(color=BLUE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("time_slot:N", title=None, sort=time_slot_order),
                y=alt.Y("sales_amount:Q", title="매출(원)"),
                tooltip=[
                    alt.Tooltip("time_slot:N", title="시간대"),
                    alt.Tooltip("sales_amount:Q", title="매출", format=",.0f"),
                ],
            )
            .properties(height=280, title="시간대별 매출")
        )
        st.altair_chart(time_slot_chart, use_container_width=True)

    st.divider()
    st.subheader("상권변화지표 등급 분포 (당분기)")
    st.caption("LL/HH는 지표상 신규·기존 진입 모두 주의가 필요한 등급, LH/HL은 각각 신규·기존 상점에 유리한 등급입니다.")
    change_index_df = con.execute(CHANGE_INDEX_DIST_SQL).fetchdf()
    change_index_chart = (
        alt.Chart(change_index_df)
        .mark_bar(color=BLUE, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            x=alt.X("district_count:Q", title="상권 수"),
            y=alt.Y("change_index_name:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("change_index_name:N", title="등급"),
                alt.Tooltip("district_count:Q", title="상권 수", format=",.0f"),
            ],
        )
        .properties(height=200)
    )
    st.altair_chart(change_index_chart, use_container_width=True)

with data_tab:
    st.sidebar.header("데이터 미리보기")
    selected = st.sidebar.selectbox("테이블 선택", table_names)
    if selected:
        df = con.execute(f"SELECT * FROM {selected} LIMIT 500").fetchdf()
        st.subheader(f"{selected} ({len(df)}행 미리보기)")
        st.dataframe(df, use_container_width=True)
