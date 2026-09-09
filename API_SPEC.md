# RunStop 코스 추천 API — 요청/응답 형식

`POST /api/v1/routes/recommend`
헤더: `Authorization: Bearer {accessToken}` · `Content-Type: application/json`

내부 `pipeline.recommend()` 출력을 프론트용 camelCase 로 정리한 것.

---

## 1. 요청 (Request)

```json
{
  "start":  { "latitude": 37.4979, "longitude": 127.0276 },
  "end":    { "latitude": 37.5045, "longitude": 127.0400 },
  "vias":   [ { "latitude": 37.5045, "longitude": 127.0490 } ],

  "routeType": "LOOP",
  "targetDistanceKm": 3.0,
  "distanceTolerance": 10,

  "weights": {
    "distance": 5, "elevation": 4, "toilet": 5,
    "store": 2, "park": 3, "night": 5
  },
  "requirements": {
    "toilet": true, "store": false, "park": false, "noStairs": true
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `start.latitude` / `start.longitude` | number | Y | 출발지 (WGS84) |
| `end` | object | **ONE_WAY만 Y** | 도착지. LOOP/ROUND_TRIP 은 무시 |
| `vias` | array | N | 반드시 지날 경유지, **입력 순서대로**. 없으면 생략 |
| `routeType` | string | Y | `LOOP`(순환) · `ONE_WAY`(편도) · `ROUND_TRIP`(왕복) |
| `targetDistanceKm` | number | Y | 목표 거리. 1 ~ 30 |
| `distanceTolerance` | int | N | 허용 오차 %. 기본 10 |
| `weights.*` | int | N | 각 1~5. 생략 시 3. `night` = 가로등+CCTV 공통 가중치 |
| `requirements.*` | bool | N | 필수조건. 못 맞춰도 후보는 반환되고 `failedConditions` 에 표시 |

---

## 2. 성공 응답 (200)

```json
{
  "success": true,
  "message": "추천 코스 조회 완료",
  "data": {
    "exactMatch": true,
    "routes": [
      {
        "routeId": "loop-0",
        "conditionScore": 70.7,

        "distanceKm": 3.13,
        "distanceErrorPct": 4.4,
        "estimatedMinutes": 19,
        "overlapRatio": 0.0,

        "exactMatch": true,
        "failedConditions": [],

        "elevation": { "gainM": 34, "avgSlopePct": 3.3, "maxSlopePct": 8.0 },

        "facilities": {
          "toilet": { "count": 12, "perKm": 3.8, "nearestM": 29 },
          "store":  { "count": 28, "perKm": 8.9, "nearestM": 12 },
          "park":   { "count": 1,  "perKm": 0.3, "nearestM": 210 },
          "cctv":   { "count": 88, "perKm": 28,  "nearestM": 3 }
        },

        "nature":  { "parkRatio": 0.03, "waterRatio": 0.0 },

        "surface": {
          "walkableRatio": 0.61, "bigroadRatio": 0.45,
          "stairsCount": 0, "signalPerKm": 0.3, "crossingPerKm": 3.2
        },

        "subScores": {
          "distance": 56, "elevation": 63, "toilet": 100, "store": 100,
          "park": 3, "water": 0, "streetlight": 88, "cctv": 100,
          "surface": 60, "flow": 92, "overlap": 100
        },

        "path": [ [37.4979, 127.0276], [37.4981, 127.0279], "..." ]
      }
    ]
  }
}
```

| 필드 | 설명 |
|---|---|
| `data.exactMatch` | 후보 중 **하나라도** 모든 requirements 를 충족하면 true |
| `routes` | `conditionScore` 내림차순, 최대 3개 |
| `routeId` | `{routeType}-{index}` (임시). DB 저장 시 숫자 ID 로 |
| `conditionScore` | 0~100. `subScores` 를 `weights` 로 가중평균 |
| `distanceErrorPct` | 목표 대비 오차 % (프론트에서 "목표보다 4% 김" 표시용) |
| `overlapRatio` | 겹친 도로 비율. 0 = 완전히 다른 길로 복귀. `ROUND_TRIP` 은 항상 ~0.5(정상) |
| `failedConditions` | 못 맞춘 필수조건 문자열 배열 (`["화장실 최소 1곳"]`) |
| `elevation.gainM` | 누적 상승고도 (m). DEM 범위 밖이면 `null` |
| `facilities.<종류>` | 코스 100m 버퍼 내 개수 / km당 / 최근접거리(m). 없으면 `nearestM: null` |
| `nature.parkRatio` / `waterRatio` | 코스 100m 띠 면적 중 공원 / 하천 겹침 비율 (0~1). 폴리곤 데이터 없으면 `null` |
| `surface.walkableRatio` | 보행자친화(footway·path·주택가) 길이 비율 |
| `surface.bigroadRatio` | 큰길(대로·간선) 길이 비율. **낮을수록 좋음** |
| `surface.stairsCount` | 계단 구간 수 |
| `surface.signalPerKm` | km당 신호등 수 |
| `subScores.*` | 각 항목 0~100 정규화 점수. `null` = 데이터 없어 평균에서 제외 |
| `path` | `[[위도, 경도], ...]` 폴리라인. 지도에 그대로 그림 |

---

## 3. 조건 만족 코스 없음 (200)

에러 아님. 가장 가까운 대안을 반환.

```json
{
  "success": true,
  "message": "모든 조건을 만족하는 코스가 없어 대안을 제공합니다",
  "data": {
    "exactMatch": false,
    "routes": [ { "...": "위와 동일", "failedConditions": ["화장실 최소 1곳"] } ]
  }
}
```

## 4. 후보 자체가 없음 (404)

```json
{ "success": false, "code": "NO_CANDIDATE_ROUTE",
  "message": "조건에 맞는 코스를 만들지 못했습니다. 목표 거리를 조정해 보세요." }
```

## 5. 요청 오류 (400)

```json
{ "success": false, "code": "INVALID_DISTANCE",
  "message": "targetDistanceKm 는 1 ~ 30 사이여야 합니다" }
```

| code | 상황 |
|---|---|
| `INVALID_REQUEST` | 필수 필드 누락 / 타입 오류 |
| `INVALID_COORDINATE` | 좌표가 서울 범위 밖 |
| `INVALID_DISTANCE` | `targetDistanceKm` 1~30 벗어남, 또는 ONE_WAY 에서 목표 < 직선거리 |
| `INVALID_WEIGHT` | `weights` 값이 1~5 밖 |
| `NO_CANDIDATE_ROUTE` | 8방향 다 시도했으나 후보 0개 |
| `INTERNAL_ERROR` | 서버 오류 |

---

## 6. 코스 상세 (선택)

`GET /api/v1/routes/{routeId}` — 목록의 route 객체 + 주변 시설 좌표 목록(마커용).

```json
{
  "success": true,
  "data": {
    "...": "recommend 의 route 객체와 동일",
    "facilityPoints": {
      "toilet": [ { "name": "...", "latitude": 37.5, "longitude": 127.0, "distanceM": 29 } ],
      "store":  [ "..." ]
    }
  }
}
```
