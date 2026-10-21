"""PlantCare AI - FastAPI backend (auth, diagnosis, history, library, analytics, profile, expert assistance)."""

import json
import logging
import sqlite3
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from PIL import Image

from .config import Settings
from .db import Database
from .disease_info import get_disease_info, is_high_concern
from .library import build_library
from .ml.explain import gradcam_overlay
from .ml.labels import canon, display, is_healthy, split_label
from .ml.members import ModelUnavailable
from .ml.registry import ModelRegistry
from .services import fertilizer as fert_svc
from .services.crop import CropService, CropUnavailable, InputError
from .services.weather import WeatherError, fetch_weather, provider_name
from .security import (COOKIE_NAME, EMAIL_RE, LoginThrottle, hash_password, make_token, password_problem, read_token,
                       verify_password)
from .services.plant_part import PlantPartClassifier
from .validation import ImageRejected, validate_upload

log = logging.getLogger("plantcare")
PLANT_PARTS = {"leaf", "stem", "whole_plant"}
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- request models --------------------------------------------------------------
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)


class CropIn(BaseModel):
    N: Optional[float] = None
    P: Optional[float] = None
    K: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    ph: Optional[float] = None
    rainfall: Optional[float] = None


class FertIn(BaseModel):
    crop: str = Field(default="", max_length=100)
    n_level: Optional[str] = None
    p_level: Optional[str] = None
    k_level: Optional[str] = None
    ph: Optional[float] = None
    growth_stage: Optional[str] = Field(default=None, max_length=50)
    location: Optional[str] = Field(default=None, max_length=100)


class ConsultIn(BaseModel):
    prediction_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=80)
    contact: str = Field(min_length=3, max_length=200)
    urgency: str = Field(default="normal", pattern="^(normal|urgent)$")
    message: str = Field(min_length=5, max_length=2000)


# ---- helpers -----------------------------------------------------------------------
def expert_assessment(label: str, status: str, reasons: list, plant_part: str) -> dict:
    healthy = is_healthy(label)
    if healthy and status == "ok":
        return {"level": "optional", "reason": "No disease was indicated for this image. Consult an expert if you still notice symptoms in the field."}
    if not healthy and is_high_concern(label):
        return {"level": "urgent", "reason": "This problem can spread quickly or has no cure, so please have it confirmed by an agricultural expert or plant pathologist soon."}
    if not healthy:
        return {"level": "recommended", "reason": "A disease was indicated. Please have it confirmed by an agricultural expert before choosing any treatment."}
    return {"level": "recommended", "reason": "The result is not reliable enough to rely on: " + (reasons[0] if reasons else "please verify with an expert.")}


def row_to_record(row) -> dict:
    d = json.loads(row["details_json"])
    label = row["label"]
    return {
        "id": row["id"], "created_at": row["created_at"], "original_name": row["original_name"], "plant_part": row["plant_part"],
        "label": label, "title": display(label), "crop": row["crop"], "disease": row["disease"], "is_healthy": bool(row["is_healthy"]),
        "confidence": row["confidence"], "status": row["status"], "reasons": d.get("reasons", []),
        "expert": {"level": row["expert_level"], "reason": d.get("expert_reason", "")},
        "top": [{**t, "title": display(t["label"])} for t in d.get("top", [])], "members": d.get("members", []),
        "agreement": d.get("agreement"), "models_used": d.get("models_used", []), "failed_members": d.get("failed_members", []),
        "quality": d.get("quality"), "latency_ms": row["latency_ms"], "has_heatmap": bool(row["heatmap_file"]),
        "heatmap_note": d.get("heatmap_note"), "disease_info": get_disease_info(label),
        "image_url": f"/api/predictions/{row['id']}/image", "heatmap_url": f"/api/predictions/{row['id']}/heatmap" if row["heatmap_file"] else None,
    }


def user_dict(row) -> dict:
    return {"id": row["id"], "name": row["name"], "email": row["email"], "created_at": row["created_at"]}


