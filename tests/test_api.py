from fastapi.testclient import TestClient

from app import config, updater
from app.sources import Row


def test_data_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "market.db")
    monkeypatch.setattr(config, "SCHEDULER_ENABLED", False)
    monkeypatch.setattr(config, "AUTO_BOOTSTRAP", False)
    from app import db, main

    db.init()
    updater.store([
        Row("eln", "inventory", "2026-07", "5260", "美好", 5e8),
        Row("eln", "inventory", "2026-09", "5260", "美好", 6e8),
        Row("eln", "inventory", "2026-09", "9800", "元大", 9e9),
        Row("eln", "inventory", "2026-09", "1234", "某某證券", 0),
    ], "test")

    with TestClient(main.app) as client:
        body = client.get("/api/data").json()
        assert client.post("/api/refresh").status_code == 404  # no ADMIN_TOKEN configured

    eln = next(p for p in body["products"] if p["id"] == "eln")["metrics"]["inventory"]
    assert eln["months"] == ["2026-07", "2026-08", "2026-09"]  # gap month kept as null
    assert [b["name"] for b in eln["brokers"]] == ["元大", "美好"]  # sorted by latest, all-zero dropped
    assert eln["brokers"][1]["values"] == [5.0, None, 6.0]  # 億元
