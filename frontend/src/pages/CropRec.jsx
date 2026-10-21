import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CloudSun } from "lucide-react";
import { api } from "../api";
import { Bars, Card, Notice, PageHeader, Spinner, pct } from "../ui";

const FIELDS = [["N", "Nitrogen (N)"], ["P", "Phosphorus (P)"], ["K", "Potassium (K)"], ["ph", "Soil pH"], ["temperature", "Temperature"], ["humidity", "Humidity"], ["rainfall", "Rainfall"]];
const blank = Object.fromEntries(FIELDS.map(([k]) => [k, ""]));

export default function CropRec() {
  const [info, setInfo] = useState(null);
  const [v, setV] = useState(blank);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [loc, setLoc] = useState("");
  const [wmsg, setWmsg] = useState("");
  useEffect(() => { api("/crop/info").then(setInfo).catch(e => setErr(e.message)); }, []);
  if (!info) return err ? <Notice tone="error">{err}</Notice> : <Spinner />;

  function check() {
    for (const [k, label] of FIELDS) {
      if (v[k] === "") return `${label} is required.`;
      const n = Number(v[k]); const [lo, hi] = info.limits[k];
      if (!Number.isFinite(n) || n < lo || n > hi) return `${label} must be between ${lo} and ${hi} (${info.units[k]}).`;
    }
    return "";
  }
  async function submit(e) {
    e.preventDefault(); setRes(null);
    const m = check(); if (m) return setErr(m);
    setErr(""); setBusy(true);
    try { setRes(await api("/crop/recommend", { method: "POST", json: Object.fromEntries(FIELDS.map(([k]) => [k, Number(v[k])])) })); }
    catch (ex) { setErr(ex.message); } finally { setBusy(false); }
  }
  async function fillWeather() {
    setWmsg("");
    try {
      const w = await api(`/weather?location=${encodeURIComponent(loc)}`);
      const c = w.current;
      setV(x => ({ ...x, temperature: c.temperature_c ?? x.temperature, humidity: c.humidity_pct ?? x.humidity }));
      setWmsg(`Filled temperature and humidity from ${w.location.name} (${w.provider}, observed ${w.observed_at || "n/a"}). Rainfall is left for you: the model expects seasonal rainfall in mm, which a current reading is not.`);
    } catch (ex) { setWmsg(ex.message); }
  }
  const m = info.metrics;
  return (
    <>
      <PageHeader title="Crop Recommendation" sub="Suggest suitable crops from soil nutrients, pH and climate using a trained machine-learning model" />
      {!info.available && <Notice tone="warn"><b>Crop model not trained yet.</b> {info.error} Nothing is guessed in the meantime. See the README section "Train the crop model".</Notice>}
      <div className="grid-2 wide-left">
        <Card title="Soil and climate inputs">
          <form onSubmit={submit} noValidate>
            <div className="form-grid">{FIELDS.map(([k, label]) => (
              <label key={k}>{label} <small>({info.units[k]})</small>
                <input type="number" step="any" inputMode="decimal" value={v[k]} onChange={e => setV({ ...v, [k]: e.target.value })}
                  placeholder={info.ranges ? `${info.ranges[k][0].toFixed(1)} - ${info.ranges[k][1].toFixed(1)}` : ""} /></label>))}</div>
            <details className="weather-fill"><summary><CloudSun size={15} /> Optional: fill temperature and humidity from weather</summary>
              <div className="inline"><input placeholder="City, e.g. Davangere" value={loc} onChange={e => setLoc(e.target.value)} /><button type="button" className="btn btn-light" onClick={fillWeather} disabled={!loc.trim()}>Fetch</button></div>
              {wmsg && <p className="muted small">{wmsg}</p>}</details>
            {err && <Notice tone="error">{err}</Notice>}
            <button className="btn btn-primary wide" disabled={busy || !info.available}>{busy ? "Analysing..." : "Recommend crop"}</button>
          </form>
        </Card>
        <Card title="Supported inputs and model">
          <table className="mini"><thead><tr><th>Input</th><th>Allowed</th><th>Training data range</th></tr></thead><tbody>
            {FIELDS.map(([k, l]) => <tr key={k}><td>{l}</td><td>{info.limits[k][0]}-{info.limits[k][1]}</td><td>{info.ranges ? `${info.ranges[k][0].toFixed(1)}-${info.ranges[k][1].toFixed(1)}` : "-"}</td></tr>)}</tbody></table>
          {info.dataset && <p className="muted small"><b>Dataset:</b> {info.dataset.source}, {info.dataset.rows} rows, {info.dataset.classes} crops. {info.dataset.limitations}</p>}
          {m && <p className="muted small"><b>Offline evaluation:</b> hold-out accuracy {pct(m.holdout_accuracy)}, macro-F1 {pct(m.holdout_macro_f1)} ({m.n_test} test rows). {m.scope}</p>}
          <p className="muted small">This model is separate from the plant-disease classifier. It does not consider soil type, season, variety, market or local regulations.</p>
        </Card>
      </div>
      {res && (
        <Card title="Recommendation">
          <div className="crop-result"><div className="big-crop"><span>Recommended crop</span><b>{res.recommended}</b></div>
            <div><h4>Alternatives</h4><Bars rows={res.alternatives.map(a => ({ label: a.crop, value: a.probability }))} fmt={x => pct(x, 0)} max={1} /></div></div>
          {res.warnings.map((w, i) => <Notice key={i} tone="warn">{w}</Notice>)}
          <h4>Inputs considered</h4>
          <table className="mini"><thead><tr><th>Factor</th><th>Your value</th><th>Overall importance in the model</th></tr></thead><tbody>
            {res.factors.map(f => <tr key={f.feature}><td>{f.label}</td><td>{f.value} {f.unit}</td><td>{f.importance == null ? "-" : pct(f.importance, 0)}</td></tr>)}</tbody></table>
          <p className="muted small">{res.note} Saved to your <Link to="/history">history</Link>. Model scores are not yield guarantees - confirm with local agricultural advice.</p>
        </Card>)}
    </>
  );
}
