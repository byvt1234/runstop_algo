"""사용자 선호도와 원시 도로 지표를 가중치 계산용 범위로 정규화한다."""


from algo import config


# [가중치 설계 추가] 기존 API 키와 새로 권장하는 의미 중심 키를 함께 지원한다.
_WEIGHT_ALIASES = {
    "safety": ("safety", "night"),
    "nature": ("nature", "park"),
    "distance": ("distance",),
    "elevation": ("elevation",),
    "surface": ("surface",),
    "flow": ("flow",),
    "overlap": ("overlap",),
}


def clamp(value, minimum=0.0, maximum=1.0):
    """값을 minimum~maximum 범위로 제한한다."""
    return max(minimum, min(maximum, value))


def normalize_preference_weight(weights, name, default=None):
    """사용자 선호도 0~5를 엣지 비용에서 사용할 0~1로 변환한다."""
    # [가중치 설계 추가] 값 누락 시 기존 서비스와 비슷한 중간 선호도를 적용한다.
    if default is None:
        default = config.PREFERENCE_LEVEL_DEFAULT
    source = weights or {}
    raw_value = default
    for key in _WEIGHT_ALIASES.get(name, (name,)):
        if key in source:
            raw_value = source[key]
            break

    try:
        numeric_value = float(raw_value)
    except (TypeError, ValueError):
        numeric_value = default

    return clamp(
        (numeric_value - config.PREFERENCE_LEVEL_MIN)
        / (config.PREFERENCE_LEVEL_MAX - config.PREFERENCE_LEVEL_MIN)
    )


def increasing_penalty(value, good, bad):
    """작을수록 좋은 지표를 good=0, bad=1인 벌점으로 변환한다."""
    # [가중치 설계 추가] 경사도처럼 낮을수록 좋은 연속형 값에 사용한다.
    if value is None:
        return 0.0
    if bad <= good:
        raise ValueError("bad는 good보다 커야 합니다")
    return clamp((float(value) - good) / (bad - good))
