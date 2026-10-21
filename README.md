# PlantCare AI — Multimodal, Multimodel Plant Disease Detection and Expert Assistance System

Built on your existing project (FastAPI backend + React/Vite frontend, originally "PlantGuard AI").
Four **separate** services share one login, database and UI:

| Service | What it is | Status in this package |
|---|---|---|
| Plant disease detection | Fine-tuned ResNet50 (Hugging Face `mesabo/agri-plant-disease-resnet50`, 38 PlantVillage classes) **plus optional** ResNet50/MobileNetV2 + SVM/Random Forest bundles, soft-voted | ResNet50 works as before. SVM/RF bundles **do not exist yet** — see "Train the disease SVM/RF models" |
| Crop recommendation | Random Forest on N, P, K, pH, temperature, humidity, rainfall | **Code complete, model not trained** — needs a dataset you download (see below) |
| Fertilizer guidance | Transparent rule set on soil-test categories (no ML) | Works |
| Weather | OpenWeatherMap (if key set) or keyless Open-Meteo | Works when internet is available |

## Assessment of the project you uploaded
* It contained **one** model: a single pretrained ResNet50 classifier downloaded from Hugging Face. There were **no** MobileNetV2, SVM or Random Forest artifacts, no saved features/scalers, no database, no login, and history lived in a Python list that vanished on restart. No crop or fertilizer data/models existed either.
* So the "4 model combinations" in the reference image are **supported by the code but not yet trained**. Until you train them, the app honestly runs the single ResNet50 and says so on every result ("Models used"). Nothing is faked.
* I kept the FastAPI + React stack, the Hugging Face model, `disease_info.py` guidance text and the dashboard look, and replaced the in-memory demo with a real application.

## Features
* **Auth** — register/login/logout, scrypt password hashing, HttpOnly session cookie, login throttling, protected routes, per-user data isolation.
* **Dashboard** — real per-user counts, trend chart, distribution donut, quick-action cards, recent activity, empty states.
* **Disease detection** — leaf / stem / whole-crop selector, drag-and-drop, preview, replace, client + server validation (type, content, size, min size). Blur / brightness / plant-colour checks are **preliminary warnings**, not a trained plant detector. Stem and whole-crop photos are flagged "unvalidated prototype" because the classifier is trained on leaf images.
* **Multimodel ensemble** — soft voting (mean of probabilities) over members that share the same class list; disagreement or low confidence ⇒ "uncertain/conflict" and an expert recommendation. Models actually used are shown per result.
* **Result page** — confidence labelled as a model score, per-model outputs, reference symptoms/causes/conditions/management (clearly labelled as general knowledge, **not** detected symptoms), expert section, print summary, delete.
* **Explainability** — Grad-CAM heatmap for the end-to-end ResNet50 only (see limitations). No invented per-model contribution percentages.
* **Crop recommendation, fertilizer guidance, weather insights** — see below.
* **Unified history** — disease + crop + fertilizer, filter by type/date/search, pagination, delete, open, print, CSV export.
* **Disease library** — built from the model's classes; "Detectable by current model" vs "Reference only"; searchable. Adding text never adds detectable classes.
* **Analytics** — filters by date/disease, healthy vs diseased, trend, confidence distribution, reliability breakdown, model usage. **Model comparison appears only if `backend/models/evaluation.json` exists** (real hold-out metrics).
* **Expert assistance** — consultation form saved locally (**not sent to anyone**), optional verified-contact directory from `backend/data/experts.json`, guidance for spreading problems.
* **Profile** — edit name, stats, change password, logout.

## Windows PowerShell setup
Requires Python 3.12, Node.js 20+ (you have these if the old project ran). If scripts are blocked: `Set-ExecutionPolicy -Scope Process Bypass`.

```powershell
cd PlantCare_AI
# Terminal 1 - backend (creates .venv, installs requirements, creates backend\.env from the example)
.\scripts\run_backend.ps1
# Terminal 2 - frontend dev server
.\scripts\run_frontend_dev.ps1      # open http://localhost:5173
```
Or a single server: `.\scripts\build_frontend.ps1` once, then `.\scripts\run_backend.ps1` and open http://127.0.0.1:8000.

