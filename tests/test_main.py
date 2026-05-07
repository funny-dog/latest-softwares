from __future__ import annotations

import json

from fastapi.testclient import TestClient

import main


def test_download_redirect_records_metrics(tmp_path, monkeypatch, capsys):
    data_file = tmp_path / "latest.json"
    db_file = tmp_path / "metrics.db"
    data_file.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "packages": [
                    {
                        "id": "ubuntu",
                        "name": "Ubuntu",
                        "category": "Operating Systems",
                        "version": "26.04",
                        "source": "Ubuntu releases",
                        "assets": [
                            {
                                "platform": "desktop-amd64",
                                "url": "https://releases.ubuntu.com/26.04/ubuntu-26.04-desktop-amd64.iso",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "DATA_FILE", data_file)
    monkeypatch.setattr(main, "DB_PATH", db_file)

    client = TestClient(main.app)

    response = client.get(
        "/api/download/ubuntu/desktop-amd64",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"].endswith("ubuntu-26.04-desktop-amd64.iso")

    metrics = client.get("/api/metrics").json()
    assert metrics["scope"] == "instance-local"
    assert metrics["downloads"]["total"] == 1
    assert metrics["downloads"]["packages"]["ubuntu"] == 1
    assert metrics["downloads"]["assets"]["ubuntu:desktop-amd64"] == 1
    captured = capsys.readouterr().out
    assert '"event":"download"' in captured
    assert '"package_id":"ubuntu"' in captured


def test_visit_endpoint_records_page_views(tmp_path, monkeypatch, capsys):
    db_file = tmp_path / "metrics.db"
    monkeypatch.setattr(main, "DB_PATH", db_file)

    client = TestClient(main.app)

    response = client.post("/api/visit")

    assert response.status_code == 200
    assert response.json()["metrics"]["visits"]["total"] == 1
    metrics = client.get("/api/metrics").json()
    assert metrics["scope"] == "instance-local"
    assert metrics["visits"]["total"] == 1
    assert metrics["visits"]["paths"]["/"] == 1
    assert '"event":"visit"' in capsys.readouterr().out


def test_seed_db_from_json_restores_metrics(tmp_path, monkeypatch):
    db_file = tmp_path / "metrics.db"
    seed_file = tmp_path / "site_metrics.json"
    seed_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scope": "instance-local",
                "storage": "persistent-sqlite",
                "updated_at": "2026-05-05T12:00:00+00:00",
                "visits": {"total": 42, "paths": {"/": 42}},
                "downloads": {
                    "total": 100,
                    "packages": {"vscode": 60, "chrome": 40},
                    "platforms": {"win-x64": 70, "mac-arm64": 30},
                    "assets": {
                        "vscode:win-x64": 50,
                        "vscode:mac-arm64": 10,
                        "chrome:win-x64": 20,
                        "chrome:mac-arm64": 20,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "DB_PATH", db_file)
    monkeypatch.setattr(main, "SEED_FILE", seed_file)

    main._seed_db_from_json()

    metrics = main._load_metrics()
    assert metrics["visits"]["total"] == 42
    assert metrics["visits"]["paths"]["/"] == 42
    assert metrics["downloads"]["total"] == 100
    assert metrics["downloads"]["packages"]["vscode"] == 60
    assert metrics["downloads"]["packages"]["chrome"] == 40
    assert metrics["downloads"]["assets"]["vscode:win-x64"] == 50
    assert metrics["downloads"]["assets"]["chrome:mac-arm64"] == 20
    assert metrics["updated_at"] == "2026-05-05T12:00:00+00:00"


def test_seed_db_skips_when_db_already_has_data(tmp_path, monkeypatch):
    db_file = tmp_path / "metrics.db"
    seed_file = tmp_path / "site_metrics.json"
    seed_file.write_text(
        json.dumps(
            {
                "visits": {"total": 999, "paths": {}},
                "downloads": {"total": 0, "packages": {}, "platforms": {}, "assets": {}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "DB_PATH", db_file)
    monkeypatch.setattr(main, "SEED_FILE", seed_file)

    main._init_db()
    conn = __import__("sqlite3").connect(str(db_file))
    conn.execute(
        "INSERT INTO metrics (key, value) VALUES ('visits_total', '10')"
    )
    conn.commit()
    conn.close()

    main._seed_db_from_json()

    metrics = main._load_metrics()
    assert metrics["visits"]["total"] == 10


def test_seed_db_skips_when_seed_file_missing(tmp_path, monkeypatch):
    db_file = tmp_path / "metrics.db"
    seed_file = tmp_path / "nonexistent.json"
    monkeypatch.setattr(main, "DB_PATH", db_file)
    monkeypatch.setattr(main, "SEED_FILE", seed_file)

    main._seed_db_from_json()

    metrics = main._load_metrics()
    assert metrics["visits"]["total"] == 0
    assert metrics["downloads"]["total"] == 0


def test_seed_db_skips_empty_seed(tmp_path, monkeypatch):
    db_file = tmp_path / "metrics.db"
    seed_file = tmp_path / "site_metrics.json"
    seed_file.write_text(
        json.dumps(
            {
                "visits": {"total": 0, "paths": {}},
                "downloads": {"total": 0, "packages": {}, "platforms": {}, "assets": {}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "DB_PATH", db_file)
    monkeypatch.setattr(main, "SEED_FILE", seed_file)

    main._seed_db_from_json()

    metrics = main._load_metrics()
    assert metrics["visits"]["total"] == 0
    assert metrics["downloads"]["total"] == 0


def test_lifespan_seeds_db_on_startup(tmp_path, monkeypatch):
    db_file = tmp_path / "metrics.db"
    seed_file = tmp_path / "site_metrics.json"
    seed_file.write_text(
        json.dumps(
            {
                "visits": {"total": 7, "paths": {"/": 7}},
                "downloads": {
                    "total": 3,
                    "packages": {"firefox": 3},
                    "platforms": {"win-x64": 3},
                    "assets": {"firefox:win-x64": 3},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "DB_PATH", db_file)
    monkeypatch.setattr(main, "SEED_FILE", seed_file)

    with TestClient(main.app) as client:
        metrics = client.get("/api/metrics").json()
        assert metrics["visits"]["total"] == 7
        assert metrics["downloads"]["total"] == 3
        assert metrics["downloads"]["assets"]["firefox:win-x64"] == 3
