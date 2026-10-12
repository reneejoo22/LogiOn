"""시연용 초기 데이터.

기사·점포는 앱의 MockUser.kt / MockDat.kt, 품목·별칭은 AI 노트북의 ITEM_FORMS 값이다.
점포 전화번호·좌표·바코드는 실제 값이 아닌 임시 값이다.
"""
import sqlite3
from datetime import date, datetime

DRIVER = (1, "김도윤", "성수 2권역", "82허 4210")

# (id, name, short_name, address, phone, lat, lng)
STORES = [
    (1, "GS25 성수연무장점", "성수연무장점", "서울 성동구 연무장길 21", "02-0000-0001", 37.5428, 127.0563),
    (2, "CU 서울숲점", "서울숲점", "서울 성동구 서울숲2길 32", "02-0000-0002", 37.5466, 127.0432),
    (3, "세븐일레븐 뚝섬점", "뚝섬점", "서울 광진구 능동로 10", "02-0000-0003", 37.5316, 127.0667),
]

# 이름: (구역, 부르는 이름들)
PRODUCTS = {
    "서울우유": ("chilled", ["서울우유", "우유"]),
    "바나나우유": ("chilled", ["바나나우유", "바나나 우유"]),
    "딸기우유": ("chilled", ["딸기우유", "딸기 우유"]),
    "요거트": ("chilled", ["요거트", "요구르트"]),
    "아이스크림": ("chilled", ["아이스크림"]),
    "제육도시락": ("ready_meal", ["제육도시락", "제육 도시락", "도시락"]),
    "치킨마요도시락": ("ready_meal", ["치킨마요도시락", "치킨마요", "마요 도시락"]),
    "참치삼각김밥": ("ready_meal", ["참치삼각김밥", "참치김밥", "삼각김밥"]),
    "스팸마요삼각김밥": ("ready_meal", ["스팸마요삼각김밥", "스팸마요", "삼각김밥"]),
    "샌드위치": ("ready_meal", ["샌드위치"]),
    "컵라면": ("ready_meal", ["컵라면", "라면"]),
    "새우깡": ("ready_meal", ["새우깡"]),
    "감자칩": ("ready_meal", ["감자칩"]),
    "초코파이": ("ready_meal", ["초코파이"]),
    "젤리": ("ready_meal", ["젤리"]),
    "생수": ("ambient_drink", ["생수", "물"]),
    "콜라": ("ambient_drink", ["콜라"]),
    "사이다": ("ambient_drink", ["사이다"]),
    "이온음료": ("ambient_drink", ["이온음료", "이온 음료"]),
    "캔커피": ("ambient_drink", ["캔커피", "커피"]),
}

# 오늘 운행: (store_id, eta, distance_km, notice, 구역별 박스, 품목)
ROUTE_STOPS = [
    (1, "10:25", 1.8, "냉장 상품 4박스가 별도 구역에 있습니다.",
     {"tobacco": 2, "ambient_drink": 3, "chilled": 4, "ready_meal": 3},
     [("서울우유", 12, "개"), ("바나나우유", 6, "개"), ("제육도시락", 4, "개"), ("생수", 2, "박스")]),
    (2, "10:48", 3.2, None,
     {"tobacco": 1, "ambient_drink": 3, "chilled": 2, "ready_meal": 2},
     [("서울우유", 6, "개"), ("참치삼각김밥", 10, "개"), ("콜라", 1, "박스")]),
    (3, "11:16", 5.7, None,
     {"tobacco": 3, "ambient_drink": 5, "chilled": 4, "ready_meal": 3},
     [("샌드위치", 8, "개"), ("캔커피", 2, "박스"), ("초코파이", 3, "박스")]),
]
DEPART, EST_END, SYNCED = "09:40", "12:05", "09:38"


def seed_master(conn: sqlite3.Connection) -> None:
    """기준 정보(기사·점포·품목·별칭). 이미 있으면 건너뛴다."""
    if conn.execute("SELECT 1 FROM drivers LIMIT 1").fetchone():
        return
    conn.execute("INSERT INTO drivers (id, name, area, vehicle_number) VALUES (?, ?, ?, ?)", DRIVER)
    conn.executemany(
        "INSERT INTO stores (id, name, short_name, address, phone, lat, lng) VALUES (?, ?, ?, ?, ?, ?, ?)",
        STORES,
    )
    for i, (name, (category, forms)) in enumerate(PRODUCTS.items(), start=1):
        conn.execute(
            "INSERT INTO products (id, name, category, barcode) VALUES (?, ?, ?, ?)",
            (i, name, category, f"88000000{i:05d}"),
        )
        aliases = {f.replace(" ", "") for f in forms}
        conn.executemany(
            "INSERT INTO product_aliases (product_id, alias) VALUES (?, ?)",
            [(i, a) for a in sorted(aliases)],
        )


def ensure_today_route(conn: sqlite3.Connection, day: date | None = None) -> None:
    """오늘 날짜 운행이 없으면 시연용 운행을 만든다. 실제 배차 데이터가 들어오면 대체할 부분."""
    day = day or date.today()
    driver_id = DRIVER[0]
    if conn.execute(
        "SELECT 1 FROM routes WHERE driver_id = ? AND service_date = ?", (driver_id, day.isoformat())
    ).fetchone():
        return

    def at(hhmm: str) -> str:
        return f"{day.isoformat()}T{hhmm}:00"

    now = datetime.now().isoformat(timespec="seconds")
    route_id = conn.execute(
        "INSERT INTO routes (driver_id, service_date, depart_at, est_end_at, synced_at) VALUES (?, ?, ?, ?, ?)",
        (driver_id, day.isoformat(), at(DEPART), at(EST_END), at(SYNCED)),
    ).lastrowid
    product_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM products")}
    for seq, (store_id, eta, km, notice, zones, items) in enumerate(ROUTE_STOPS, start=1):
        stop_id = conn.execute(
            "INSERT INTO stops (route_id, store_id, seq, eta, distance_km, notice, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (route_id, store_id, seq, at(eta), km, notice, now),
        ).lastrowid
        conn.executemany(
            "INSERT INTO stop_zones (stop_id, category, boxes, updated_at) VALUES (?, ?, ?, ?)",
            [(stop_id, category, boxes, now) for category, boxes in zones.items()],
        )
        conn.executemany(
            "INSERT INTO stop_items (stop_id, product_id, qty, unit) VALUES (?, ?, ?, ?)",
            [(stop_id, product_ids[name], qty, unit) for name, qty, unit in items],
        )


def seed(conn: sqlite3.Connection) -> None:
    seed_master(conn)
    ensure_today_route(conn)
