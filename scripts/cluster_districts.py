"""상권 특성 기반 K-means 군집화.

매출·유동인구·점포 구조 지표로 상권을 몇 개의 '유형'으로 묶는다(위치가 아니라
특성 기준 군집). k는 3~8 범위에서 실루엣 점수가 가장 높은 값을 자동 선택하고,
각 군집은 표준화된 피처 평균 중 가장 튀는 지표로 사람이 읽을 수 있는 라벨을
자동 생성한다. 결과는 raw_district_clusters 테이블로 DuckDB에 적재되어
dbt staging/mart에서 이어받는다.

raw_* 테이블(원본 API 응답)을 직접 읽는다 — stg_* dbt 뷰가 아니다. 이 스크립트의
출력을 dbt의 stg_district_clusters/mart_district_map이 다시 참조하기 때문에,
dbt 뷰에 의존하면 "dbt run이 있어야 이 스크립트가 돌고, 이 스크립트가 있어야
dbt run이 끝까지 돈다"는 순환이 생긴다. 그래서 fetch_seoul_data.py 직후,
dbt run 이전에 실행 가능하도록 raw 레이어만 사용한다.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "seoul_commercial.duckdb"

FEATURE_PANEL_SQL = """
with latest as (
    select max(STDR_YYQU_CD) as std_yyqu from raw_sales
),
sales as (
    select
        TRDAR_CD as district_code,
        sum(THSMON_SELNG_AMT) as total_sales_amount,
        count(distinct SVC_INDUTY_CD) as industry_count
    from raw_sales
    where STDR_YYQU_CD = (select std_yyqu from latest)
    group by 1
),
footfall as (
    select TRDAR_CD as district_code, TOT_FLPOP_CO as total_footfall_count
    from raw_footfall
    where STDR_YYQU_CD = (select std_yyqu from latest)
),
stores as (
    select
        TRDAR_CD as district_code,
        sum(STOR_CO) as total_store_count,
        sum(FRC_STOR_CO) as total_franchise_store_count,
        avg(OPBIZ_RT) as avg_open_rate,
        avg(CLSBIZ_RT) as avg_close_rate
    from raw_stores
    where STDR_YYQU_CD = (select std_yyqu from latest)
    group by 1
),
change_index as (
    select
        TRDAR_CD as district_code,
        OPR_SALE_MT_AVRG as avg_operating_months_open,
        CLS_SALE_MT_AVRG as avg_operating_months_closed
    from raw_change_index
    where STDR_YYQU_CD = (select std_yyqu from latest)
)
select
    f.district_code,
    f.total_footfall_count,
    s.total_sales_amount,
    s.industry_count,
    st.total_store_count,
    st.total_franchise_store_count,
    st.avg_open_rate,
    st.avg_close_rate,
    ci.avg_operating_months_open,
    ci.avg_operating_months_closed
from footfall f
left join sales s on f.district_code = s.district_code
left join stores st on f.district_code = st.district_code
left join change_index ci on f.district_code = ci.district_code
"""

FEATURE_COLUMNS = [
    "total_footfall_count",
    "total_sales_amount",
    "industry_count",
    "total_store_count",
    "franchise_ratio",
    "avg_open_rate",
    "avg_close_rate",
    "avg_operating_months_open",
    "avg_operating_months_closed",
]

# 각 피처가 z-score로 높을 때 / 낮을 때 붙일 한글 설명
FEATURE_PHRASES = {
    "total_footfall_count": ("고유동인구", "저유동인구"),
    "total_sales_amount": ("고매출", "저매출"),
    "industry_count": ("업종 다양", "업종 단조"),
    "total_store_count": ("점포 밀집", "점포 희소"),
    "franchise_ratio": ("프랜차이즈 중심", "개인상점 중심"),
    "avg_open_rate": ("신규창업 활발", "창업 저조"),
    "avg_close_rate": ("폐업률 높음", "폐업률 낮음"),
    "avg_operating_months_open": ("장기생존형", "단기회전형"),
    "avg_operating_months_closed": ("폐업까지 장기", "폐업까지 단기"),
}


def build_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute(FEATURE_PANEL_SQL).fetchdf()
    df["franchise_ratio"] = df["total_franchise_store_count"] / df["total_store_count"].replace(0, pd.NA)
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].fillna(df[FEATURE_COLUMNS].median())
    return df


def pick_best_k(x_scaled, k_range=range(3, 9)) -> tuple[int, dict[int, float]]:
    scores = {}
    for k in k_range:
        labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(x_scaled)
        scores[k] = silhouette_score(x_scaled, labels)
    best_k = max(scores, key=scores.get)
    return best_k, scores


def label_clusters(centroids_z: pd.DataFrame) -> dict[int, str]:
    labels = {}
    for cluster_id, row in centroids_z.iterrows():
        ranked = row.abs().sort_values(ascending=False)
        top_features = ranked.index[:2]
        parts = []
        for feat in top_features:
            high_phrase, low_phrase = FEATURE_PHRASES[feat]
            parts.append(high_phrase if row[feat] >= 0 else low_phrase)
        labels[cluster_id] = " · ".join(parts)
    return labels


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    df = build_features(con)

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(df[FEATURE_COLUMNS])

    best_k, scores = pick_best_k(x_scaled)
    print("silhouette scores by k:", {k: round(v, 3) for k, v in scores.items()})
    print(f"selected k = {best_k}")

    model = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df["cluster_id"] = model.fit_predict(x_scaled)

    centroids_z = pd.DataFrame(model.cluster_centers_, columns=FEATURE_COLUMNS)
    label_map = label_clusters(centroids_z)
    df["cluster_label"] = df["cluster_id"].map(label_map)

    print("\ncluster sizes and labels:")
    print(df.groupby(["cluster_id", "cluster_label"]).size().rename("district_count"))

    out_cols = ["district_code", "cluster_id", "cluster_label", *FEATURE_COLUMNS]
    result = df[out_cols]
    con.execute("CREATE OR REPLACE TABLE raw_district_clusters AS SELECT * FROM result")
    con.close()
    print(f"\nsaved raw_district_clusters ({len(result)} rows) to {DB_PATH}")


if __name__ == "__main__":
    main()
