import json

import requests
from fastapi.testclient import TestClient

from conftest import make_crop_bundle, register, upload
from app.main import create_app
from app.services.crop import CropService
from app.services.fertilizer import recommend as fert

GOOD = dict(N=80, P=45, K=40, temperature=24, humidity=82, ph=6.4, rainfall=230)


# ---- crop recommendation ----------------------------------------------------------------
def test_crop_recommendation_valid_input_saved(authed):
    r = authed.post("/api/crop/recommend", json=GOOD)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["recommended"] == "rice" and len(d["alternatives"]) == 2 and d["factors"] and not d["warnings"]
    assert "separate from the disease" in authed.get(f"/api/recommendations/{d['id']}").json()["model_info"]
    assert authed.get("/api/activity?type=crop").json()["total"] == 1


def test_crop_invalid_inputs(authed):
    assert authed.post("/api/crop/recommend", json={**GOOD, "ph": 15}).status_code == 400
    assert authed.post("/api/crop/recommend", json={**GOOD, "humidity": -5}).status_code == 400
    assert authed.post("/api/crop/recommend", json={**GOOD, "N": None}).status_code == 400
    assert authed.post("/api/crop/recommend", json={**GOOD, "N": "abc"}).status_code == 400
    assert authed.get("/api/activity").json()["total"] == 0


def test_crop_out_of_training_range_warns(authed):
    d = authed.post("/api/crop/recommend", json={**GOOD, "rainfall": 4000}).json()
    assert any("outside the range" in w for w in d["warnings"])


def test_crop_model_missing_gives_503(tmp_path):
    from app.config import Settings
    s = Settings(data_dir=tmp_path / "d", model_dir=tmp_path / "m", secret_key="test-secret-at-least-32-bytes-long-for-jwt-signing!")
    c = TestClient(create_app(s))
    register(c)
    assert c.get("/api/crop/info").json()["available"] is False
    r = c.post("/api/crop/recommend", json=GOOD)
    assert r.status_code == 503 and "train_crop_model" in r.json()["detail"]
    assert c.get("/api/activity").json()["total"] == 0  # nothing fabricated or stored


def test_corrupt_crop_model_is_handled(tmp_path):
    (tmp_path / "crop_model.joblib").write_bytes(b"junk")
    svc = CropService(tmp_path)
    assert svc.available is False and "could not be loaded" in svc.error


def test_crop_bundle_metrics_are_real():
    m = make_crop_bundle()["metrics"]
    assert 0.9 <= m["holdout_accuracy"] <= 1.0 and m["n_test"] == 36 and "Offline" in m["scope"]


# ---- fertilizer ----------------------------------------------------------------------------
def test_fertilizer_low_nutrient_options_and_no_rates(authed):
    d = authed.post("/api/fertilizer/recommend", json={"crop": "Rice", "n_level": "low", "p_level": "medium", "k_level": "high", "ph": 5.2}).json()
    by = {n["nutrient"]: n for n in d["nutrients"]}
    assert by["Nitrogen"]["options"] and not by["Phosphorus"]["options"] and "avoid adding more" in by["Potassium"]["finding"]
    assert "lime" in d["ph"]["option"].lower() and "labels" in d["safety"]
    text = json.dumps(d).lower()
    assert "kg/ha" not in text and "per acre" not in text
    assert authed.get("/api/activity?type=fertilizer").json()["total"] == 1


def test_fertilizer_does_not_invent_deficiency_for_unmeasured():
    d = fert("wheat", {"N": "low"}, None)
    by = {n["nutrient"]: n for n in d["nutrients"]}
    assert by["Phosphorus"]["level"] == "not measured" and "no conclusion" in by["Phosphorus"]["finding"].lower() and by["Phosphorus"]["options"] == []
    assert d["ph"] is None


