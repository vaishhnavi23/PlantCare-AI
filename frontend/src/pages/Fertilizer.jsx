import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, FlaskConical, HelpCircle, Info, Sprout } from "lucide-react";
import { api } from "../api";
import { Card, Notice, PageHeader } from "../ui";

const CROP_SUGGESTIONS = [
  "Rice", "Wheat", "Maize", "Sugarcane", "Cotton", "Chickpea", "Soybean", "Groundnut",
  "Tomato", "Potato", "Apple", "Banana", "Mango", "Grapes", "Pears", "Papaya",
  "Pineapple", "Coconut", "Onion", "Chili", "Peas", "Beans", "Cabbage", "Cauliflower",
  "Cucumber", "Mustard", "Barley"
];

const LEVELS = [
  ["", "Not measured"],
  ["low", "Low"],
  ["medium", "Medium"],
  ["high", "High"]
];

const GROWTH_STAGES = [
  ["", "Any / Not specified"],
  ["planting", "Basal / Planting / Pre-sowing"],
  ["vegetative", "Vegetative / Active Growth / Tillering"],
  ["flowering", "Flowering / Fruit Set / Panicle Initiation"],
  ["fruiting", "Fruiting / Bulking / Grain Filling"],
  ["maturity", "Ripening / Pre-harvest / Post-harvest"]
];

