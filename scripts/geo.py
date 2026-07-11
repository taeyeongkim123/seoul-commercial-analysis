"""Korea Central Belt TM (서울 열린데이터광장 좌표계) -> WGS84 위경도 변환.

서울시 상권영역(TbgisTrdarRelm) API는 중심점 좌표를 GRS80 중부원점 TM으로 반환한다
(중앙 경선 127E, 기준위도 38N, false easting 200000, false northing 500000).
지도 라이브러리(pydeck/leaflet 등)는 WGS84 위경도를 요구하므로 역변환이 필요하다.
"""
from __future__ import annotations

import math


def tm_to_wgs84(x_value: float, y_value: float) -> tuple[float | None, float | None]:
    """TM(x, y) -> (lon, lat). 입력값이 비정상이면 (None, None)을 반환한다."""
    try:
        x = float(x_value)
        y = float(y_value)
    except (TypeError, ValueError):
        return None, None
    if math.isnan(x) or math.isnan(y):
        return None, None

    a = 6378137.0
    f = 1 / 298.257222101
    e2 = 2 * f - f * f
    ep2 = e2 / (1 - e2)
    lat0 = math.radians(38.0)
    lon0 = math.radians(127.0)
    false_easting = 200000.0
    false_northing = 500000.0
    scale = 1.0

    def meridian_arc(phi: float) -> float:
        return a * (
            (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * phi
            - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * phi)
            + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * phi)
            - (35 * e2**3 / 3072) * math.sin(6 * phi)
        )

    m0 = meridian_arc(lat0)
    m = m0 + (y - false_northing) / scale
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))

    fp = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )

    sin_fp = math.sin(fp)
    cos_fp = math.cos(fp)
    tan_fp = math.tan(fp)
    c1 = ep2 * cos_fp**2
    t1 = tan_fp**2
    n1 = a / math.sqrt(1 - e2 * sin_fp**2)
    r1 = a * (1 - e2) / (1 - e2 * sin_fp**2) ** 1.5
    d = (x - false_easting) / (n1 * scale)

    lat = fp - (n1 * tan_fp / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ep2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ep2 - 3 * c1**2) * d**6 / 720
    )
    lon = lon0 + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ep2 + 24 * t1**2) * d**5 / 120
    ) / cos_fp

    return round(math.degrees(lon), 7), round(math.degrees(lat), 7)
