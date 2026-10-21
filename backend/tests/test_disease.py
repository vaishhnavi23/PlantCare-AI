import io
import numpy as np
from PIL import Image
from conftest import FakeMember, leaf_png, upload
from app.ml.ensemble import MemberOutput, aggregate
from app.ml.members import FeatureClassifierMember
from app.ml.registry import ModelRegistry


def test_valid_upload_saved_and_serialised(authed):
    r = upload(authed)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["label"] == "Apple___Black_rot" and d["status"] == "ok" and d["models_used"] == ["ResNet50 + SVM"]
    assert d["expert"]["level"] == "recommended" and d["disease_info"]["causes"]
    assert authed.get(d["image_url"]).status_code == 200
    assert authed.get("/api/predictions").json()["total"] == 1
    assert d["has_heatmap"] is False  # fake member is not a CNN: no heatmap is invented


def unrelated_png(size=300):
    buf = io.BytesIO()
    Image.new("RGB", (size, size), (20, 50, 240)).save(buf, "PNG")
    return buf.getvalue()


def stem_png(size=300):
    buf = io.BytesIO()
    Image.new("RGB", (size, size), (139, 69, 19)).save(buf, "PNG")
    return buf.getvalue()


def whole_plant_png(size=300):
    from PIL import ImageDraw
    im = Image.new("RGB", (size, size), (120, 100, 80))
    draw = ImageDraw.Draw(im)
    draw.line([(150, 50), (150, 270)], fill=(80, 50, 20), width=6)
    draw.ellipse([50, 60, 110, 120], fill=(40, 140, 50))
    draw.ellipse([190, 70, 250, 130], fill=(40, 140, 50))
    draw.ellipse([40, 160, 100, 220], fill=(40, 140, 50))
    draw.ellipse([200, 170, 260, 230], fill=(40, 140, 50))
    draw.ellipse([120, 30, 180, 90], fill=(40, 140, 50))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def person_png(size=300):
    from PIL import ImageDraw
    im = Image.new("RGB", (size, size), (220, 215, 205))
    draw = ImageDraw.Draw(im)
    draw.rectangle([60, 40, 240, 160], fill=(45, 30, 20))
    draw.ellipse([80, 70, 220, 250], fill=(215, 160, 125))
    draw.ellipse([105, 120, 135, 140], fill=(250, 245, 240))
    draw.ellipse([115, 123, 128, 137], fill=(45, 30, 20))
    draw.ellipse([165, 120, 195, 140], fill=(250, 245, 240))
    draw.ellipse([172, 123, 185, 137], fill=(45, 30, 20))
    draw.rectangle([105, 110, 135, 115], fill=(45, 30, 20))
    draw.rectangle([165, 110, 195, 115], fill=(45, 30, 20))
    draw.ellipse([125, 200, 175, 215], fill=(185, 80, 80))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def cartoon_png(size=300):
    from PIL import ImageDraw
    im = Image.new("RGB", (size, size), (255, 240, 245))
    draw = ImageDraw.Draw(im)
    draw.rectangle([20, 20, size - 20, size - 20], fill=(255, 210, 60), outline=(0, 0, 0), width=4)
    draw.ellipse([60, 60, 130, 130], fill=(255, 255, 255), outline=(0, 0, 0), width=3)
    draw.ellipse([170, 60, 240, 130], fill=(255, 255, 255), outline=(0, 0, 0), width=3)
    draw.ellipse([85, 85, 105, 105], fill=(0, 0, 0))
    draw.ellipse([195, 85, 215, 105], fill=(0, 0, 0))
    draw.arc([80, 150, 220, 220], 0, 180, fill=(0, 0, 0), width=5)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def ambiguous_leaf_png(size=300):
    buf = io.BytesIO()
    Image.new("RGB", (size, size), (128, 128, 128)).save(buf, "PNG")
    return buf.getvalue()


def test_invalid_uploads_rejected(authed):
    assert upload(authed, b"", "e.png").status_code == 400
    assert upload(authed, b"not an image", "x.png").status_code == 400
    assert upload(authed, b"hello", "x.txt").status_code == 400
    assert upload(authed, leaf_png(), "x.gif").status_code == 400
    assert upload(authed, leaf_png(40), "tiny.png").status_code == 400
    assert upload(authed, leaf_png(), "x.png", part="root").status_code == 400
    assert upload(authed, leaf_png()[:200], "trunc.png").status_code == 400
    big = leaf_png(1900, seed=3)
    assert len(big) > 5 * 1024 * 1024
    assert upload(authed, big, "big.png").status_code == 400
    # Unrelated non-plant images must be rejected
    assert upload(authed, unrelated_png(), "car.png").status_code == 400
    assert authed.get("/api/predictions").json()["total"] == 0


