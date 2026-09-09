"""전역 튜닝 상수. 다른 algo 모듈을 import 하지 않는 잎(leaf) 모듈.

각 모듈은 `from algo import config` 후 `config.NAME` 으로 참조한다.
함수 기본값에 직접 쓰지 말 것(=import 시점에 값이 고정됨). 파라미터는 `None` 으로
두고 함수 안에서 `config.NAME` 을 읽는다 — 그래야 테스트/추후 env 로 덮어쓸 수 있다.
"""

import os 

# ── 라우팅: 지나온 엣지 벌점 배수 ──────────────────
LOOP_PENALTY_FACTOR = 5.0     # loop 복귀 경로
P2P_PENALTY_FACTOR  = 2.0     # point_to_point 중간 구간
VIA_PENALTY_FACTOR  = 3.0     # 경유지 체인(_route_chain)

# ── 라우팅: 목표거리 맞추기 반복 ──────────────────
DIST_FIT_MAX_ITER = 6         # scale 보정 최대 반복
DIST_FIT_TOL      = 0.05      # 거리오차 이내면 조기 종료 (5%)

# ── 후보 풀 필터 ─────────────────────────────────
DEDUP_SIMILARITY  = 0.6       # 도로 공유율 초과 시 '같은 코스' 취급
CAND_DIST_TOL_PCT = 10.0      # 후보 거리오차 하드컷 (%)
CAND_MAX_OVERLAP  = 0.35      # 후보 겹침 하드컷

# ── features: 코스 주변 분석 ──────────────────────
BUFFER_M       = 100          # 시설/녹지 인접 판정 버퍼 폭 (m) — facilities·nature 공용
SLOPE_SAMPLE_M = 30.0         # 경사 프로파일 폴리라인 샘플 간격 (m)
MIN_SEGMENT_M  = 1.0          # 이보다 짧은 구간은 경사 계산에서 제외 (0 나눗셈 방지)

# [가중치 설계 추가] 사용자 선호도 입력 범위와 엣지 비용 튜닝값.
PREFERENCE_LEVEL_MIN     = 0.0
PREFERENCE_LEVEL_MAX     = 5.0
PREFERENCE_LEVEL_DEFAULT = 3.0

EDGE_COST_SCALE_ELEVATION = 1.2
EDGE_COST_SCALE_SAFETY    = 0.8
EDGE_COST_SCALE_NATURE    = 0.6
EDGE_COST_SCALE_SURFACE   = 0.8
EDGE_COST_SCALE_FLOW      = 0.5
EDGE_SLOPE_GOOD_PCT       = 2.0
EDGE_SLOPE_BAD_PCT        = 10.0