export function FertResult({ res }) {
  if (res.data_available === false) {
    return (
      <>
        <Notice tone="warn">
          <b>Agronomic nutrient data unavailable for "{res.crop}"</b>
          <p>
            PlantCare AI does not fabricate crop nutrient values or fertilizer amounts when reliable
            agronomic data is unavailable.
          </p>
        </Notice>
        {res.notes && res.notes.map((n, i) => <Notice key={i}>{n}</Notice>)}
        {res.general_advice && (
          <Card title="Recommended General Practices">
            <ul className="checks">
              {res.general_advice.map((adv, idx) => (
                <li key={idx}>{adv}</li>
              ))}
            </ul>
          </Card>
        )}
        <Notice tone="warn">
          <b>Safe use.</b> {res.safety}
        </Notice>
      </>
    );
  }

  const isPersonalized = Boolean(res.has_soil_test);

  return (
    <>
      <div className="badge-row" style={{ marginBottom: "10px" }}>
        {isPersonalized ? (
          <span className="badge badge-green">Personalized with Soil Test</span>
        ) : (
          <span className="badge badge-amber">General Crop Recommendation (No Soil Test)</span>
        )}
      </div>

      <Notice tone={isPersonalized ? "info" : "warn"}>
        {res.method}
      </Notice>

      {res.nutrients && res.nutrients.length > 0 && (
        <div className="nutrients">
          {res.nutrients.map(n => (
            <div key={n.nutrient} className={`nutrient lvl-${(n.level || "general").replace(/\s+/g, "-")}`}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <b>{n.nutrient}</b>
                <span className="badge">{n.demand ? `${n.demand} Need` : n.level}</span>
              </div>
              <p>{n.finding}</p>
              {n.options && n.options.length > 0 && (
                <>
                  <p className="small muted" style={{ marginTop: "8px", fontWeight: "600" }}>Suitable fertilizer sources:</p>
                  <ul>
                    {n.options.map((o, i) => (
                      <li key={i}>{o}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {res.ph && (
        <div className="nutrient" style={{ marginTop: "12px" }}>
          <b>
            Soil pH {res.ph.value !== null && res.ph.value !== undefined ? res.ph.value : `(Preferred: ${res.ph.optimal_range})`}
          </b>
          <p>{res.ph.finding}</p>
          {res.ph.option && <p>{res.ph.option}</p>}
          {res.ph.caveat && <p className="muted small">{res.ph.caveat}</p>}
        </div>
      )}

      {res.notes && res.notes.map((n, i) => <Notice key={i}>{n}</Notice>)}

      {res.fertilizer_distinction_note && (
        <Notice tone="info">
          <b>Important distinction:</b> {res.fertilizer_distinction_note}
        </Notice>
      )}

      <Notice tone="warn">
        <b>Safe use.</b> {res.safety} No commercial application rates are produced because they require field-specific calibration, soil-test methods, variety, and yield targets.
      </Notice>
    </>
  );
}

export default function Fertilizer() {
  const [f, setF] = useState({
    crop: "",
    n_level: "",
    p_level: "",
    k_level: "",
    ph: "",
    growth_stage: "",
    location: ""
  });
  const [hasSoilTest, setHasSoilTest] = useState(false);
  const [hasContext, setHasContext] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const set = k => e => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setRes(null);

    if (!f.crop.trim()) {
      return setErr("Please enter the crop being cultivated.");
    }
    if (f.ph !== "" && (Number(f.ph) < 0 || Number(f.ph) > 14)) {
      return setErr("Soil pH must be between 0 and 14.");
    }

    setBusy(true);
    try {
      const payload = {
        crop: f.crop.trim(),
        n_level: f.n_level || null,
        p_level: f.p_level || null,
        k_level: f.k_level || null,
        ph: f.ph === "" ? null : Number(f.ph),
        growth_stage: f.growth_stage || null,
        location: f.location.trim() || null
      };
      const result = await api("/fertilizer/recommend", {
        method: "POST",
        json: payload
      });
      setRes(result);
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Fertilizer Recommendation"
        sub="Crop-specific nutrient guidance and suitable fertilizer options"
      />
      <div className="grid-2 wide-left">
        <Card title="Crop & Soil Information">
          <form onSubmit={submit} noValidate>
            <label>
              Plant or crop name <small>(any crop accepted)</small>
              <input
                list="crop-suggestions"
                value={f.crop}
                onChange={set("crop")}
                maxLength={100}
                placeholder="e.g. Grapes, Pears, Rice, Tomato, Wheat"
                required
              />
              <datalist id="crop-suggestions">
                {CROP_SUGGESTIONS.map(c => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </label>

            <details
              className="soil-test-details"
              open={hasSoilTest}
              onToggle={e => setHasSoilTest(e.currentTarget.open)}
              style={{
                border: "1px solid var(--line)",
                borderRadius: "10px",
                padding: "10px 14px",
                marginBottom: "12px",
                background: "#fafcfb"
              }}
            >
              <summary
                style={{
                  cursor: "pointer",
                  fontWeight: "600",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  color: "var(--ink)"
                }}
              >
                <FlaskConical size={16} color="var(--green)" />
                <span>I have a soil test (optional)</span>
              </summary>
              <div style={{ marginTop: "12px" }}>
                <p className="small muted" style={{ marginTop: "0", marginBottom: "10px" }}>
                  Enter categories from your laboratory soil-test report to personalize the recommendation. Unmeasured nutrients will not be assumed.
                </p>
                <div className="form-grid three">
                  {[
                    ["n_level", "Nitrogen (N) level"],
                    ["p_level", "Phosphorus (P) level"],
                    ["k_level", "Potassium (K) level"]
                  ].map(([k, l]) => (
                    <label key={k}>
                      {l}
                      <select value={f[k]} onChange={set(k)}>
                        {LEVELS.map(([v, t]) => (
                          <option key={v} value={v}>
                            {t}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
                <label>
                  Soil pH <small>(0-14, optional)</small>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="14"
                    value={f.ph}
                    onChange={set("ph")}
                    placeholder="e.g. 6.5"
                  />
                </label>
              </div>
            </details>

            <details
              className="context-details"
              open={hasContext}
              onToggle={e => setHasContext(e.currentTarget.open)}
              style={{
                border: "1px solid var(--line)",
                borderRadius: "10px",
                padding: "10px 14px",
                marginBottom: "14px",
                background: "#fafcfb"
              }}
            >
              <summary
                style={{
                  cursor: "pointer",
                  fontWeight: "600",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  color: "var(--ink)"
                }}
              >
                <Sprout size={16} color="var(--green)" />
                <span>Growth stage & location (optional)</span>
              </summary>
              <div style={{ marginTop: "12px" }}>
                <div className="form-grid">
                  <label>
                    Growth stage <small>(optional)</small>
                    <select value={f.growth_stage} onChange={set("growth_stage")}>
                      {GROWTH_STAGES.map(([v, t]) => (
                        <option key={v} value={v}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Location / District <small>(optional)</small>
                    <input
                      type="text"
                      value={f.location}
                      onChange={set("location")}
                      maxLength={100}
                      placeholder="e.g. Nashik, Davangere"
                    />
                  </label>
                </div>
              </div>
            </details>

            {!hasSoilTest && (
              <p className="small muted" style={{ marginBottom: "12px" }}>
                <Info size={13} style={{ verticalAlign: "middle", marginRight: "4px" }} />
                No soil test? Enter your crop name above to get general agronomic nutrient guidance.
              </p>
            )}

            {err && <Notice tone="error">{err}</Notice>}

            <button className="btn btn-primary wide" disabled={busy}>
              {busy ? "Analyzing crop guidance..." : "Get guidance"}
            </button>
          </form>
        </Card>

        <Card title="How this works">
          <p className="long">
            <b>Crop-first guidance:</b> Enter your crop name to see crop-specific nutrient demand profiles and suitable mineral and organic fertilizer options based on FAO and ICAR agronomic research.
          </p>
          <p className="long">
            <b>Optional soil test:</b> If you have a laboratory report, expand "I have a soil test" to input Low, Medium, or High levels. Unmeasured nutrients are never assumed.
          </p>
          <p className="long">
            <b>No synthetic rates:</b> This tool does not invent kg/ha or application quantities, because precise fertilizer doses require laboratory soil calibration, variety, and yield targets. Always consult your local agricultural extension service.
          </p>
        </Card>
      </div>

      {res && (
        <Card title={`Guidance for ${res.crop}`}>
          <FertResult res={res} />
          <p className="muted small" style={{ marginTop: "16px" }}>
            Saved to your <Link to="/history">history</Link>.
          </p>
        </Card>
      )}
    </>
  );
}