def test_fertilizer_validation(authed):
    # Empty crop name is rejected
    assert authed.post("/api/fertilizer/recommend", json={"crop": ""}).status_code == 400
    # Invalid nutrient level is rejected
    assert authed.post("/api/fertilizer/recommend", json={"crop": "rice", "n_level": "extreme"}).status_code == 400
    # Invalid pH is rejected
    assert authed.post("/api/fertilizer/recommend", json={"crop": "rice", "ph": 20}).status_code == 400


def test_fertilizer_crop_only_recommendation(authed):
    # Crop name is the primary required input; does not require manual N/P/K levels
    r = authed.post("/api/fertilizer/recommend", json={"crop": "Rice"})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["crop"] == "Rice"
    assert d["data_available"] is True
    assert d["has_soil_test"] is False
    assert d["recommendation_type"] == "crop_general"
    assert len(d["nutrients"]) == 3
    # Clearly labeled as general recommendation
    assert any("general recommendation" in n.lower() for n in d["notes"])
    # Suitable options provided without inventing application rates
    text = json.dumps(d).lower()
    assert "kg/ha" not in text and "per acre" not in text


def test_fertilizer_optional_soil_test_personalizes(authed):
    # When farmer provides measured results under optional soil test, recommendation is personalized
    r = authed.post("/api/fertilizer/recommend", json={"crop": "Grapes", "n_level": "low", "k_level": "high", "ph": 6.8})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["has_soil_test"] is True
    assert d["recommendation_type"] == "soil_test_personalized"
    by = {n["nutrient"]: n for n in d["nutrients"]}
    assert by["Nitrogen"]["level"] == "low"
    assert by["Potassium"]["level"] == "high"
    assert by["Phosphorus"]["level"] == "not measured"
    # Grapes special advice mentions Sulfate of Potash (SOP)
    assert any("sulfate of potash" in n.lower() for n in d["notes"])


def test_fertilizer_unknown_crop_avoids_fabrication(authed):
    # If crop is unknown and data is unavailable, explains this and avoids fabricating recommendations
    r = authed.post("/api/fertilizer/recommend", json={"crop": "UncatalogedPlantX"})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["data_available"] is False
    assert d["recommendation_type"] == "crop_data_unavailable"
    assert len(d["nutrients"]) == 0
    assert any("not currently cataloged" in n.lower() or "unavailable" in n.lower() for n in d["notes"])
    assert d.get("general_advice")


def test_fertilizer_free_form_crops_accepted(authed):
    # Free-form names including grapes, pears, tomato, rice are supported
    for crop in ("grapes", "pears", "Grape", "Pear", "Tomato", "Rice", "Wheat", "Maize"):
        r = authed.post("/api/fertilizer/recommend", json={"crop": crop})
        assert r.status_code == 201, f"{crop} should be accepted"
        assert r.json()["data_available"] is True


def test_fertilizer_legume_note():
    assert fert("Soybean", {"N": "low"}, None)["notes"]



# ---- weather -----------------------------------------------------------------------------------
class Resp:
    def __init__(self, code=200, data=None):
        self.status_code, self._d = code, data

    def json(self):
        if self._d is None:
            raise ValueError
        return self._d


class FakeHttp:
    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        return self.handler(url, params)


def weather_client(env_settings_dir, handler, key=""):
    from app.config import Settings
    s = Settings(data_dir=env_settings_dir / "d", model_dir=env_settings_dir / "m", secret_key="test-secret-at-least-32-bytes-long-for-jwt-signing!", openweather_key=key)
    c = TestClient(create_app(s, http=FakeHttp(handler)))
    register(c)
    return c


def meteo(url, params):
    if "geocoding" in url:
        return Resp(200, {"results": [{"name": "Davangere", "admin1": "Karnataka", "country_code": "IN", "latitude": 14.46, "longitude": 75.92}]} if params["name"] == "Davangere" else {})
    return Resp(200, {"current": {"time": "2026-10-10T12:00", "temperature_2m": 29.5, "relative_humidity_2m": 61, "precipitation": 0.0, "weather_code": 2},
                      "daily": {"time": ["2026-10-10", "2026-10-11"], "temperature_2m_max": [31, 30], "temperature_2m_min": [22, 21], "precipitation_sum": [0.0, 3.2], "weather_code": [2, 61]}})


