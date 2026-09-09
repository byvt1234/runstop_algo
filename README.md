# RunStop 알고리즘

RunStop의 사용자 맞춤형 러닝·보행 경로 추천 알고리즘 소스 저장소입니다.
NetworkX 기반 가중 다익스트라 탐색으로 후보 경로를 만들고, 거리·경사·안전·자연·노면·보행 흐름 등의 조건을 점수화해 추천 순위를 계산합니다.

> 이 Public 저장소에는 소스 코드만 포함됩니다. GraphML, DEM, 시설 CSV, 공원·하천 GeoJSON 등 실제 데이터셋은 포함하지 않습니다.

## 주요 구조

```text
runstop_algo/
├── algo/
│   ├── pipeline.py              # 전체 추천 파이프라인
│   ├── draw_map.py              # 추천 경로 HTML 지도 생성
│   ├── config.py                # 공통 튜닝 상수
│   ├── routing/                 # 최단경로·경유지·후보 경로 생성
│   ├── features/                # 경사·시설·자연·노면 분석
│   ├── scoring/                 # 엣지 비용·필수조건·후보 점수
│   └── utils/                   # 좌표 및 그래프 유틸리티
├── datasets/
│   └── 배포/query_elevation.py  # DEM 조회 함수
├── tests/                       # 가중치 알고리즘 단위 테스트
├── API_SPEC.md
├── Dockerfile
└── requirements.txt
```

## 클론 및 설치

```bash
git clone https://github.com/byvt1234/runstop_algo.git
cd runstop_algo
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 데이터셋 배치

전체 알고리즘을 실행하려면 별도로 확보한 데이터를 다음 위치에 배치합니다.

```text
algo/data/
└── 서울_보행네트워크.graphml

datasets/
├── 배포/
│   ├── 서울_DEM_10m.npy
│   ├── 서울_DEM_10m_meta.json
│   └── 서울_시설데이터_통합.csv
└── osm/out/
    ├── 서울_공원.geojson
    └── 서울_하천_polygon.geojson
```

데이터 경로는 `RUNSTOP_DATA_DIR`, GraphML 경로는 `RUNSTOP_GRAPHML` 환경변수로 변경할 수 있습니다. 위 데이터 확장자는 `.gitignore`에 등록되어 있어 실수로 Public 저장소에 커밋되지 않습니다.

## 실행

알고리즘 파이프라인:

```powershell
python -m algo.pipeline
```

ONE_WAY 지도 생성:

```powershell
python -m algo.draw_map ONE_WAY 3
```

3km LOOP 지도 생성:

```powershell
python -m algo.draw_map LOOP 3
```

생성된 지도는 기본적으로 `algo/routes_map.html`에 저장되며 Git 추적에서 제외됩니다.

## 테스트

```powershell
python -m unittest discover -s tests -v
```

현재 테스트는 사용자 선호도에 따른 경로 변경, 계단 제외 조건, 대체 경로 선택을 검증합니다.

## API 형식

프론트엔드와 주고받는 요청·응답 필드는 [API_SPEC.md](API_SPEC.md)를 참고하세요.