def test_content_must_match_extension_type(authed):
    # a text file renamed .png is rejected by content check
    assert upload(authed, b"<html>evil</html>" * 50, "evil.png").status_code == 400


def test_non_leaf_parts_are_flagged_unvalidated(authed):
    # Stem photos (brown woody tones) are valid plant images but flagged unvalidated
    r = upload(authed, stem_png(), part="stem")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "unvalidated" and any("unvalidated prototype" in r for r in d["reasons"])



def test_quality_warning_makes_result_uncertain(authed):
    flat = io.BytesIO(); Image.new("RGB", (300, 300), (128, 128, 128)).save(flat, "PNG")
    d = upload(authed, flat.getvalue(), "grey.png").json()
    assert d["status"] == "uncertain" and any("preliminary" in r for r in d["reasons"])


def test_regression_person_photo_rejected(authed):
    # A photo of a person must be rejected before inference with a helpful message
    r = upload(authed, person_png(), "person.png")
    assert r.status_code == 400
    assert "person or face" in r.json()["detail"].lower()
    # Confirm no diagnosis was created in DB
    assert authed.get("/api/predictions").json()["total"] == 0


def test_regression_cartoon_illustration_rejected(authed):
    # A cartoon or digital illustration must be rejected before inference
    r = upload(authed, cartoon_png(), "cartoon.png")
    assert r.status_code == 400
    assert "cartoon or illustration" in r.json()["detail"].lower()
    # Confirm no diagnosis was created in DB
    assert authed.get("/api/predictions").json()["total"] == 0


def test_regression_valid_leaf_accepted(authed):
    # A valid leaf image must be accepted and diagnosed
    r = upload(authed, leaf_png(), "leaf.png")
    assert r.status_code == 200
    d = r.json()
    assert d["label"] == "Apple___Black_rot"
    assert d["status"] == "ok"


def test_regression_ambiguous_image_gives_uncertain_status(authed):
    # An ambiguous/unusual image must not be rejected outright, but flagged uncertain with warnings
    r = upload(authed, ambiguous_leaf_png(), "ambiguous.png")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "uncertain"
    assert any("preliminary" in r for r in d["reasons"])


def test_low_confidence_and_conflict(env, authed):
    env.registry.inject([FakeMember(probs=(0.4, 0.35, 0.25))])
    assert upload(authed).json()["status"] == "uncertain"
    env.registry.inject([FakeMember("A", (0.9, 0.05, 0.05)), FakeMember("B", (0.05, 0.9, 0.05))])
    d = upload(authed).json()
    assert d["status"] == "conflict" and d["expert"]["level"] in ("recommended", "urgent") and d["agreement"] == 0.5


def test_urgent_for_high_concern_disease(env, authed):
    env.registry.inject([FakeMember(probs=(0.02, 0.03, 0.95))])
    assert upload(authed).json()["expert"]["level"] == "urgent"


def test_healthy_ok_result_expert_optional(env, authed):
    env.registry.inject([FakeMember(probs=(0.02, 0.96, 0.02))])
    d = upload(authed).json()
    assert d["is_healthy"] and d["expert"]["level"] == "optional"


def test_missing_model_gives_503_not_traceback(env, authed):
    env.registry.members, env.registry.error = [], "weights missing"
    r = authed.post("/api/predict", files={"file": ("a.png", leaf_png(), "image/png")}, data={"plant_part": "leaf"})
    assert r.status_code == 503 and "Traceback" not in r.text
    assert authed.get("/api/health").json()["model"]["available"] is False


def test_failed_member_is_reported_but_others_used(env, authed):
    env.registry.inject([FakeMember("good"), FakeMember("bad", fail=True)])
    d = upload(authed).json()
    assert d["models_used"] == ["good"] and d["failed_members"] and "bad" in d["failed_members"][0]


def test_ensemble_math():
    cls = ["a", "b", "c"]
    out = aggregate([MemberOutput("m1", cls, np.array([.6, .3, .1])), MemberOutput("m2", cls, np.array([.2, .7, .1]))])
    assert out["label"] == "b" or out["label"] == "a"
    assert abs(out["probability"] - 0.5) < 1e-9 and out["status"] == "conflict"