The first prediction downloads the Hugging Face model (internet needed once). If it can't load, the app shows a clear 503 message instead of a traceback.
**Database:** SQLite at `backend\data\plantcare.db`, created automatically on first start (no migrations needed). Uploaded images: `backend\data\uploads\` (re-encoded JPEGs with random names, served only to their owner).

macOS/Linux: same steps with `python3 -m venv .venv && source .venv/bin/activate`, `pip install -r requirements.txt`, `uvicorn app.main:app --port 8000`, and `npm install && npm run dev`.

## Train the crop model (required for Crop Recommendation)
1. Download the public **Crop Recommendation Dataset** (Kaggle, "Atharva Ingle") — a CSV with columns `N,P,K,temperature,humidity,ph,rainfall,label` (22 crops). It is not bundled; Kaggle needs a login.
2. `cd backend; .\.venv\Scripts\Activate.ps1; python scripts\train_crop_model.py --csv C:\path\Crop_recommendation.csv`
3. Restart the backend. The page then shows the supported ranges, dataset and **your own** hold-out accuracy / CV scores.

Limitations to state in your report: the dataset is small, balanced and largely synthetic-looking; metrics are offline on that dataset, not field performance; it ignores soil type, season, variety, market and region. Feature importances shown are global, not per-prediction. N/P/K values are on the dataset's own scale. Weather can fill only temperature and humidity (the dataset's rainfall is a seasonal total, not a current reading).

## Train the disease SVM/RF models (optional, enables the multimodel ensemble)
Needs PyTorch and a PlantVillage-style folder `PlantVillage\<ClassName>\*.jpg` whose folder names match the ResNet50 model's labels (e.g. `Apple___Black_rot`).
```powershell
python scripts\train_feature_classifiers.py --data C:\data\PlantVillage --max-per-class 300
```
This writes up to four bundles (`resnet50_svm`, `resnet50_rf`, `mobilenetv2_svm`, `mobilenetv2_rf`) and `models\evaluation.json`. On restart the registry loads every bundle; any with a different class list, a corrupt file or a mismatched feature size is skipped and reported by `/api/health` instead of breaking the app. Feature extraction in training and inference share `app/ml/features.py` so preprocessing matches.

## Weather API setup
Default is Open-Meteo (no key). For OpenWeatherMap: create a free key at openweathermap.org, put `OPENWEATHER_API_KEY=...` in `backend\.env` (never in frontend code), restart. Invalid locations, timeouts, rate limits, bad keys and incomplete data return clear messages; values are never invented. Every result shows location, provider, observation time and fetch time.

## Expert directory
Copy `backend/data/experts.example.json` to `experts.json` and replace it with **real, verified** contacts. With no file, the page lists none and says so.

## Tests
```powershell
.\scripts\run_tests.ps1
```
Last run in the build environment: **41 passed, 0 failed (~100 s)**. They cover auth, duplicate email, throttling, hashing, authorization between users, valid/invalid/corrupt/oversized uploads, ensemble agreement/conflict/low-confidence, class-order alignment, feature-bundle loading (synthetic data), missing/corrupt models, history filters, analytics numbers, library search, consultations, crop (valid/invalid/out-of-range/missing model), fertilizer rules, weather (success, bad location, timeout, 5xx, bad JSON, bad key, both providers), unified activity and CSV export.

## What is NOT verified (please read)
* **Real model inference was not run.** The build sandbox could not download the Hugging Face weights or ImageNet weights, so tests use stand-in models. Run one real upload on your machine to confirm.
* **Grad-CAM was never run against the real network** (no PyTorch here). It hooks the last spatial feature map generically and falls back to "no explanation" on any error; if the heatmap looks wrong or is missing, tell me the traceback from the backend log.
* **SVM/RF bundles and the crop model were not trained on real datasets** — only on tiny synthetic data in tests. Their accuracy is unknown until you train them.
* Live weather calls were tested with mocked HTTP only.
* Screenshots were taken from the real app but with a **stand-in disease model, a synthetic crop model and canned weather**, so the predictions shown are not real.

## Other limitations / needs
* Stem and whole-crop diagnosis needs training data for those inputs; plant localization/cropping is not implemented.
* No reference photos are bundled in the library (none were available to use legitimately).
* Expert requests are stored locally only; real routing needs an email/CRM integration or a verified directory.
* The login throttle is in-memory (per process). Use HTTPS and set `COOKIE_SECURE=true` for deployment.
* Fertilizer guidance gives no application rates by design.
