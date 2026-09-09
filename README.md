# RunStop 배포 패키지 (알고리즘 + 데이터셋)

`알고리즘/code/` 의 코스 추천 알고리즘을 **동봉 데이터셋과 함께** 그대로 실행·배포할 수
있게 묶은 폴더. 원본 저장소(`runstop/data/...`)에 대한 절대경로 의존을 없애고, 데이터
위치를 환경변수 하나(`RUNSTOP_DATA_DIR`)로 바꿀 수 있게 했다.

`pipeline.recommend()` 를 감싼 FastAPI 서버(`POST /api/v1/routes/recommend`)가 들어있다.
요청/응답 형식은 [`API_SPEC.md`](API_SPEC.md) 참고.

- GitHub: `https://github.com/Jeabin90/ruustopal`
- 대용량 파일(`*.graphml`, `*.npy`)은 **Git LFS** 로 관리 → 클론 후 `git lfs pull` 필요

---

## 폴더 구조

```
deploy/
├── README.md              # 이 파일
├── API_SPEC.md            # 요청/응답 형식 (원본 API_형식.md)
├── requirements.txt       # 런타임 + FastAPI
├── Dockerfile             # 알고리즘·데이터셋·서버 한 이미지
├── .dockerignore
├── .gitignore             # __pycache__, .venv, *.log, algo/data/*.pkl
├── .gitattributes         # *.graphml, *.npy → Git LFS
├── run.sh                 # 로컬: venv 생성 → 의존성 설치 → uvicorn
│
├── app/                   # ── 배포 래퍼 (신규) ──
│   ├── config.py          #   경로·파라미터 (전부 env 로 덮어쓰기 가능)
│   ├── schema.py          #   요청 camelCase 파싱 + 검증 → 에러코드
│   ├── mapper.py          #   recommend() 출력 → 응답 DTO(camelCase)
│   └── server.py          #   FastAPI 엔드포인트 (POST /recommend, GET /health)
│
├── algo/                  # ── 알고리즘 (기능별 서브패키지) ──
│   ├── pipeline.py        #   최상위 오케스트레이터 (요청 1건 → 추천 TOP-K)
│   ├── _datapaths.py      #   ★ 데이터셋 위치 해석 (features/* 만 참조)
│   ├── utils/             #   geo(좌표) · graph(도로망 로드·스냅)
│   ├── routing/           #   shortest_path · waypoints · course · candidates
│   ├── features/          #   elevation · facilities · nature · surface (후보에 속성 부착)
│   ├── scoring/           #   weighting (소점수 → conditionScore)
│   └── data/
│       ├── 서울_보행네트워크.graphml   (191MB, 실제 서울 보행망 · LFS)
│       └── 서울_보행네트워크.pkl       (96MB, graphml 로드 캐시 · git 제외, 첫 실행 시 자동 생성)
│
└── datasets/             # ── 알고리즘이 소비하는 공공데이터 (runstop/data 에서 복사) ──
    ├── 배포/
    │   ├── query_elevation.py               # DEM 조회 함수 (elevation.py 가 import)
    │   ├── 서울_DEM_10m.npy (+ _meta.json)   # 10m 수치표고 → 경사 (npy 43MB · LFS)
    │   └── 서울_시설데이터_통합.csv          # 화장실·편의점·CCTV·가로등... (유형/명칭/위도/경도) 21MB
    └── osm/out/
        ├── 서울_공원.geojson              # nature.py 녹지 인접률 (4.2MB)
        └── 서울_하천_polygon.geojson      # nature.py 하천 인접률 (756KB)
```

동봉 데이터 합계 약 **355MB** (graphml 191 + pkl 96 + npy 43 + csv 21 + geojson 5).

---

## 원본(`알고리즘/code/`) 대비 변경점