def test_class_order_is_aligned_between_members(env, authed):
    other = FakeMember("shuffled", probs=(0.05, 0.03, 0.92), classes=["Tomato___Late_blight", "Apple___healthy", "Apple___Black_rot"])
    # shuffled member's argmax is Apple___Black_rot (index 2 in its own order)
    env.registry.inject([FakeMember(), other])
    assert upload(authed).json()["agreement"] == 1.0


def test_feature_bundle_member_with_stub_extractor(tmp_path, monkeypatch):
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from app.ml import features
    rng = np.random.default_rng(1)
    X = np.vstack([rng.normal(0, 1, (30, 1280)), rng.normal(3, 1, (30, 1280))]); y = ["Apple___healthy"] * 30 + ["Apple___Black_rot"] * 30
    est = RandomForestClassifier(n_estimators=20, random_state=0).fit(X, y)
    joblib.dump({"extractor": "mobilenetv2", "classifier": "RF", "model": est, "classes": list(est.classes_)}, tmp_path / "m.joblib")
    monkeypatch.setattr(features, "extract", lambda imgs, name: np.full((len(imgs), 1280), 3.0, dtype=np.float32))
    m = FeatureClassifierMember(tmp_path / "m.joblib")
    out = m.predict(Image.new("RGB", (100, 100)))
    assert m.name == "MobileNetV2 + RF" and out.classes[int(np.argmax(out.probs))] == "Apple___Black_rot"
    monkeypatch.setattr(features, "extract", lambda imgs, name: np.zeros((len(imgs), 5), dtype=np.float32))
    import pytest
    from app.ml.members import ModelUnavailable
    with pytest.raises(ModelUnavailable):
        m.predict(Image.new("RGB", (100, 100)))


def test_corrupt_bundle_is_skipped(tmp_path):
    from app.ml.members import load_bundles
    (tmp_path / "bad.joblib").write_bytes(b"garbage")
    members, problems = load_bundles(tmp_path)
    assert members == [] and len(problems) == 1


def test_history_filters_pagination_delete(env, authed):
    env.registry.inject([FakeMember(probs=(0.02, 0.96, 0.02))]); upload(authed)
    env.registry.inject([FakeMember()])
    for _ in range(3):
        upload(authed, part="stem")
    all_ = authed.get("/api/predictions?page_size=2").json()
    assert all_["total"] == 4 and all_["pages"] == 2 and len(all_["items"]) == 2
    assert authed.get("/api/predictions?result=healthy").json()["total"] == 1
    assert authed.get("/api/predictions?plant_part=stem").json()["total"] == 3
    assert authed.get("/api/predictions?q=black").json()["total"] == 3
    assert authed.get("/api/predictions?date_from=2999-01-01").json()["total"] == 0
    pid = all_["items"][0]["id"]
    assert authed.delete(f"/api/predictions/{pid}").status_code == 200
    assert authed.get(f"/api/predictions/{pid}").status_code == 404
    assert authed.get("/api/predictions").json()["total"] == 3


def test_analytics_and_dashboard_use_real_records(env, authed):
    d = authed.get("/api/dashboard").json()
    assert d["total"] == 0 and d["avg_confidence"] is None and d["recent"] == []
    env.registry.inject([FakeMember(probs=(0.02, 0.96, 0.02))]); upload(authed)
    env.registry.inject([FakeMember()]); upload(authed); upload(authed)
    a = authed.get("/api/analytics").json()
    assert (a["total"], a["healthy"], a["diseased"]) == (3, 1, 2)
    assert a["distribution"][0] == {"label": "Apple Black rot", "count": 2}
    assert abs(a["avg_confidence"] - (0.96 + 0.92 * 2) / 3) < 1e-3
    assert sum(b["count"] for b in a["confidence_buckets"]) == 3
    assert a["model_evaluation"] is None  # no evaluation.json => no invented model comparison
    assert authed.get("/api/analytics?disease=Apple___healthy").json()["total"] == 1
    assert authed.get("/api/dashboard").json()["total"] == 3


def test_library_and_search(authed):
    lib = authed.get("/api/library").json()
    assert len(lib["items"]) >= 38 or len(lib["items"]) == 3
    r = authed.get("/api/library?q=late blight").json()["items"]
    assert r and all("blight" in e["title"].lower() or "blight" in e["symptoms"].lower() for e in r)
    assert any(e["detectable"] for e in lib["items"])  # classes from the loaded (fake) model
    assert authed.get("/api/library?crop=Apple").json()["items"]


