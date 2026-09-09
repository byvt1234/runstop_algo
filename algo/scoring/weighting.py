"""
후보 코스의 원시 feature -> 0~100 소점수(sub_scores) -> 사용자 가중치로 conditionScore.
필수조건(requirements) 미충족은 failedConditions 로 표시하되 후보는 버리지 않는다.

입력 candidate 는 course + elevation(slope) + scoring(facilities) + nature + surface 가
붙은 상태여야 한다 (pipeline.recommend 가 순서대로 붙임).

정규화는 절대 기준 곡선 (후보가 3개뿐이라 min-max 는 불안정). 임계값은 아래 상수.
"""

# ── 0점 ↔ 100점 기준 (튜닝 포인트) ─────────────────────────────
DIST_ERR_ZERO_PCT   = 10.0    # 거리 오차 10% -> 0점, 0% -> 100점
GAIN_PER_KM_ZERO    = 30.0    # 1km당 오르막 30m -> 0점, 0m -> 100점
ELEVATION_NEUTRAL   = 50.0    # DEM 없을 때 경사 소점수 (중립)
TOILET_FULL         = 2       # 화장실 이 개수 이상이면 개수점 만점
STORE_FULL          = 3
NEAR_OK_M           = 100.0   # 시설 최근접 이 거리까지는 감점 없음
NEAR_PENALTY_SPAN_M   = 100.0  # 이 거리마다 아래 점수씩 추가 감점
NEAR_PENALTY_PER_SPAN = 20.0   # 스팬당 감점
NEAR_PENALTY_MAX      = 40.0   # 근접 감점 총상한
PARK_RATIO_FULL     = 0.15    # 녹지 인접률 15% -> 100점
WATER_RATIO_FULL    = 0.15    # 하천 인접률 15% -> 100점
STREETLIGHT_PER_KM_FULL = 120.0  # (가로등+보안등+보행등)/km — 서울 도심은 대부분 포화
CCTV_PER_KM_FULL    = 15.0
WALKABLE_FULL       = 0.60    # 보행자친화 길이비율 60% -> 100점 기여
BIGROAD_ZERO        = 0.30    # 큰길 비율 30% -> 큰길 감점 최대
BIGROAD_PENALTY_MAX = 40.0    # 큰길 감점 상한 (= 스케일 계수)
STAIRS_PENALTY      = 15.0    # 계단 1개당 노면점 -15
SIGNAL_PER_KM_ZERO  = 4.0     # 신호등 4개/km -> 0점, 0 -> 100점
OVERLAP_ZERO        = 0.30    # 겹침 0.30 -> 0점, 0 -> 100점
PACE_MIN_PER_KM     = 6.0     # 예상 소요시간용
DEFAULT_WEIGHT      = 3       # 사용자 가중치 미지정 시 기본

# ── 필수조건(requirements) 하드 판정 ──────────────────────────
DIST_TOLERANCE_PCT  = 10.0    # 목표 거리 ±이 값(%)
REQ_MIN_COUNT       = 1       # 필수 시설(화장실/편의점) 최소 개수
REQ_PARK_RATIO_MIN  = 0.05    # 필수 "녹지 인접" 최소 인접률


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def _score_lower_is_better(value, good, bad):
    """value=good -> 100, value=bad -> 0 (작을수록 좋음). 선형 + 클램프."""
    if bad == good:
        return 100.0
    return _clamp(100.0 * (bad - value) / (bad - good))


def _score_higher_is_better(value, zero, full):
    """value<=zero -> 0, value>=full -> 100 (클수록 좋음)."""
    if full == zero:
        return 100.0
    return _clamp(100.0 * (value - zero) / (full - zero))


def _facility_count_score(count, full, nearest_m):
    if not count:
        return 0.0
    base = _clamp(100.0 * count / full)
    if nearest_m is not None and nearest_m > NEAR_OK_M:
        base -= _clamp((nearest_m - NEAR_OK_M) / NEAR_PENALTY_SPAN_M * NEAR_PENALTY_PER_SPAN,
                       0.0, NEAR_PENALTY_MAX)
    return _clamp(base)