def create_app(settings: Settings | None = None, registry: ModelRegistry | None = None, crop: CropService | None = None, http=None, part_classifier: PlantPartClassifier | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.ensure_dirs()
    db = Database(settings.db_path)
    db.init()
    registry = registry or ModelRegistry(settings)
    throttle = LoginThrottle()
    crop = crop or CropService(settings.model_dir)
    part_classifier = part_classifier or PlantPartClassifier(settings.data_dir / "plant_part_model.joblib")
    app_http = http

    app = FastAPI(title="PlantCare AI", version="2.0.0", description="Multimodal, multimodel plant disease detection and expert assistance.")
    app.state.settings, app.state.db, app.state.registry, app.state.crop, app.state.part_classifier = settings, db, registry, crop, part_classifier
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(RequestValidationError)
    async def _validation(_req, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(x) for x in first.get("loc", [])[1:]) or "input"
        return JSONResponse(status_code=400, content={"detail": f"Invalid {field}: {first.get('msg', 'please check your input')}."})

    @app.exception_handler(Exception)
    async def _unhandled(_req, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Please try again."})

    # ---- auth plumbing ---------------------------------------------------------------
    def current_user(request: Request):
        token = request.cookies.get(COOKIE_NAME)
        uid = read_token(token, settings.secret_key) if token else None
        if uid is None:
            raise HTTPException(401, "Please log in to continue.")
        with db.conn() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            raise HTTPException(401, "Please log in to continue.")
        return row

    User = Annotated[object, Depends(current_user)]

    def set_cookie(resp: Response, user_id: int):
        resp.set_cookie(COOKIE_NAME, make_token(user_id, settings.secret_key, settings.session_days), httponly=True,
                        samesite="lax", secure=settings.cookie_secure, max_age=settings.session_days * 86400, path="/")

    # ---- public --------------------------------------------------------------------
    @app.get("/api/health")
    def health():
        st = registry.status()
        return {"status": "ok" if st["available"] or not st["loaded"] else "degraded", "model": st, "model_id": settings.model_id, "crop_model_available": crop.available}

    # ---- auth ----------------------------------------------------------------------
    @app.post("/api/auth/register", status_code=201)
    def register(body: RegisterIn, response: Response):
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "Please enter your name.")
        email = body.email.strip().lower()
        if not EMAIL_RE.match(email):
            raise HTTPException(400, "Please enter a valid email address.")
        problem = password_problem(body.password)
        if problem:
            raise HTTPException(400, problem)
        try:
            with db.conn() as c:
                if c.execute("SELECT 1 FROM users WHERE lower(email)=?", (email,)).fetchone():
                    raise HTTPException(409, "An account with this email already exists.")
                cur = c.execute("INSERT INTO users(email,name,password_hash,created_at) VALUES(?,?,?,?)",
                                (email, name, hash_password(body.password), now_iso()))
                row = c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
        except sqlite3.IntegrityError:
            raise HTTPException(409, "An account with this email already exists.")
        set_cookie(response, row["id"])
        return {"user": user_dict(row)}

    @app.post("/api/auth/login")
    def login(body: LoginIn, request: Request, response: Response):
        email = body.email.strip().lower()
        key = f"{request.client.host if request.client else '?'}|{email}"
        if throttle.blocked(key):
            raise HTTPException(429, "Too many failed attempts. Please wait a few minutes and try again.")
        with db.conn() as c:
            row = c.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
        if not row or not verify_password(body.password, row["password_hash"]):
            throttle.fail(key)
            raise HTTPException(401, "Incorrect email or password.")
        throttle.clear(key)
        set_cookie(response, row["id"])
        return {"user": user_dict(row)}

    @app.post("/api/auth/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"ok": True}

    @app.get("/api/auth/me")
    def me(user: User):
        return {"user": user_dict(user)}

    # ---- profile -------------------------------------------------------------------
    @app.get("/api/profile")
    def profile(user: User):
        with db.conn() as c:
            r = c.execute("SELECT COUNT(*) n, COALESCE(SUM(is_healthy),0) h FROM predictions WHERE user_id=?", (user["id"],)).fetchone()
        return {"user": user_dict(user), "stats": {"total": r["n"], "healthy": r["h"], "diseased": r["n"] - r["h"]}}

    @app.patch("/api/profile")
    def update_profile(body: ProfileIn, user: User):
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "Please enter your name.")
        with db.conn() as c:
            c.execute("UPDATE users SET name=? WHERE id=?", (name, user["id"]))
            row = c.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        return {"user": user_dict(row)}

    @app.post("/api/profile/password")
    def change_password(body: PasswordIn, user: User):
        if not verify_password(body.current_password, user["password_hash"]):
            raise HTTPException(400, "Your current password is incorrect.")
        problem = password_problem(body.new_password)
        if problem:
            raise HTTPException(400, problem)
        with db.conn() as c:
            c.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(body.new_password), user["id"]))
        return {"ok": True}

    # ---- diagnosis -----------------------------------------------------------------
    @app.post("/api/detect-part")
    async def detect_part(user: User, file: Annotated[UploadFile, File()]):
        max_bytes = settings.max_upload_mb * 1024 * 1024
        data = await file.read(max_bytes + 1)
        try:
            image, quality = validate_upload(data, file.filename or "", max_bytes, plant_part="auto")
        except ImageRejected as exc:
            raise HTTPException(400, str(exc))
        return part_classifier.classify(image)

    @app.post("/api/predict")
    async def predict(user: User, file: Annotated[UploadFile, File()], plant_part: Annotated[str, Form()] = "auto"):
        if plant_part != "auto" and plant_part not in PLANT_PARTS:
            raise HTTPException(400, "Plant part must be leaf, stem or whole_plant.")
        max_bytes = settings.max_upload_mb * 1024 * 1024
        data = await file.read(max_bytes + 1)
        try:
            image, quality = validate_upload(data, file.filename or "", max_bytes, plant_part=plant_part)
        except ImageRejected as exc:
            raise HTTPException(400, str(exc))

        if plant_part == "auto":
            detection = part_classifier.classify(image)
            if detection["plant_part"] == "uncertain":
                raise HTTPException(400, "Plant part detection is uncertain. The image may be blurry, low-contrast, or ambiguous. Please upload a clear photo of a plant leaf, stem, or whole plant.")
            plant_part = detection["plant_part"]

        started = time.perf_counter()
        try:
            result = registry.predict(image)
        except ModelUnavailable as exc:
            log.error("Model unavailable: %s", exc)
            raise HTTPException(503, f"The disease-detection model is not available right now. {exc}")
        label = result["label"]
        latency = round((time.perf_counter() - started) * 1000)

        status, reasons = result["status"], list(result["reasons"])
        if plant_part != "leaf":
            reasons.append("The classifier was trained on leaf images. Predictions for stem or whole-plant photos are an unvalidated prototype and should not be trusted without expert confirmation.")
            if status == "ok":
                status = "unvalidated"
        if quality.warnings:
            reasons.extend(quality.warnings)
            if status == "ok":
                status = "uncertain"
        expert = expert_assessment(label, status, reasons, plant_part)
        if status in ("uncertain", "conflict") and expert["level"] == "optional":
            expert["level"] = "recommended"

        uid = uuid.uuid4().hex
        image_file = f"{uid}.jpg"
        save = image.copy()
        save.thumbnail((1600, 1600))
        save.save(settings.upload_dir / image_file, "JPEG", quality=92)  # re-encoding also strips metadata

        heatmap_file, heatmap_note = None, None
        cnn = registry.primary_cnn()
        if cnn is not None:
            try:
                idx = [canon(c) for c in cnn.classes].index(canon(label))
                overlay = gradcam_overlay(cnn, image, idx)
            except Exception:
                overlay = None
            if overlay is not None:
                heatmap_file = f"{uid}_cam.jpg"
                overlay.thumbnail((1600, 1600))
                overlay.save(settings.upload_dir / heatmap_file, "JPEG", quality=90)
                heatmap_note = "Grad-CAM from the ResNet50 network only. It shows where that network looked, not a confirmed lesion, and does not explain the SVM/Random Forest members."
        details = {"top": result["top"], "members": result["members"], "agreement": result["agreement"], "reasons": reasons,
                   "quality": quality.as_dict(), "models_used": result["models_used"], "failed_members": result["failed_members"],
                   "expert_reason": expert["reason"], "heatmap_note": heatmap_note}
        crop, disease = split_label(label)
        with db.conn() as c:
            cur = c.execute(
                "INSERT INTO predictions(user_id,original_name,image_file,heatmap_file,plant_part,label,crop,disease,is_healthy,confidence,status,expert_level,details_json,latency_ms,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (user["id"], (file.filename or "image")[:120], image_file, heatmap_file, plant_part, label, crop, disease,
                 int(is_healthy(label)), result["probability"], status, expert["level"], json.dumps(details), latency, now_iso()))
            row = c.execute("SELECT * FROM predictions WHERE id=?", (cur.lastrowid,)).fetchone()
        return row_to_record(row)

    def own_prediction(pid: int, user) -> object:
        with db.conn() as c:
            row = c.execute("SELECT * FROM predictions WHERE id=? AND user_id=?", (pid, user["id"])).fetchone()
        if not row:
            raise HTTPException(404, "Diagnosis not found.")
        return row

    @app.get("/api/predictions")
    def list_predictions(user: User, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50), q: str = "",
                         plant_part: str = "", status: str = "", result: str = "", date_from: str = "", date_to: str = ""):
        where, args = ["user_id=?"], [user["id"]]
        if q.strip():
            where.append("(label LIKE ? OR disease LIKE ? OR crop LIKE ? OR original_name LIKE ?)")
            args += [f"%{q.strip().replace('_', ' ')}%"] * 4
        if plant_part in PLANT_PARTS:
            where.append("plant_part=?"); args.append(plant_part)
        if status in ("ok", "uncertain", "conflict", "unvalidated"):
            where.append("status=?"); args.append(status)
        if result == "healthy":
            where.append("is_healthy=1")
        elif result == "diseased":
            where.append("is_healthy=0")
        if date_from:
            where.append("substr(created_at,1,10)>=?"); args.append(date_from[:10])
        if date_to:
            where.append("substr(created_at,1,10)<=?"); args.append(date_to[:10])
        sql = " AND ".join(where)
        with db.conn() as c:
            total = c.execute(f"SELECT COUNT(*) FROM predictions WHERE {sql}", args).fetchone()[0]
            rows = c.execute(f"SELECT * FROM predictions WHERE {sql} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                             args + [page_size, (page - 1) * page_size]).fetchall()
        return {"items": [row_to_record(r) for r in rows], "total": total, "page": page, "page_size": page_size,
                "pages": max(1, -(-total // page_size))}

    @app.get("/api/predictions/{pid}")
    def get_prediction(pid: int, user: User):
        return row_to_record(own_prediction(pid, user))

    @app.delete("/api/predictions/{pid}")
    def delete_prediction(pid: int, user: User):
        row = own_prediction(pid, user)
        with db.conn() as c:
            c.execute("DELETE FROM predictions WHERE id=? AND user_id=?", (pid, user["id"]))
        for name in (row["image_file"], row["heatmap_file"]):
            if name:
                (settings.upload_dir / name).unlink(missing_ok=True)
        return {"ok": True}

    def serve_file(name: Optional[str]):
        path = (settings.upload_dir / (name or "")).resolve()
        if not name or settings.upload_dir.resolve() not in path.parents or not path.exists():
            raise HTTPException(404, "File not found.")
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})

    @app.get("/api/predictions/{pid}/image")
    def prediction_image(pid: int, user: User):
        return serve_file(own_prediction(pid, user)["image_file"])

    @app.get("/api/predictions/{pid}/heatmap")
    def prediction_heatmap(pid: int, user: User):
        return serve_file(own_prediction(pid, user)["heatmap_file"])

    # ---- dashboard & analytics ----------------------------------------------------
    def stats_for(user_id: int, date_from: str = "", date_to: str = "", disease: str = "") -> dict:
        where, args = ["user_id=?"], [user_id]
        if date_from:
            where.append("substr(created_at,1,10)>=?"); args.append(date_from[:10])
        if date_to:
            where.append("substr(created_at,1,10)<=?"); args.append(date_to[:10])
        if disease:
            where.append("label=?"); args.append(disease)
        with db.conn() as c:
            rows = c.execute(f"SELECT * FROM predictions WHERE {' AND '.join(where)} ORDER BY created_at", args).fetchall()
        total = len(rows)
        healthy = sum(r["is_healthy"] for r in rows)
        dist = Counter(display(r["label"]) for r in rows)
        trend: dict = {}
        for r in rows:
            day = r["created_at"][:10]
            t = trend.setdefault(day, {"date": day, "healthy": 0, "diseased": 0})
            t["healthy" if r["is_healthy"] else "diseased"] += 1
        buckets = Counter()
        for r in rows:
            b = min(int(r["confidence"] * 10), 9)
            buckets[b] += 1
        models = Counter()
        for r in rows:
            for m in json.loads(r["details_json"]).get("models_used", []):
                models[m] += 1
        return {
            "total": total, "healthy": healthy, "diseased": total - healthy,
            "avg_confidence": round(sum(r["confidence"] for r in rows) / total, 4) if total else None,
            "distribution": [{"label": k, "count": v} for k, v in dist.most_common()],
            "trend": list(trend.values()),
            "confidence_buckets": [{"range": f"{i * 10}-{i * 10 + 10}%", "count": buckets.get(i, 0)} for i in range(10)],
            "status_counts": dict(Counter(r["status"] for r in rows)),
            "model_usage": [{"model": k, "count": v} for k, v in models.most_common()],
        }

    @app.get("/api/dashboard")
    def dashboard(user: User):
        s = stats_for(user["id"])
        with db.conn() as c:
            rows = c.execute("SELECT * FROM predictions WHERE user_id=? ORDER BY created_at DESC, id DESC LIMIT 5", (user["id"],)).fetchall()
        since = (datetime.now(timezone.utc) - timedelta(days=29)).date().isoformat()
        s["trend"] = [t for t in s["trend"] if t["date"] >= since]
        s["recent"] = [row_to_record(r) for r in rows]
        with db.conn() as c:
            counts = {r["kind"]: r["n"] for r in c.execute("SELECT kind, COUNT(*) n FROM recommendations WHERE user_id=? GROUP BY kind", (user["id"],))}
        s["crop_count"], s["fertilizer_count"] = counts.get("crop", 0), counts.get("fertilizer", 0)
        s["recent_activity"] = activity_rows(user["id"], "", "", "", "")[:8]
        return s

    @app.get("/api/analytics")
    def analytics(user: User, date_from: str = "", date_to: str = "", disease: str = ""):
        s = stats_for(user["id"], date_from, date_to, disease)
        with db.conn() as c:
            labels = [r[0] for r in c.execute("SELECT DISTINCT label FROM predictions WHERE user_id=? ORDER BY label", (user["id"],))]
        s["available_labels"] = [{"label": l, "title": display(l)} for l in labels]
        s["model_evaluation"] = load_evaluation()
        return s

    def load_evaluation():
        path = settings.model_dir / "evaluation.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    # ---- library -------------------------------------------------------------------
    @app.get("/api/library")
    def library(user: User, q: str = "", crop: str = "", status: str = ""):
        classes = registry.reference_classes or None
        items = build_library(classes)
        if q.strip():
            ql = q.strip().lower()
            items = [e for e in items if ql in (e["title"] + " " + e["symptoms"] + " " + e["causes"]).lower()]
        if crop:
            items = [e for e in items if e["crop"] == crop]
        if status:
            items = [e for e in items if e["status"] == status]
        return {"items": items, "crops": sorted({e["crop"] for e in build_library(classes)}),
                "note": "Reference information only. Entries marked 'detectable' are classes the loaded model can output; no reference photos are bundled."}

    # ---- expert assistance -------------------------------------------------------------
    @app.get("/api/experts")
    def experts(user: User):
        path = settings.experts_file
        entries = []
        if path.exists():
            try:
                for e in json.loads(path.read_text(encoding="utf-8")):
                    if isinstance(e, dict) and e.get("name"):
                        entries.append({k: str(e.get(k, ""))[:200] for k in ("name", "organisation", "specialty", "region", "email", "phone", "url")})
            except Exception:
                log.warning("experts.json could not be parsed")
        return {"items": entries, "configured": bool(entries)}

    @app.post("/api/consultations", status_code=201)
    def create_consultation(body: ConsultIn, user: User):
        if body.prediction_id is not None:
            own_prediction(body.prediction_id, user)
        with db.conn() as c:
            cur = c.execute("INSERT INTO consultations(user_id,prediction_id,name,contact,urgency,message,created_at) VALUES(?,?,?,?,?,?,?)",
                            (user["id"], body.prediction_id, body.name.strip(), body.contact.strip(), body.urgency, body.message.strip(), now_iso()))
        return {"id": cur.lastrowid, "status": "saved",
                "message": "Your request is saved in PlantCare AI. It is not sent to any expert automatically - use the contacts listed or your local agricultural office to follow up."}

    @app.get("/api/consultations")
    def list_consultations(user: User):
        with db.conn() as c:
            rows = c.execute("SELECT * FROM consultations WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
        return {"items": [dict(r) for r in rows]}

    # ---- crop recommendation (separate ML service) --------------------------------------
    def save_rec(user_id: int, kind: str, summary: str, inputs: dict, output: dict, model_info: str) -> int:
        with db.conn() as c:
            cur = c.execute("INSERT INTO recommendations(user_id,kind,summary,inputs_json,output_json,model_info,created_at) VALUES(?,?,?,?,?,?,?)",
                            (user_id, kind, summary, json.dumps(inputs), json.dumps(output), model_info, now_iso()))
            return cur.lastrowid

    def rec_to_dict(r) -> dict:
        return {"type": r["kind"], "id": r["id"], "created_at": r["created_at"], "summary": r["summary"], "inputs": json.loads(r["inputs_json"]),
                "output": json.loads(r["output_json"]), "model_info": r["model_info"]}

    @app.get("/api/crop/info")
    def crop_info(user: User):
        return crop.info()

    @app.post("/api/crop/recommend", status_code=201)
    def crop_recommend(body: CropIn, user: User):
        try:
            out = crop.recommend(body.model_dump())
        except InputError as exc:
            raise HTTPException(400, str(exc))
        except CropUnavailable as exc:
            raise HTTPException(503, str(exc))
        info = f"{out['model_info']['algorithm']} - separate from the disease models"
        rid = save_rec(user["id"], "crop", f"Recommended crop: {out['recommended']}", out["inputs"], out, info)
        return {"id": rid, **out}

    # ---- fertilizer guidance (rule-based) ---------------------------------------------------
    @app.post("/api/fertilizer/recommend", status_code=201)
    def fertilizer_recommend(body: FertIn, user: User):
        try:
            out = fert_svc.recommend(
                crop=body.crop,
                levels={"N": body.n_level, "P": body.p_level, "K": body.k_level},
                ph=body.ph,
                growth_stage=body.growth_stage,
                location=body.location,
            )
        except fert_svc.FertInputError as exc:
            raise HTTPException(400, str(exc))

        if not out.get("data_available", True):
            summary = f"{out['crop'].title()}: agronomic data unavailable - no recommendation fabricated"
        elif out.get("has_soil_test"):
            low = [n["nutrient"] for n in out["nutrients"] if n.get("level") == "low"]
            summary = f"{out['crop'].title()} (soil-tested): " + (("low " + ", ".join(low)) if low else "no soil deficiency indicated")
        else:
            summary = f"{out['crop'].title()}: general crop nutrient guidance"

        rid = save_rec(user["id"], "fertilizer", summary, out["inputs"] | {"crop": out["crop"]}, out, "Rule-based agronomic guidance (no ML)")
        return {"id": rid, **out}

    @app.get("/api/recommendations/{rid}")
    def get_recommendation(rid: int, user: User):
        with db.conn() as c:
            r = c.execute("SELECT * FROM recommendations WHERE id=? AND user_id=?", (rid, user["id"])).fetchone()
        if not r:
            raise HTTPException(404, "Record not found.")
        return rec_to_dict(r)

    @app.delete("/api/recommendations/{rid}")
    def delete_recommendation(rid: int, user: User):
        with db.conn() as c:
            n = c.execute("DELETE FROM recommendations WHERE id=? AND user_id=?", (rid, user["id"])).rowcount
        if not n:
            raise HTTPException(404, "Record not found.")
        return {"ok": True}

    # ---- unified activity history -----------------------------------------------------------
    def activity_rows(user_id: int, type_: str, date_from: str, date_to: str, q: str) -> list:
        items = []
        dsql, dargs = "", []
        if date_from:
            dsql += " AND substr(created_at,1,10)>=?"; dargs.append(date_from[:10])
        if date_to:
            dsql += " AND substr(created_at,1,10)<=?"; dargs.append(date_to[:10])
        with db.conn() as c:
            if type_ in ("", "disease"):
                for r in c.execute(f"SELECT * FROM predictions WHERE user_id=?{dsql}", [user_id] + dargs):
                    rec = row_to_record(r)
                    items.append({"type": "disease", "id": r["id"], "created_at": r["created_at"], "summary": f"{rec['title']} ({r['plant_part'].replace('_', ' ')})",
                                  "detail": f"{r['confidence'] * 100:.0f}% model confidence - {r['status']}", "thumb": rec["image_url"]})
            if type_ in ("", "crop", "fertilizer"):
                kind_sql = "" if type_ == "" else " AND kind=?"
                for r in c.execute(f"SELECT * FROM recommendations WHERE user_id=?{dsql}{kind_sql}", [user_id] + dargs + ([type_] if type_ else [])):
                    items.append({"type": r["kind"], "id": r["id"], "created_at": r["created_at"], "summary": r["summary"], "detail": r["model_info"], "thumb": None})
        if q.strip():
            ql = q.strip().lower()
            items = [i for i in items if ql in (i["summary"] + " " + i["detail"]).lower()]
        return sorted(items, key=lambda i: (i["created_at"], i["id"]), reverse=True)

    @app.get("/api/activity")
    def activity(user: User, type: str = "", q: str = "", date_from: str = "", date_to: str = "", page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50)):
        if type not in ("", "disease", "crop", "fertilizer"):
            raise HTTPException(400, "Unknown activity type.")
        rows = activity_rows(user["id"], type, date_from, date_to, q)
        return {"items": rows[(page - 1) * page_size: page * page_size], "total": len(rows), "page": page, "pages": max(1, -(-len(rows) // page_size))}

    @app.get("/api/activity/export.csv")
    def activity_export(user: User, type: str = "", date_from: str = "", date_to: str = ""):
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["date_time_utc", "type", "summary", "details"])
        for i in activity_rows(user["id"], type, date_from, date_to, ""):
            w.writerow([i["created_at"], i["type"], i["summary"], i["detail"]])
        return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=plantcare_activity.csv"})

    # ---- weather ------------------------------------------------------------------------------
    @app.get("/api/weather/status")
    def weather_status(user: User):
        return {"provider": provider_name(settings.openweather_key), "api_key_configured": bool(settings.openweather_key)}

    @app.get("/api/weather")
    def weather(user: User, location: str = ""):
        import requests as _rq
        try:
            return fetch_weather(location, settings.openweather_key, app_http or _rq)
        except WeatherError as exc:
            raise HTTPException(exc.status if exc.status in (400, 404, 429, 504) else 502, str(exc))

    # ---- optional: serve the built frontend --------------------------------------------
    if FRONTEND_DIST.exists():
        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404, "Not found.")
            target = (FRONTEND_DIST / path).resolve()
            if path and FRONTEND_DIST.resolve() in target.parents and target.is_file():
                return FileResponse(target)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
