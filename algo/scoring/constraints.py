"""경로 탐색 전에 적용할 도로 구간 필수 조건."""

import ast


def parse_osm_tags(raw_value):
    """OSM의 단일 문자열 또는 문자열화된 목록을 문자열 집합으로 변환한다."""
    # [가중치 설계 추가] GraphML 로딩 후 남는 여러 표현 형식을 동일하게 처리한다.
    if raw_value is None:
        return set()
    if isinstance(raw_value, (list, tuple, set)):
        return {str(value) for value in raw_value}

    serialized_value = str(raw_value)
    if serialized_value.startswith("["):
        try:
            parsed_value = ast.literal_eval(serialized_value)
            if isinstance(parsed_value, (list, tuple, set)):
                return {str(value) for value in parsed_value}
        except (SyntaxError, ValueError):
            pass
    return {serialized_value}


def extract_slope_pct(edge_data):
    """OSMnx grade/grade_abs 값을 경사도 퍼센트로 반환한다."""
    # [가중치 설계 추가] OSMnx grade는 보통 비율이므로 100을 곱해 퍼센트로 바꾼다.
    raw_slope = edge_data.get("grade_abs", edge_data.get("grade"))
    if raw_slope is None:
        return None
    try:
        slope = abs(float(raw_slope))
    except (TypeError, ValueError):
        return None
    return slope * 100.0 if slope <= 1.0 else slope


def violates_edge_requirements(edge_data, requirements=None):
    """필수 조건을 위반하면 True를 반환한다."""
    # [가중치 설계 추가] 선호 가중치와 절대 금지 조건을 분리한다.
    required = requirements or {}
    highway_tags = parse_osm_tags(edge_data.get("highway"))

    if required.get("no_stairs") and "steps" in highway_tags:
        return True

    max_slope_pct = required.get(
        "max_slope_pct",
        required.get("max_slope", required.get("maxSlope")),
    )
    slope_pct = extract_slope_pct(edge_data)
    if max_slope_pct is not None and slope_pct is not None:
        try:
            if slope_pct > float(max_slope_pct):
                return True
        except (TypeError, ValueError):
            pass

    return False
