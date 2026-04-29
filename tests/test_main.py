from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

import main


def test_download_redirect_records_metrics(tmp_path, monkeypatch, caplog):
    data_file = tmp_path / "latest.json"
    stats_file = tmp_path / "stats.json"
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
    monkeypatch.setattr(main, "STATS_FILE", stats_file)
    caplog.set_level(logging.INFO, logger="latest_softwares.metrics")

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
    assert '"event":"download"' in caplog.text
    assert '"package_id":"ubuntu"' in caplog.text


def test_visit_endpoint_records_page_views(tmp_path, monkeypatch, caplog):
    stats_file = tmp_path / "stats.json"
    monkeypatch.setattr(main, "STATS_FILE", stats_file)
    caplog.set_level(logging.INFO, logger="latest_softwares.metrics")

    client = TestClient(main.app)

    response = client.post("/api/visit")

    assert response.status_code == 200
    metrics = client.get("/api/metrics").json()
    assert metrics["scope"] == "instance-local"
    assert metrics["visits"]["total"] == 1
    assert metrics["visits"]["paths"]["/"] == 1
    assert '"event":"visit"' in caplog.text