def compute_sub_scores(cand):
    f = cand.get("facilities") or {}
    slope = cand.get("slope") or {}
    nat = cand.get("nature") or {}
    surf = cand.get("surface") or {}
    km = cand["actual_distance_m"] / 1000 or 1e-9

    subs = {}

    # 거리
    subs["distance"] = round(_score_lower_is_better(cand["distance_error_pct"], 0.0, DIST_ERR_ZERO_PCT), 1)

    # 경사 (DEM 없으면 중립 50)
    gain = slope.get("elevation_gain_m")
    subs["elevation"] = ELEVATION_NEUTRAL if gain is None else round(_score_lower_is_better(gain / km, 0.0, GAIN_PER_KM_ZERO), 1)

    # 화장실 / 편의점 (개수 + 근접)
    subs["toilet"] = round(_facility_count_score(f.get("toilet_count", 0), TOILET_FULL, f.get("toilet_nearest_m")), 1)
    subs["store"] = round(_facility_count_score(f.get("store_count", 0), STORE_FULL, f.get("store_nearest_m")), 1)

    # 녹지 / 하천 인접률 (OSM 폴리곤 없으면 None)
    pr = nat.get("park_ratio")
    subs["park"] = None if pr is None else round(_score_higher_is_better(pr, 0.0, PARK_RATIO_FULL), 1)
    wr = nat.get("water_ratio")
    subs["water"] = None if wr is None else round(_score_higher_is_better(wr, 0.0, WATER_RATIO_FULL), 1)

    # 야간: 가로등+보안등+보행등 합산 / CCTV 별도
    light = (f.get("light_count", 0) + f.get("security_count", 0) + f.get("walklight_count", 0))
    subs["streetlight"] = round(_score_higher_is_better(light / km, 0.0, STREETLIGHT_PER_KM_FULL), 1)
    subs["cctv"] = round(_score_higher_is_better(f.get("cctv_count", 0) / km, 0.0, CCTV_PER_KM_FULL), 1)

    # 노면 (OSM 속성 없으면 None): 보행자친화 비율이 기본점, 큰길·계단은 감점
    wratio = surf.get("walkable_ratio")
    if wratio is None:
        subs["surface"] = None
    else:
        base = _score_higher_is_better(wratio, 0.0, WALKABLE_FULL)
        bigroad_penalty = _clamp(surf.get("bigroad_ratio", 0.0) / BIGROAD_ZERO * BIGROAD_PENALTY_MAX,
                                 0.0, BIGROAD_PENALTY_MAX)
        stairs_penalty = STAIRS_PENALTY * surf.get("stairs_count", 0)
        subs["surface"] = round(_clamp(base - bigroad_penalty - stairs_penalty), 1)

    # 흐름: 신호등 적을수록 좋음 (None 이면 제외)
    spk = surf.get("signal_per_km")
    subs["flow"] = None if spk is None else round(_score_lower_is_better(spk, 0.0, SIGNAL_PER_KM_ZERO), 1)

    # 겹침: 왕복(out_and_back)은 의미 없어 제외
    if cand.get("mode") == "out_and_back":
        subs["overlap"] = None
    else:
        subs["overlap"] = round(_score_lower_is_better(cand.get("overlap_ratio", 0.0), 0.0, OVERLAP_ZERO), 1)

    return subs


# 소점수 이름 -> 사용자 weights dict 에서 읽을 키
_WEIGHT_KEY = {
    "distance": "distance", "elevation": "elevation",
    "toilet": "toilet", "store": "store",
    "park": "park", "water": "park",            # 하천도 자연 선호(park) 가중치 공유
    "streetlight": "night", "cctv": "night",    # 야간 가중치 공유
    "surface": "surface", "flow": "flow", "overlap": "overlap",
}
_DEFAULT_W = {"distance": 3, "elevation": 3, "toilet": 3, "store": 3,
              "park": 3, "night": 3, "surface": 2, "flow": 2, "overlap": 2}


def compute_condition_score(subs, weights=None):
    w = {**_DEFAULT_W, **(weights or {})}
    num = den = 0.0
    for name, score in subs.items():
        if score is None:
            continue
        wt = w.get(_WEIGHT_KEY.get(name, name), DEFAULT_WEIGHT)
        num += score * wt
        den += wt
    return round(num / den, 1) if den else 0.0


def check_requirements(cand, requirements=None):
    """반환: (failed_conditions[], exact_match)."""
    req = requirements or {}
    f = cand.get("facilities") or {}
    surf = cand.get("surface") or {}
    nat = cand.get("nature") or {}
    failed = []

    if cand["distance_error_pct"] > DIST_TOLERANCE_PCT:
        failed.append(f"목표 거리 ±{DIST_TOLERANCE_PCT:.0f}%")
    if req.get("toilet") and f.get("toilet_count", 0) < REQ_MIN_COUNT:
        failed.append("화장실 최소 1곳")
    if req.get("store") and f.get("store_count", 0) < REQ_MIN_COUNT:
        failed.append("편의점 최소 1곳")
    if req.get("no_stairs") and surf.get("stairs_count", 0) > 0:
        failed.append("계단 없음")
    if req.get("park") and (nat.get("park_ratio") or 0) < REQ_PARK_RATIO_MIN:
        failed.append("녹지 인접")

    return failed, len(failed) == 0


def score_candidate(cand, weights=None, requirements=None):
    subs = compute_sub_scores(cand)
    failed, exact = check_requirements(cand, requirements)
    cand["sub_scores"] = subs
    cand["condition_score"] = compute_condition_score(subs, weights)
    cand["failed_conditions"] = failed
    cand["exact_match"] = exact
    cand["estimated_minutes"] = round(cand["actual_distance_m"] / 1000 * PACE_MIN_PER_KM)
    return cand
