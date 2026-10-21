import React, { useEffect, useState } from "react";
import { Activity, Bug, Leaf, Target } from "lucide-react";
import { api, qs } from "../api";
import { Bars, Card, Donut, Notice, PageHeader, Spinner, Stat, TrendChart, pct } from "../ui";

export default function Analytics() {
  const [f, setF] = useState({ date_from: "", date_to: "", disease: "" });
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api("/analytics" + qs(f)).then(setD).catch(e => setErr(e.message)); }, [f]);
  if (err) return <Notice tone="error">{err}</Notice>;
  if (!d) return <Spinner />;
  const ev = d.model_evaluation;
  return (
    <>
      <PageHeader title="Analytics" sub="Calculated from your own stored diagnoses" />
      <Card><div className="filters">
        <label className="inline-label">From<input type="date" value={f.date_from} onChange={e => setF({ ...f, date_from: e.target.value })} /></label>
        <label className="inline-label">To<input type="date" value={f.date_to} onChange={e => setF({ ...f, date_to: e.target.value })} /></label>
        <select value={f.disease} onChange={e => setF({ ...f, disease: e.target.value })} aria-label="Disease filter"><option value="">All results</option>{d.available_labels.map(l => <option key={l.label} value={l.label}>{l.title}</option>)}</select></div></Card>
      <div className="stats four">
        <Stat icon={Activity} label="Total diagnoses" value={d.total} tone="blue" /><Stat icon={Leaf} label="Healthy" value={d.healthy} tone="green" />
        <Stat icon={Bug} label="Diseased" value={d.diseased} tone="red" /><Stat icon={Target} label="Avg. model confidence" value={pct(d.avg_confidence)} tone="blue" />
      </div>
      <div className="grid-2">
        <Card title="Disease distribution"><Donut data={d.distribution} /></Card>
        <Card title="Prediction trend"><TrendChart data={d.trend} /></Card>
        <Card title="Model confidence distribution">{d.total ? <Bars rows={d.confidence_buckets.filter(b => b.count).map(b => ({ label: b.range, value: b.count }))} /> : <p className="muted">No data in this range.</p>}
          <p className="muted small">Confidence is each model's own probability, not verified accuracy.</p></Card>
        <Card title="Result reliability">{d.total ? <Bars rows={Object.entries(d.status_counts).map(([k, v]) => ({ label: { ok: "Model result", uncertain: "Uncertain", conflict: "Models disagree", unvalidated: "Unvalidated input" }[k] || k, value: v }))} /> : <p className="muted">No data in this range.</p>}</Card>
      </div>
      <Card title="Model comparison (offline test results)">
        {ev ? <><Bars rows={ev.models.map(m => ({ label: m.name, value: m.accuracy }))} fmt={x => pct(x, 1)} max={1} />
          <p className="muted small">Dataset: {ev.dataset}, {ev.classes} classes, trained {ev.trained_on}. {ev.scope}</p></>
          : <p className="muted">No evaluation results are available, so no model comparison is shown. Running <code>scripts/train_feature_classifiers.py</code> creates <code>models/evaluation.json</code> with real hold-out metrics.</p>}
        {d.model_usage.length > 0 && <><h4>Models used in your diagnoses</h4><Bars rows={d.model_usage.map(m => ({ label: m.model, value: m.count }))} /></>}
      </Card>
    </>
  );
}
