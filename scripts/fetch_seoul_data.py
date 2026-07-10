"""서울 열린데이터광장 상권분석 API 수집 스크립트.

서울 열린데이터광장은 요청당 최대 1000건까지 반환하므로,
list_total_count를 확인하며 1000건 단위로 페이지네이션한다.
"""
import json
import os
import time
from pathlib import Path

import duckdb
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["SEOUL_API_KEY"]
BASE_URL = "http://openapi.seoul.go.kr:8088"
PAGE_SIZE = 1000

# 서비스명: (API 서비스 ID, 결과가 담기는 최상위 키는 서비스 ID와 동일)
SERVICES = {
    "sales": "VwsmTrdarSelngQq",       # 상권별 추정매출
    "footfall": "VwsmTrdarFlpopQq",    # 상권별 추정 유동인구
    "change_index": "VwsmTrdarChgIx",  # 상권변화지표
    "stores": "VwsmTrdarStorQq",       # 상권-점포 정보
}

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "seoul_commercial.duckdb"


def fetch_service(service_id: str) -> list[dict]:
    rows: list[dict] = []
    start = 1
    while True:
        end = start + PAGE_SIZE - 1
        url = f"{BASE_URL}/{API_KEY}/json/{service_id}/{start}/{end}/"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        body = payload.get(service_id)
        if body is None:
            raise RuntimeError(f"{service_id} 응답에 예상 키가 없습니다: {payload}")

        result_code = body.get("RESULT", {}).get("CODE")
        if result_code == "INFO-200":  # 해당 조건에 자료가 없음
            break
        if result_code and result_code != "INFO-000":
            raise RuntimeError(f"{service_id} API 오류: {body['RESULT']}")

        page_rows = body.get("row", [])
        rows.extend(page_rows)

        total = body.get("list_total_count", len(rows))
        if end >= total or not page_rows:
            break
        start = end + 1
        time.sleep(0.2)  # API 과호출 방지

    return rows


def save_raw(service_name: str, rows: list[dict]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / f"{service_name}.json"
    out_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return out_path


def load_to_duckdb(service_name: str, rows: list[dict]) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    con = duckdb.connect(str(DB_PATH))
    con.execute(f"CREATE OR REPLACE TABLE raw_{service_name} AS SELECT * FROM df")
    con.close()


def main() -> None:
    for name, service_id in SERVICES.items():
        print(f"[fetch] {name} ({service_id}) 수집 중...")
        rows = fetch_service(service_id)
        print(f"[fetch] {name}: {len(rows)}건 수집")
        save_raw(name, rows)
        load_to_duckdb(name, rows)
        print(f"[load] raw_{name} 테이블 적재 완료")


if __name__ == "__main__":
    main()
