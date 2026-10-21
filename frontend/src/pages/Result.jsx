import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, CheckCircle2, Printer, Trash2, UserCheck } from "lucide-react";
import { api } from "../api";
import { Card, Notice, ResultBadge, Spinner, StatusBadge, fmtDate, pct } from "../ui";

const PART = { leaf: "Leaf", stem: "Stem", whole_plant: "Whole crop" };
const LEVEL = { urgent: ["Urgent: consult an expert", "red"], recommended: ["Expert consultation recommended", "amber"], optional: ["Expert check optional", "green"] };

export default function Result() {
  const { id } = useParams();
  const nav = useNavigate();
  const [r, setR] = useState(null);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState("image");
  useEffect(() => { api(`/predictions/${id}`).then(setR).catch(e => setErr(e.message)); }, [id]);
  if (err) return <Notice tone="error">{err} <Link to="/history">Back to history</Link></Notice>;
  if (!r) return <Spinner />;
  const info = r.disease_info;
  const [lvlText, lvlTone] = LEVEL[r.expert.level];
  async function remove() {
    if (!window.confirm("Delete this diagnosis and its image?")) return;
    await api(`/predictions/${r.id}`, { method: "DELETE" }); nav("/history");
  }
  return (
    <>
      <div className="back no-print"><Link to="/diagnose"><ArrowLeft size={16} /> Detection Result</Link></div>
      <div className="grid-2 wide-left">
        <Card>
          <div className="img-tabs no-print">
            <button className={tab === "image" ? "on" : ""} onClick={() => setTab("image")}>Your image</button>
            {r.has_heatmap && <button className={tab === "heat" ? "on" : ""} onClick={() => setTab("heat")}>Grad-CAM heatmap</button>}
          </div>
          <img className="result-img" src={tab === "heat" && r.has_heatmap ? r.heatmap_url : r.image_url} alt={tab === "heat" ? "Grad-CAM heatmap" : "Uploaded plant"} />
          <p className="muted small">{r.original_name} - {fmtDate(r.created_at)}</p>
        </Card>
        <div className="stack">
          <Card className={`verdict ${r.is_healthy ? "ok" : "bad"}`}>
            <div className="verdict-top"><ResultBadge healthy={r.is_healthy} /><StatusBadge status={r.status} /></div>
            <h2 className="verdict-title">{r.title}</h2>
            <dl className="facts">
              <div><dt>Model confidence</dt><dd><b className="conf">{pct(r.confidence)}</b>{r.plant_part !== "leaf" && <span className="muted small"> (unvalidated for {PART[r.plant_part].toLowerCase()})</span>}</dd></div>
              <div><dt>Detected plant part</dt><dd>{PART[r.plant_part]}</dd></div>
              <div><dt>Models used</dt><dd>{r.models_used.join(", ")}</dd></div>
              {r.agreement !== null && r.members.length > 1 && <div><dt>Model agreement</dt><dd>{Math.round(r.agreement * r.members.length)} of {r.members.length}</dd></div>}
            </dl>
            {r.plant_part !== "leaf" ? (
              <p className="muted small"><b>Limitation notice:</b> This model was trained exclusively on single-leaf photos. It has not been validated for stem or whole-crop photos, and this score does not represent verified real-world accuracy for non-leaf parts.</p>
            ) : (
              <p className="muted small">Confidence is the model's own probability score. It is not a guarantee of diagnostic certainty and is not calibrated against real-world accuracy.</p>
            )}
          </Card>
          {r.reasons.length > 0 && <Notice tone="warn"><b><AlertTriangle size={15} /> Please note</b><ul>{r.reasons.map((x, i) => <li key={i}>{x}</li>)}</ul>
            {r.status !== "ok" && <p>If you can, upload a clearer, closer photo of the plant or ask an agricultural expert.</p>}</Notice>}
          {r.failed_members.length > 0 && <Notice tone="warn">Some models could not run: {r.failed_members.join("; ")}</Notice>}
          <div className={`expert expert-${lvlTone}`}>
            <UserCheck size={26} /><div><b>{lvlText}</b><p>{r.expert.reason}</p>
              <p className="small">Summary to share: {r.title}, {pct(r.confidence, 0)} model confidence, {PART[r.plant_part].toLowerCase()} photo{r.reasons.length ? ", with the caveats listed above" : ""}. This is an AI prediction, not a confirmed professional diagnosis.</p></div>
            <Link className="btn btn-primary no-print" to={`/experts?prediction=${r.id}`}>Find Expert</Link>
          </div>
        </div>
      </div>

      <div className="grid-2">
        <Card title={`About ${r.title} (reference information)`}>
          <p className="muted small">General knowledge about this class, not something detected in your image.</p>
          <dl className="info">
            <dt>Typical symptoms</dt><dd>{info.symptoms}</dd>
            <dt>Causes</dt><dd>{info.causes}</dd>
            <dt>Favouring conditions</dt><dd>{info.risk_factors}</dd>
          </dl>
        </Card>
        <Card title="Recommended next steps">
          <dl className="info">
            <dt>Management</dt><dd>{info.treatment}</dd>
            <dt>Chemical control (educational)</dt><dd>{info.pesticide}</dd>
            <dt>Prevention and care</dt><dd>{info.prevention}</dd>
          </dl>
          <p className="muted small">No application rates are given. Always follow the product label and local agricultural advice.</p>
        </Card>
      </div>

      <Card title="Why this prediction?">
        <div className="grid-2">
          <div>
            <h4>What each model said (actual outputs)</h4>
            <table className="mini"><thead><tr><th>Model</th><th>Its top class</th><th>Probability</th></tr></thead>
              <tbody>{r.members.map(m => <tr key={m.name}><td>{m.name}</td><td>{m.label.replaceAll("___", " - ").replaceAll("_", " ")}</td><td>{pct(m.probability)}</td></tr>)}</tbody></table>
            <h4>Combined top candidates</h4>
            <table className="mini"><tbody>{r.top.map(t => <tr key={t.label}><td>{t.title}</td><td>{pct(t.probability)}</td></tr>)}</tbody></table>
            <p className="muted small">Combined result = average of the listed models' probabilities. No per-model "contribution" percentages are shown because none are computed.</p>
          </div>
          <div>
            <h4>Image regions</h4>
            {r.has_heatmap ? <><button className="btn btn-light no-print" onClick={() => setTab("heat")}>Show Grad-CAM heatmap</button><p className="muted small">{r.heatmap_note}</p></>
              : <p className="muted small">No visual explanation is available for this result. Grad-CAM works only with the end-to-end ResNet50 network; it cannot explain SVM / Random Forest models, and it was not available for this run.</p>}
            {r.quality && <p className="muted small">Image checks (preliminary): {r.quality.width}x{r.quality.height}px, sharpness {r.quality.sharpness}, plant-like colour {Math.round(r.quality.plant_color_ratio * 100)}%.</p>}
          </div>
        </div>
      </Card>

      <div className="row-actions no-print">
        <span className="saved"><CheckCircle2 size={16} /> Saved to your history</span>
        <Link className="btn btn-light" to="/history">View history</Link>
        <Link className="btn btn-primary" to="/diagnose">Run another diagnosis</Link>
        <button className="btn btn-light" onClick={() => window.print()}><Printer size={15} /> Print summary</button>
        <button className="btn btn-danger" onClick={remove}><Trash2 size={15} /> Delete</button>
      </div>
    </>
  );
}
