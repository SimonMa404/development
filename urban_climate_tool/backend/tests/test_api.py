from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "registered_layers" in data


def test_layers_endpoint() -> None:
    response = client.get("/api/layers")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1


def test_unknown_layer() -> None:
    response = client.get("/api/layers/does-not-exist")
    assert response.status_code == 404


def test_raster_tile_endpoint() -> None:
    response = client.get("/api/tiles/lst-planegg/14/8711/5688.png")
    assert response.status_code in {200, 400}
    if response.status_code == 200:
        assert response.headers["content-type"] == "image/png"


def test_raster_point_endpoint() -> None:
    response = client.get("/api/rasters/lst-planegg/point?lon=11.42&lat=48.10")
    assert response.status_code == 200
    data = response.json()
    assert data["layer_id"] == "lst-planegg"


def test_area_statistics_endpoint() -> None:
    payload = {
        "layer_ids": ["lst-planegg", "ndvi-planegg"],
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[11.415, 48.095], [11.435, 48.095], [11.435, 48.105], [11.415, 48.105], [11.415, 48.095]]],
        },
    }
    response = client.post("/api/analysis/area-statistics", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 2
    for result in data["results"]:
        assert "selected" in result
        assert "baseline" in result
        assert result["selected"]["count"] > 0


def test_heat_vulnerability_endpoint() -> None:
    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[11.415, 48.095], [11.435, 48.095], [11.435, 48.105], [11.415, 48.105], [11.415, 48.095]]],
        },
        "census_layer_id": "census-2022-100m-planegg",
        "lst_layer_id": "lst-planegg",
    }
    response = client.post("/api/analysis/heat-vulnerability", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "result" in body
    assert "summary" in body["result"]
    assert "lst_exposure_bins" in body["result"]