def test_consultation_request_saved_honestly(authed):
    pid = upload(authed).json()["id"]
    r = authed.post("/api/consultations", json={"prediction_id": pid, "name": "Asha", "contact": "9999999999", "urgency": "urgent", "message": "Leaves spotting fast"})
    assert r.status_code == 201 and "not sent" in r.json()["message"]
    assert len(authed.get("/api/consultations").json()["items"]) == 1
    assert authed.post("/api/consultations", json={"name": "A", "contact": "x", "message": "hi"}).status_code == 400
    assert authed.get("/api/experts").json() == {"items": [], "configured": False}


def test_experts_directory_from_config(env, authed):
    env.settings.experts_file.write_text('[{"name":"Dr. Test","email":"t@example.org"},{"nope":1}]')
    d = authed.get("/api/experts").json()
    assert d["configured"] and len(d["items"]) == 1


def test_detect_part_leaf(authed):
    r = authed.post("/api/detect-part", files={"file": ("leaf.png", leaf_png(), "image/png")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["plant_part"] == "leaf"
    assert d["label"] == "Leaf"
    assert d["supported_for_disease_model"] is True
    assert d["confidence"] >= 0.55
    assert d["limitation_warning"] is None


def test_detect_part_stem(authed):
    r = authed.post("/api/detect-part", files={"file": ("stem.png", stem_png(), "image/png")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["plant_part"] == "stem"
    assert d["label"] == "Stem"
    assert d["supported_for_disease_model"] is False
    assert d["limitation_warning"] is not None
    assert "leaf images" in d["limitation_warning"]


def test_detect_part_whole_plant(authed):
    r = authed.post("/api/detect-part", files={"file": ("whole.png", whole_plant_png(), "image/png")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["plant_part"] == "whole_plant"
    assert d["label"] == "Whole Crop"
    assert d["supported_for_disease_model"] is False
    assert d["limitation_warning"] is not None
    assert "leaf images" in d["limitation_warning"]


def test_detect_part_uncertain(authed):
    r = authed.post("/api/detect-part", files={"file": ("grey.png", ambiguous_leaf_png(), "image/png")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["plant_part"] == "uncertain"
    assert d["supported_for_disease_model"] is False
    assert "clearer" in d["limitation_warning"].lower()


def test_detect_part_non_plant_rejected(authed):
    # Person photo
    r = authed.post("/api/detect-part", files={"file": ("person.png", person_png(), "image/png")})
    assert r.status_code == 400
    assert "person or face" in r.json()["detail"].lower()

    # Cartoon illustration
    r = authed.post("/api/detect-part", files={"file": ("cartoon.png", cartoon_png(), "image/png")})
    assert r.status_code == 400
    assert "cartoon or illustration" in r.json()["detail"].lower()

    # Synthetic non-plant image
    r = authed.post("/api/detect-part", files={"file": ("blue.png", unrelated_png(), "image/png")})
    assert r.status_code == 400
    assert "plant" in r.json()["detail"].lower()


def test_predict_auto_detects_plant_part_leaf(authed):
    r = authed.post("/api/predict", files={"file": ("leaf.png", leaf_png(), "image/png")}, data={"plant_part": "auto"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["plant_part"] == "leaf"
    assert d["status"] == "ok"
    # Verify recorded correctly in history
    p_id = d["id"]
    rec = authed.get(f"/api/predictions/{p_id}").json()
    assert rec["plant_part"] == "leaf"


def test_predict_auto_detects_plant_part_stem_with_limitations(authed):
    r = authed.post("/api/predict", files={"file": ("stem.png", stem_png(), "image/png")}, data={"plant_part": "auto"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["plant_part"] == "stem"
    assert d["status"] == "unvalidated"
    assert any("unvalidated prototype" in r for r in d["reasons"])
    # Verify recorded correctly in history
    p_id = d["id"]
    rec = authed.get(f"/api/predictions/{p_id}").json()
    assert rec["plant_part"] == "stem"


def test_predict_auto_rejects_uncertain_part(authed):
    r = authed.post("/api/predict", files={"file": ("ambig.png", ambiguous_leaf_png(), "image/png")}, data={"plant_part": "auto"})
    assert r.status_code == 400
    assert "detection is uncertain" in r.json()["detail"].lower()

