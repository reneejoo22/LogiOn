"""배송 데이터 조회·변경. 화면 API와 (나중에 붙을) 음성 명령이 같이 쓰는 곳.

찾는 대상이 없으면 None을 돌려주고, HTTP 상태 코드는 api 쪽에서 정한다.
"""
import sqlite3
from datetime import date, datetime

CATEGORY_LABELS = {
    "tobacco": "담배류",
    "ambient_drink": "상온 음료",
    "chilled": "냉장 상품",
    "ready_meal": "간편식",
}

_STOP_SELECT = """
SELECT s.id, s.route_id, s.seq, s.eta, s.distance_km, s.notice, s.status, s.completed_at, s.receiver,
       st.id AS store_id, st.name AS store_name, st.short_name, st.address, st.phone, st.lat, st.lng,
       (SELECT COALESCE(SUM(z.boxes), 0) FROM stop_zones z WHERE z.stop_id = s.id) AS boxes
FROM stops s JOIN stores st ON st.id = s.store_id
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _next_stop_id(conn: sqlite3.Connection, route_id: int) -> int | None:
    """다음 배송지 = 아직 안 끝난 곳 중 순서가 가장 빠른 곳."""
    row = conn.execute(
        "SELECT id FROM stops WHERE route_id = ? AND status = 'pending' ORDER BY seq LIMIT 1", (route_id,)
    ).fetchone()
    return row["id"] if row else None


def _stop_dict(row: sqlite3.Row, next_id: int | None) -> dict:
    return {
        "id": row["id"],
        "seq": row["seq"],
        "store": {
            "id": row["store_id"],
            "name": row["store_name"],
            "short_name": row["short_name"],
            "address": row["address"],
            "phone": row["phone"],
            "lat": row["lat"],
            "lng": row["lng"],
        },
        "eta": row["eta"],
        "distance_km": row["distance_km"],
        "boxes": row["boxes"],
        "notice": row["notice"],
        "status": row["status"],
        "is_next": row["id"] == next_id,
        "completed_at": row["completed_at"],
        "receiver": row["receiver"],
    }


def get_driver(conn: sqlite3.Connection, driver_id: int = 1) -> dict | None:
    row = conn.execute("SELECT * FROM drivers WHERE id = ?", (driver_id,)).fetchone()
    if not row:
        return None
    driver = dict(row)
    # 앱 프로필 동그라미에 들어가는 글자 (김도윤 -> 도)
    driver["initial"] = row["name"][1] if len(row["name"]) > 1 else row["name"][:1]
    return driver


def get_today_route(conn: sqlite3.Connection, driver_id: int = 1, day: date | None = None) -> dict | None:
    day = day or date.today()
    route = conn.execute(
        "SELECT * FROM routes WHERE driver_id = ? AND service_date = ?", (driver_id, day.isoformat())
    ).fetchone()
    if not route:
        return None
    next_id = _next_stop_id(conn, route["id"])
    rows = conn.execute(_STOP_SELECT + " WHERE s.route_id = ? ORDER BY s.seq", (route["id"],)).fetchall()
    stops = [_stop_dict(r, next_id) for r in rows]
    done = sum(1 for s in stops if s["status"] == "done")
    return {
        "id": route["id"],
        "service_date": route["service_date"],
        "depart_at": route["depart_at"],
        "est_end_at": route["est_end_at"],
        "synced_at": route["synced_at"],
        "summary": {
            "total": len(stops),
            "done": done,
            "remaining": len(stops) - done,
            "progress": round(done / len(stops), 2) if stops else 0.0,
        },
        "next_stop_id": next_id,
        "stops": stops,
    }


def get_stop(conn: sqlite3.Connection, stop_id: int) -> dict | None:
    """배송지 상세: 기본 정보 + 구역별 박스 + 품목 + 이상 보고."""
    row = conn.execute(_STOP_SELECT + " WHERE s.id = ?", (stop_id,)).fetchone()
    if not row:
        return None
    stop = _stop_dict(row, _next_stop_id(conn, row["route_id"]))

    zones = {
        z["category"]: z
        for z in conn.execute("SELECT category, boxes, checked FROM stop_zones WHERE stop_id = ?", (stop_id,))
    }
    stop["zones"] = [
        {"category": c, "label": label, "boxes": zones[c]["boxes"], "checked": bool(zones[c]["checked"])}
        for c, label in CATEGORY_LABELS.items()
        if c in zones
    ]
    stop["items"] = [
        dict(r)
        for r in conn.execute(
            "SELECT si.id, p.id AS product_id, p.name, p.category, si.qty, si.unit"
            " FROM stop_items si JOIN products p ON p.id = si.product_id"
            " WHERE si.stop_id = ? ORDER BY si.id",
            (stop_id,),
        )
    ]
    stop["issues"] = [
        dict(r)
        for r in conn.execute(
            "SELECT i.id, i.product_id, p.name AS product_name, i.type, i.qty, i.unit, i.source, i.created_at"
            " FROM issues i LEFT JOIN products p ON p.id = i.product_id"
            " WHERE i.stop_id = ? ORDER BY i.id",
            (stop_id,),
        )
    ]
    return stop


def complete_stop(conn: sqlite3.Connection, stop_id: int, receiver: str | None = None) -> dict | None:
    """납품 완료. 앱 동작과 같이 구역 확인도 전부 체크한다."""
    now = _now()
    cur = conn.execute(
        "UPDATE stops SET status = 'done', completed_at = ?, receiver = ?, updated_at = ? WHERE id = ?",
        (now, receiver, now, stop_id),
    )
    if cur.rowcount == 0:
        return None
    conn.execute("UPDATE stop_zones SET checked = 1, updated_at = ? WHERE stop_id = ?", (now, stop_id))
    return get_stop(conn, stop_id)


def cancel_complete(conn: sqlite3.Connection, stop_id: int) -> dict | None:
    """완료 취소. 구역 확인 상태도 초기화한다."""
    now = _now()
    cur = conn.execute(
        "UPDATE stops SET status = 'pending', completed_at = NULL, receiver = NULL, updated_at = ? WHERE id = ?",
        (now, stop_id),
    )
    if cur.rowcount == 0:
        return None
    conn.execute("UPDATE stop_zones SET checked = 0, updated_at = ? WHERE stop_id = ?", (now, stop_id))
    return get_stop(conn, stop_id)


def set_zone_checked(conn: sqlite3.Connection, stop_id: int, category: str, checked: bool) -> dict | None:
    cur = conn.execute(
        "UPDATE stop_zones SET checked = ?, updated_at = ? WHERE stop_id = ? AND category = ?",
        (int(checked), _now(), stop_id, category),
    )
    if cur.rowcount == 0:
        return None
    return get_stop(conn, stop_id)


def product_exists(conn: sqlite3.Connection, product_id: int) -> bool:
    return conn.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone() is not None


def create_issue(
    conn: sqlite3.Connection,
    stop_id: int,
    type: str,
    product_id: int | None = None,
    qty: int | None = None,
    unit: str | None = None,
    source: str = "touch",
) -> dict | None:
    if not conn.execute("SELECT 1 FROM stops WHERE id = ?", (stop_id,)).fetchone():
        return None
    if qty is None:
        unit = None
    elif unit is None:
        unit = "개"  # 수량만 말한 경우 기본 단위 (AI 노트북 resolve와 같은 규칙)
    issue_id = conn.execute(
        "INSERT INTO issues (stop_id, product_id, type, qty, unit, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (stop_id, product_id, type, qty, unit, source, _now()),
    ).lastrowid
    row = conn.execute(
        "SELECT i.id, i.stop_id, i.product_id, p.name AS product_name, i.type, i.qty, i.unit, i.source, i.created_at"
        " FROM issues i LEFT JOIN products p ON p.id = i.product_id WHERE i.id = ?",
        (issue_id,),
    ).fetchone()
    return dict(row)


def find_product_by_barcode(conn: sqlite3.Connection, barcode: str, driver_id: int = 1) -> dict | None:
    """바코드로 품목을 찾고, 오늘 어느 배송지에 몇 개 내리는지도 같이 준다."""
    row = conn.execute("SELECT id, name, category, barcode FROM products WHERE barcode = ?", (barcode,)).fetchone()
    if not row:
        return None
    product = dict(row)
    product["category_label"] = CATEGORY_LABELS[row["category"]]
    product["deliveries"] = [
        dict(r)
        for r in conn.execute(
            "SELECT s.id AS stop_id, st.name AS store_name, s.status, si.qty, si.unit"
            " FROM stop_items si"
            " JOIN stops s ON s.id = si.stop_id"
            " JOIN routes r ON r.id = s.route_id"
            " JOIN stores st ON st.id = s.store_id"
            " WHERE si.product_id = ? AND r.driver_id = ? AND r.service_date = ?"
            " ORDER BY s.seq",
            (row["id"], driver_id, date.today().isoformat()),
        )
    ]
    return product
