"""
경유지 생성 — course.py 가 "어디를 경유점으로 삼을지" 정할 때 쓴다.

circle_waypoints : 순환·왕복용. 출발점 중심 원 위의 점.
ellipse_waypoints: 편도용. 출발·도착을 초점으로, 두 초점까지 거리의 합이
                   target_sum_m 인 타원 위의 점. start==end 면 원과 같아진다.
기하 계산은 전부 미터 좌표(EPSG:5179)에서 한다.
"""

import math
from algo.utils.geo import point_at_bearing, to_5179, to_4326


def circle_waypoints(lat, lon, radius_m, n=1, start_bearing=0.0):
    """출발점 중심 반지름 radius_m 원 위에 등간격 n개."""
    return [
        point_at_bearing(lat, lon, (start_bearing + 360.0 * i / n) % 360, radius_m)
        for i in range(n)
    ]


def ellipse_waypoints(start, end, target_sum_m, n=8):
    """dist(start,P) + dist(P,end) ≈ target_sum_m 인 타원 위 n개.
    start == end 면 반지름 target_sum_m/2 인 원과 같다."""
    x1, y1 = to_5179.transform(start[1], start[0])
    x2, y2 = to_5179.transform(end[1], end[0])

    c = math.hypot(x2 - x1, y2 - y1) / 2      # 초점 간 거리의 절반
    a = target_sum_m / 2                      # 장반경 (|PF1|+|PF2| = 2a)
    if a <= c:
        raise ValueError(
            f"목표거리 {target_sum_m:.0f}m 가 직선거리 {2*c:.0f}m 보다 짧아 경로를 만들 수 없습니다"
        )
    b = math.sqrt(a * a - c * c)              # 단반경 (c=0이면 b=a -> 원)

    mx, my = (x1 + x2) / 2, (y1 + y2) / 2     # 중심 = 두 초점의 중점
    theta = math.atan2(y2 - y1, x2 - x1)      # start->end 축의 회전각

    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        ex, ey = a * math.cos(t), b * math.sin(t)              # 축 정렬 타원 위 점
        wx = mx + ex * math.cos(theta) - ey * math.sin(theta)  # theta 회전 + 중심 이동
        wy = my + ex * math.sin(theta) + ey * math.cos(theta)
        lon, lat = to_4326.transform(wx, wy)
        pts.append((lat, lon))
    return pts


if __name__ == "__main__":
    from algo.utils.geo import haversine_m

    s = (37.4979, 127.0276)   # 강남역
    e = (37.5045, 127.0350)   # 북동쪽, 직선거리 약 982m

    print("1) start==end -> 전부 중심에서 500m")
    for w in ellipse_waypoints(s, s, target_sum_m=1000, n=6):
        print("  ", round(haversine_m(s, w), 1), "m")

    print("2) start!=end -> 합이 목표(3000)")
    for w in ellipse_waypoints(s, e, target_sum_m=3000, n=6):
        print("  ", round(haversine_m(s, w) + haversine_m(w, e)), "m")

    print("3) 목표 < 직선거리 -> ValueError")
    try:
        ellipse_waypoints(s, e, target_sum_m=500, n=4)
    except ValueError as ex:
        print("  ", ex)
