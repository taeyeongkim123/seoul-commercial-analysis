# 서울시 상권분석 프로젝트

서울 열린데이터광장의 상권분석 공공데이터를 수집 → 정제 → 분석하여, 업종별/지역별 상권 현황과 쇠퇴 위험도를 시각화하는 데이터 엔지니어링 프로젝트입니다.

## 아키텍처

```
데이터 수집 (Python + Seoul Open API)
        │
        ▼
   raw layer (DuckDB) ──▶ 상권 군집화 (K-means, scripts/cluster_districts.py)
        │                        │
        ▼                        ▼
   dbt 변환 (staging → marts, 군집 결과 포함)
        │
        ▼
 Streamlit 대시보드 (지도 + 트렌드 시각화)
```

- **수집**: `scripts/fetch_seoul_data.py` — 서울 열린데이터광장 API 호출, raw 데이터를 DuckDB에 적재
- **저장**: DuckDB (`data/seoul_commercial.duckdb`, 서버 불필요)
- **군집화**: `scripts/cluster_districts.py` — 매출·유동인구·점포구조 특성으로 상권 유형을 K-means 군집화 (raw 레이어만 참조, dbt보다 먼저 실행)
- **변환**: dbt-duckdb (`dbt/` — staging/marts 레이어 분리)
- **시각화**: Streamlit + pydeck + Altair (`dashboard/app.py`)
- **자동화**: GitHub Actions로 주기적 데이터 갱신 (`.github/workflows/ingest.yml`)

## 데이터 출처

[서울 열린데이터광장](https://data.seoul.go.kr) — 우리마을가게 상권분석서비스
- 상권별 추정매출 (`VwsmTrdarSelngQq`)
- 상권별 추정 유동인구 (`VwsmTrdarFlpopQq`)
- 상권변화지표 (`VwsmTrdarIxQq`)
- 상권-점포 정보 (`VwsmTrdarStorQq`)
- 상권영역 중심좌표 (`TbgisTrdarRelm`, TM좌표 → WGS84 변환 후 지도 시각화에 사용)

## 시작하기

### 1. 환경 설정

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. API 키 발급

1. [data.seoul.go.kr](https://data.seoul.go.kr) 회원가입 후 로그인
2. 상단 메뉴에서 "인증키 신청" → 활용 목적 등 간단히 작성하면 즉시 발급
3. `.env.example`을 `.env`로 복사 후 `SEOUL_API_KEY`에 발급받은 키 입력

```bash
cp .env.example .env
```

### 3. 데이터 수집

```bash
python scripts/fetch_seoul_data.py
```

### 4. 상권 군집화 (dbt보다 먼저 실행)

매출·유동인구·점포구조 특성으로 상권을 K-means 군집화해 `raw_district_clusters` 테이블을 만듭니다.
dbt의 `stg_district_clusters`/`mart_district_map`이 이 테이블을 참조하므로 **dbt run 이전에** 실행해야 합니다.

```bash
python scripts/cluster_districts.py
```

### 5. dbt 변환

```bash
cd dbt
dbt run
dbt test
```

### 6. 대시보드 실행

```bash
streamlit run dashboard/app.py
```

### 7. (선택) 예측 모델 학습

다음 분기 유동인구 감소 여부를 예측하는 RandomForest 모델을 시계열 홀드아웃으로 학습/평가합니다.

```bash
python scripts/train_district_risk_model.py
```

결과는 `models/report.md`에 저장됩니다 (모델 바이너리는 재현용 스크립트만 커밋하고 git에는 포함하지 않습니다).

## CI/CD

`.github/workflows/ingest.yml`이 매주 월요일 자동으로 데이터를 수집하고 dbt를 실행합니다.
GitHub 저장소 Settings → Secrets and variables → Actions에 `SEOUL_API_KEY`를 등록해야 합니다.

## 프로젝트 구조

```
seoul-commercial-analysis/
├── scripts/           # 데이터 수집 스크립트
├── dbt/                # dbt 프로젝트 (staging/marts 모델)
├── dashboard/          # Streamlit 대시보드
├── models/             # 예측 모델 학습 산출물 (report.md만 커밋)
├── data/
│   ├── raw/            # 원본 API 응답 캐시
│   └── processed/      # DuckDB 파일
├── tests/              # 수집/변환 로직 테스트
└── .github/workflows/  # 정기 수집 자동화
```

## 로드맵

- [x] 프로젝트 스켈레톤 및 수집 파이프라인
- [x] dbt 변환 (매출 트렌드 `mart_district_sales_trend`, 업종별 경쟁도 `mart_industry_competition`, 상권 위험도 `mart_district_risk`)
- [x] 데이터 품질 검증 (dbt tests 35개: not_null/unique/accepted_values)
- [x] 지도 기반 상권 시각화 (`mart_district_map` + pydeck, 자치구/위험도/군집 필터)
- [x] 상권 특성 기반 K-means 군집화 (`scripts/cluster_districts.py`, 실루엣 점수로 k 자동 선택 + 군집 자동 라벨링, 지도에 색상으로 표시)
- [x] 트렌드 대시보드 (분기별 매출·유동인구 추이, 자치구별 유동인구, 지역별 업종 랭킹)
- [x] 상권 유동인구 감소 예측 모델 (scikit-learn RandomForest, 시계열 홀드아웃 평가 — 결과와 한계는 `models/report.md` 참고)
- [ ] 예측 모델 성능 개선 (등락폭 회귀, 계절성/이벤트 캘린더 피처 등)
