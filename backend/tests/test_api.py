import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGION_DB", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_driver(client):
    d = client.get("/api/driver").json()
    assert d["name"] == "김도윤"
    assert d["initial"] == "도"


def test_today_route(client):
    r = client.get("/api/routes/today").json()
    assert r["summary"] == {"total": 3, "done": 0, "remaining": 3, "progress": 0.0}
    assert [s["store"]["name"] for s in r["stops"]] == ["GS25 성수연무장점", "CU 서울숲점", "세븐일레븐 뚝섬점"]
    assert [s["boxes"] for s in r["stops"]] == [12, 8, 15]
    assert [s["is_next"] for s in r["stops"]] == [True, False, False]
    assert r["next_stop_id"] == r["stops"][0]["id"]


def test_stop_detail(client):
    s = client.get("/api/stops/1").json()
    assert [z["label"] for z in s["zones"]] == ["담배류", "상온 음료", "냉장 상품", "간편식"]
    assert sum(z["boxes"] for z in s["zones"]) == s["boxes"] == 12
    assert {"name": "서울우유", "qty": 12, "unit": "개"}.items() <= s["items"][0].items()
    assert s["issues"] == []


def test_complete_moves_next_and_cancel_restores(client):
    done = client.post("/api/stops/1/complete", json={"receiver": "점장님"}).json()
    assert done["status"] == "done" and done["receiver"] == "점장님" and done["completed_at"]
    assert all(z["checked"] for z in done["zones"])

    r = client.get("/api/routes/today").json()
    assert r["summary"]["done"] == 1 and r["summary"]["progress"] == 0.33
    assert r["next_stop_id"] == 2

    back = client.delete("/api/stops/1/complete").json()
    assert back["status"] == "pending" and back["receiver"] is None and back["completed_at"] is None
    assert not any(z["checked"] for z in back["zones"])
    assert client.get("/api/routes/today").json()["next_stop_id"] == 1


def test_complete_without_body(client):
    assert client.post("/api/stops/2/complete").json()["status"] == "done"


def test_all_done_has_no_next(client):
    for stop_id in (1, 2, 3):
        client.post(f"/api/stops/{stop_id}/complete")
    r = client.get("/api/routes/today").json()
    assert r["next_stop_id"] is None and r["summary"]["progress"] == 1.0


def test_zone_check(client):
    s = client.patch("/api/stops/1/zones/chilled", json={"checked": True}).json()
    assert {z["category"]: z["checked"] for z in s["zones"]} == {
        "tobacco": False, "ambient_drink": False, "chilled": True, "ready_meal": False,
    }
    assert client.patch("/api/stops/1/zones/frozen", json={"checked": True}).status_code == 422


def test_issue(client):
    res = client.post("/api/stops/1/issues", json={"type": "파손", "product_id": 1, "qty": 2})
    assert res.status_code == 201
    issue = res.json()
    assert issue["product_name"] == "서울우유" and issue["unit"] == "개" and issue["source"] == "touch"
    assert len(client.get("/api/stops/1").json()["issues"]) == 1

    assert client.post("/api/stops/1/issues", json={"type": "누락"}).status_code == 422
    assert client.post("/api/stops/1/issues", json={"type": "파손", "product_id": 999}).status_code == 404


def test_barcode(client):
    p = client.get("/api/products/barcode/8800000000001").json()
    assert p["name"] == "서울우유" and p["category_label"] == "냉장 상품"
    assert [(d["stop_id"], d["qty"]) for d in p["deliveries"]] == [(1, 12), (2, 6)]


def test_not_found(client):
    assert client.get("/api/stops/999").status_code == 404
    assert client.post("/api/stops/999/complete").status_code == 404
    assert client.post("/api/stops/999/issues", json={"type": "파손"}).status_code == 404
    assert client.get("/api/products/barcode/0000").status_code == 404