def test_weather_open_meteo_success(tmp_path):
    c = weather_client(tmp_path, meteo)
    assert c.get("/api/weather/status").json() == {"provider": "Open-Meteo", "api_key_configured": False}
    d = c.get("/api/weather?location=Davangere").json()
    assert d["location"]["name"] == "Davangere" and d["current"]["temperature_c"] == 29.5 and d["fetched_at"] and d["observed_at"]
    assert d["forecast"][1]["conditions"] == "Light rain"


def test_weather_errors(tmp_path):
    c = weather_client(tmp_path, meteo)
    assert c.get("/api/weather?location=Nowhereville").status_code == 404
    assert c.get("/api/weather?location=").status_code == 400

    def timeout(url, params):
        raise requests.Timeout()
    assert weather_client(tmp_path / "t", timeout).get("/api/weather?location=Pune").status_code == 504
    assert weather_client(tmp_path / "s", lambda u, p: Resp(500, {})).get("/api/weather?location=Pune").status_code == 502
    assert weather_client(tmp_path / "j", lambda u, p: Resp(200, None)).get("/api/weather?location=Pune").status_code == 502
    r = weather_client(tmp_path / "k", lambda u, p: Resp(200, {"results": [{"name": "X"}]})).get("/api/weather?location=Pune")
    assert r.status_code == 502 and "Traceback" not in r.text


def test_weather_openweather_with_key(tmp_path):
    def owm(url, params):
        assert params["appid"] == "KEY123"
        if "geo" in url:
            return Resp(200, [{"name": "Pune", "state": "Maharashtra", "country": "IN", "lat": 18.5, "lon": 73.8}])
        if url.endswith("/weather"):
            return Resp(200, {"dt": 1760000000, "main": {"temp": 27.1, "humidity": 70}, "weather": [{"description": "scattered clouds"}], "rain": {"1h": 0.4}})
        return Resp(200, {"list": [{"dt_txt": "2026-10-11 09:00:00", "main": {"temp_min": 21, "temp_max": 28}, "weather": [{"description": "light rain"}], "rain": {"3h": 1.5}}]})
    c = weather_client(tmp_path, owm, key="KEY123")
    d = c.get("/api/weather?location=Pune").json()
    assert d["provider"] == "OpenWeatherMap" and d["current"]["precipitation_mm"] == 0.4 and d["forecast"][0]["precip_mm"] == 1.5
    assert "KEY123" not in json.dumps(d) and "KEY123" not in c.get("/api/weather/status").text


def test_weather_bad_key(tmp_path):
    r = weather_client(tmp_path, lambda u, p: Resp(401, {}), key="bad").get("/api/weather?location=Pune")
    assert r.status_code == 502 and "API key" in r.json()["detail"]


# ---- unified activity ------------------------------------------------------------------------------
def test_unified_activity_filter_export_and_dashboard(authed):
    upload(authed)
    authed.post("/api/crop/recommend", json=GOOD)
    authed.post("/api/fertilizer/recommend", json={"crop": "rice", "k_level": "low"})
    a = authed.get("/api/activity").json()
    assert a["total"] == 3 and {i["type"] for i in a["items"]} == {"disease", "crop", "fertilizer"}
    assert authed.get("/api/activity?type=disease").json()["total"] == 1
    assert authed.get("/api/activity?date_from=2999-01-01").json()["total"] == 0
    assert authed.get("/api/activity?type=bogus").status_code == 400
    csv = authed.get("/api/activity/export.csv")
    assert csv.status_code == 200 and csv.text.count("\n") == 4
    d = authed.get("/api/dashboard").json()
    assert (d["total"], d["crop_count"], d["fertilizer_count"], len(d["recent_activity"])) == (1, 1, 1, 3)
    rid = authed.get("/api/activity?type=crop").json()["items"][0]["id"]
    assert authed.delete(f"/api/recommendations/{rid}").status_code == 200
    assert authed.get("/api/activity").json()["total"] == 2
