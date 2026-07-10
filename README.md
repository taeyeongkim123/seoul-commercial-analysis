# 서울시 상권분석 프로젝트

서울 열린데이터광장의 상권분석 공공데이터를 수집 → 정제 → 분석하여, 업종별/지역별 상권 현황과 쇠퇴 위험도를 시각화하는 데이터 엔지니어링 프로젝트입니다.

## 아키텍처

```
데이터 수집 (Python + Seoul Open API)
        │
        ▼
   raw layer (DuckDB)
        │
        ▼
   dbt 변환 (staging → marts)
        │
        ▼
 Streamlit 대시보드 (지도 시각화)
```

- **수집**: `scripts/fetch_seoul_data.py` — 서울 열린데이터광장 API 호출, raw 데이터를 DuckDB에 적재
- **저장**: DuckDB (`data/seoul_commercial.duckdb`, 서버 불필요)
- **변환**: dbt-duckdb (`dbt/` — staging/marts 레이어 분리)
- **시각화**: Streamlit + pydeck (`dashboard/app.py`)
- **자동화**: GitHub Actions로 주기적 데이터 갱신 (`.github/workflows/ingest.yml`)

## 데이터 출처

[서울 열린데이터광장](https://data.seoul.go.kr) — 우리마을가게 상권분석서비스
- 상권별 추정매출 (`VwsmTrdarSelngQq`)
- 상권별 추정 유동인구 (`VwsmTrdarFlpopQq`)
- 상권변화지표 (`VwsmTrdarChgIx`)
- 상권-점포 정보 (`VwsmTrdarStorQq`)

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

### 4. dbt 변환

```bash
cd dbt
dbt run
dbt test
```

### 5. 대시보드 실행

```bash
streamlit run dashboard/app.py
```

## CI/CD

`.github/workflows/ingest.yml`이 매주 월요일 자동으로 데이터를 수집하고 dbt를 실행합니다.
GitHub 저장소 Settings → Secrets and variables → Actions에 `SEOUL_API_KEY`를 등록해야 합니다.

## 프로젝트 구조

```
seoul-commercial-analysis/
├── scripts/           # 데이터 수집 스크립트
├── dbt/                # dbt 프로젝트 (staging/marts 모델)
├── dashboard/          # Streamlit 대시보드
├── data/
│   ├── raw/            # 원본 API 응답 캐시
│   └── processed/      # DuckDB 파일
├── tests/              # 수집/변환 로직 테스트
└── .github/workflows/  # 정기 수집 자동화
```

## 로드맵

- [x] 프로젝트 스켈레톤 및 수집 파이프라인
- [ ] dbt 변환 (매출 트렌드, 업종별 경쟁도 마트)
- [ ] Streamlit 대시보드 (지도 기반 상권 시각화)
- [ ] 데이터 품질 검증 (dbt tests)
- [ ] 상권 쇠퇴 위험도 예측 모델 (scikit-learn)
