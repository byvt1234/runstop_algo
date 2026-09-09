# RunStop 코스 추천 API — 알고리즘 + 데이터셋 동봉 이미지
FROM python:3.12-slim

# geopandas/shapely/pyproj 런타임 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgeos-c1v5 libproj25 libgdal34 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/runstop

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 알고리즘 코드 + 동봉 데이터셋 (algo/data/*.graphml·pkl, datasets/*)
COPY algo/   ./algo/
COPY datasets/ ./datasets/
COPY app/    ./app/

ENV RUNSTOP_DATA_DIR=/srv/runstop/datasets \
    RUNSTOP_GRAPHML=/srv/runstop/algo/data/서울_보행네트워크.graphml \
    PYTHONUNBUFFERED=1

EXPOSE 8000
# 그래프(191MB graphml → pkl 캐시) 로드가 수 초 걸리므로 워커 1, 타임아웃 여유
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
