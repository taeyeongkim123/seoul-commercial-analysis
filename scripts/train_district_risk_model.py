"""상권 유동인구 감소(쇠퇴 조짐) 예측 모델.

과제 정의: 분기 t 시점에 관측 가능한 상권 지표(매출, 점포, 상권변화지표 등)만으로
"다음 분기(t+1)에 이 상권의 유동인구가 감소할 것인가"를 이진 분류로 예측한다.
t 시점 정보만 피처로 쓰고 라벨은 t+1 값으로 만들어 미래 정보 누수를 피했고,
평가는 랜덤 분할이 아니라 마지막 두 분기 전이를 홀드아웃하는 시계열 분할로 검증한다.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "seoul_commercial.duckdb"
MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
TEST_QUARTERS = ["20252", "20253"]  # 이 분기 -> 다음 분기 전이를 테스트셋으로 홀드아웃

FEATURE_PANEL_SQL = """
with footfall as (
    select std_yyqu, district_code, total_footfall_count
    from stg_footfall
),
sales as (
    select
        std_yyqu,
        district_code,
        sum(monthly_sales_amount) as total_sales_amount,
        count(distinct industry_code) as industry_count
    from stg_sales
    group by 1, 2
),
stores as (
    select
        std_yyqu,
        district_code,
        sum(store_count) as total_store_count,
        sum(franchise_store_count) as total_franchise_store_count,
        avg(open_rate) as avg_open_rate,
        avg(close_rate) as avg_close_rate
    from stg_stores
    group by 1, 2
),
change_index as (
    select
        std_yyqu,
        district_code,
        change_index_code,
        avg_operating_months_open,
        avg_operating_months_closed
    from stg_change_index
),
panel as (
    select
        f.std_yyqu,
        f.district_code,
        f.total_footfall_count,
        s.total_sales_amount,
        s.industry_count,
        st.total_store_count,
        st.total_franchise_store_count,
        st.avg_open_rate,
        st.avg_close_rate,
        ci.change_index_code,
        ci.avg_operating_months_open,
        ci.avg_operating_months_closed
    from footfall f
    left join sales s on f.std_yyqu = s.std_yyqu and f.district_code = s.district_code
    left join stores st on f.std_yyqu = st.std_yyqu and f.district_code = st.district_code
    left join change_index ci on f.std_yyqu = ci.std_yyqu and f.district_code = ci.district_code
)
select
    *,
    lag(total_sales_amount) over (
        partition by district_code order by std_yyqu
    ) as prev_quarter_sales_amount,
    lead(total_footfall_count) over (
        partition by district_code order by std_yyqu
    ) as next_quarter_footfall_count