| 파일 | 변경 |
|---|---|
| `algo/_datapaths.py` | **신규.** `RUNSTOP_DATA_DIR`(기본 `deploy/datasets`) 기준으로 DEM·시설·OSM 경로 해석 |
| `algo/features/elevation.py` | `DEM_DIR = Path("/Users/.../data/배포")` → `from algo._datapaths import DEM_DIR` |
| `algo/features/facilities.py` | (구 `scoring.py`) `FACIL_CSV = "/Users/.../서울_시설데이터_통합.csv"` → `from algo._datapaths import FACIL_CSV` |
| `algo/features/nature.py` | `OUT = Path(__file__)...` → `from algo._datapaths import OSM_OUT as OUT` |
| `algo/pipeline.py` | ① import 시 스모크테스트 강제하던 `__name__ = "__main__"` 줄 제거<br>② `__main__` 데모 좌표 오타 수정 `(36.49, 126.02)` → `(37.49, 127.02)` (서울 밖이라 항상 크래시하던 것) |
| `algo/routing/course.py` | `generate_course` / `generate_course_via` 에서 경로 실패 시 `best is None` 언패킹(`TypeError`) 대신 `ValueError` → `generate_candidates` 가 잡아 해당 방향만 건너뜀. 전부 실패하면 서버가 `NO_CANDIDATE_ROUTE`(404) 응답 |
| **패키지화** | 평면 모듈 13개 → `algo/` 를 정식 패키지로. `utils · routing · features · scoring` 서브패키지 + 절대임포트(`from algo.routing.course import ...`). 실행은 `python -m algo.pipeline`. `routing.py`→`routing/shortest_path.py`, `scoring.py`→`features/facilities.py` 로 개명. 미사용 `ranker.py` 제거 |

알고리즘 로직·점수 계산은 그대로다.

---

## 클론

```bash
git clone https://github.com/Jeabin90/ruustopal.git
cd ruustopal
git lfs pull            # graphml·npy 실제 내용 내려받기 (안 하면 포인터 파일만 있음)
```

`git lfs pull` 을 빼먹으면 서버가 격자 그래프로 폴백하거나 npy 로드에서 깨진다.

---

## 실행

### 1) 로컬 (스크립트)

```bash
cd deploy
./run.sh                       # .venv 생성 + 설치 + 8000 포트로 서버
```

### 2) 로컬 (수동)

```bash
cd deploy
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.server:app --host 0.0.0.0 --port 8000
```

### 3) Docker

```bash
cd deploy
docker build -t runstop-api .
docker run -p 8000:8000 runstop-api
```

첫 요청(또는 컨테이너 부팅) 시 graphml → pkl 캐시 로드에 **1~20초**. 이후 요청은 수백 ms.

### 알고리즘 단독 자체 테스트

```bash
cd deploy
RUNSTOP_DATA_DIR=$PWD/datasets python -m algo.pipeline
# LOOP / ONE_WAY / ROUND_TRIP / 경유지 4케이스 × TOP3 출력
```

---

## 확인

```bash
curl localhost:8000/health

curl -X POST localhost:8000/api/v1/routes/recommend \
  -H 'Content-Type: application/json' \
  -d '{
    "start": { "latitude": 37.4979, "longitude": 127.0276 },
    "routeType": "LOOP",
    "targetDistanceKm": 3.0,
    "weights": { "distance": 5, "elevation": 4, "toilet": 5, "night": 5 },
    "requirements": { "toilet": true, "noStairs": true }
  }'
```

`GET /health` → `{ "status": "ok", "graphSource": "서울_보행네트워크.graphml", "nodes": 164891, "dataDir": "..." }`

---

## 환경변수

| 변수 | 기본값 | 용도 |
|---|---|---|
| `RUNSTOP_DATA_DIR` | `deploy/datasets` | 데이터셋 루트. 볼륨 마운트로 교체 가능 (하위 레이아웃 `배포/`, `osm/out/` 유지) |
| `RUNSTOP_GRAPHML` | `deploy/algo/data/서울_보행네트워크.graphml` | 보행 네트워크. 없으면 격자 그래프로 폴백(테스트용) |
| `RUNSTOP_N_DIR` | `12` | 후보 탐색 방향 수. 낮추면 응답 빠름 / 다양성 ↓ |
| `RUNSTOP_TOP_K` | `3` | 응답 코스 개수 |

---

## 데이터셋 출처 / 갱신

원본은 `runstop/data/원본/` 의 공공데이터를 `runstop/data/정제/` 에서 정제한 것.
갱신 시 `runstop/data/배포/`, `runstop/data/osm/out/` 를 다시 만들고 이 폴더의
`datasets/` 로 복사한다. graphml 재생성은 원본 `알고리즘/code/build_graph.py`
(osmnx 필요, 1회성).

`*.graphml`·`*.npy` 는 `.gitattributes` 로 LFS 처리되므로 교체 후 `git add` → `commit`
하면 자동으로 LFS 오브젝트로 올라간다. GitHub 무료 LFS 한도는 저장 1GB / 월 대역폭 1GB
(현재 사용 약 235MB). `.pkl` 은 커밋하지 않는다(graphml 에서 자동 재생성).