from panel
"""


def build_feature_panel(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute(FEATURE_PANEL_SQL).fetchdf()

    df["sales_qoq_growth_pct"] = (
        (df["total_sales_amount"] - df["prev_quarter_sales_amount"])
        / df["prev_quarter_sales_amount"].replace(0, pd.NA)
        * 100
    )
    df["franchise_ratio"] = df["total_franchise_store_count"] / df["total_store_count"].replace(0, pd.NA)

    # label: 다음 분기 유동인구가 이번 분기보다 감소하면 1
    df = df.dropna(subset=["next_quarter_footfall_count"]).copy()
    df["label_footfall_decline"] = (
        df["next_quarter_footfall_count"] < df["total_footfall_count"]
    ).astype(int)

    return df


FEATURE_COLUMNS = [
    "total_footfall_count",
    "total_sales_amount",
    "sales_qoq_growth_pct",
    "industry_count",
    "total_store_count",
    "franchise_ratio",
    "avg_open_rate",
    "avg_close_rate",
    "avg_operating_months_open",
    "avg_operating_months_closed",
]


def prepare_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    change_index_dummies = pd.get_dummies(df["change_index_code"], prefix="change_index")
    quarter_of_year = df["std_yyqu"].str[-1].rename("quarter_of_year")
    quarter_dummies = pd.get_dummies(quarter_of_year, prefix="q")
    x = pd.concat([df[FEATURE_COLUMNS], change_index_dummies, quarter_dummies], axis=1)
    x = x.fillna(x.median(numeric_only=True))
    y = df["label_footfall_decline"]
    return x, y


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    panel = build_feature_panel(con)
    con.close()

    train_df = panel[~panel["std_yyqu"].isin(TEST_QUARTERS)]
    test_df = panel[panel["std_yyqu"].isin(TEST_QUARTERS)]

    x_train, y_train = prepare_xy(train_df)
    x_test, y_test = prepare_xy(test_df)
    x_test = x_test.reindex(columns=x_train.columns, fill_value=0)  # 테스트셋에 없는 change_index 카테고리 대비

    print(f"train: {len(x_train)} rows ({train_df['std_yyqu'].min()}~{train_df['std_yyqu'].max()})")
    print(f"test:  {len(x_test)} rows (quarters {TEST_QUARTERS})")
    print(f"train label rate (decline=1): {y_train.mean():.3f}")
    print(f"test  label rate (decline=1): {y_test.mean():.3f}")

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=20,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)

    pred = model.predict(x_test)
    pred_proba = model.predict_proba(x_test)[:, 1]

    print("\n=== Test set evaluation ===")
    print(f"accuracy: {accuracy_score(y_test, pred):.3f}")
    print(f"roc_auc:  {roc_auc_score(y_test, pred_proba):.3f}")
    print("\nclassification report:")
    print(classification_report(y_test, pred, target_names=["stable/growth", "decline"]))
    print("confusion matrix (rows=actual, cols=predicted):")
    print(confusion_matrix(y_test, pred))

    importances = (
        pd.Series(model.feature_importances_, index=x_train.columns)
        .sort_values(ascending=False)
    )
    print("\ntop feature importances:")
    print(importances.head(10))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_DIR / "district_footfall_decline_model.joblib")

    report_lines = [
        "# 상권 유동인구 감소 예측 모델 리포트",
        "",
        f"- 학습 데이터: {len(x_train)}행 ({train_df['std_yyqu'].min()}~{train_df['std_yyqu'].max()} 분기)",
        f"- 테스트 데이터: {len(x_test)}행 (분기 {', '.join(TEST_QUARTERS)} -> 다음 분기 전이, 시계열 홀드아웃)",
        f"- accuracy: {accuracy_score(y_test, pred):.3f}",
        f"- roc_auc: {roc_auc_score(y_test, pred_proba):.3f}",
        "",
        "## 해석",
        "",
        "ROC-AUC가 0.5(랜덤)에 가깝다. 즉 이 피처들(매출, 점포수, 프랜차이즈 비율, "
        "상권변화지표, 분기)만으로는 **분기 대비 유동인구 증감 방향**을 안정적으로 "
        "맞추기 어렵다는 것이 이 실험의 정직한 결론이다. 원인으로 추정되는 것:",
        "",
        "- 유동인구 QoQ 등락은 날씨·이벤트·거시경제 같은 데이터셋 밖의 요인 비중이 클 가능성이 높다.",
        "- 라벨(등락 방향)이 이진화되면서 등락폭이 작은 '노이즈성 반전'까지 전부 같은 비중으로 취급된다.",
        "- 개선 방향: 등락 방향 대신 등락폭(회귀)으로 문제를 바꾸거나, 계절성/공휴일 캘린더·인접 상권 "
        "  스필오버 피처를 추가하거나, 임계값을 둬서 '유의미한 감소'만 라벨링하는 방법을 시도할 수 있다.",
        "",
        "## Feature importance (top 10)",
        "",
        "| feature | importance |",
        "|---|---|",
    ]
    for name, val in importances.head(10).items():
        report_lines.append(f"| {name} | {val:.4f} |")
    (MODEL_DIR / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"\nsaved model -> {MODEL_DIR / 'district_footfall_decline_model.joblib'}")
    print(f"saved report -> {MODEL_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
