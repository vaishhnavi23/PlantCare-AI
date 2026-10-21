import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Leaf, Search } from "lucide-react";
import { api, qs } from "../api";
import { Card, Empty, Notice, PageHeader, Spinner } from "../ui";

export default function Library() {
  const [f, setF] = useState({ q: "", crop: "", status: "" });
  const [d, setD] = useState(null);
  const [open, setOpen] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { const t = setTimeout(() => api("/library" + qs(f)).then(setD).catch(e => setErr(e.message)), 200); return () => clearTimeout(t); }, [f]);
  return (
    <>
      <PageHeader title="Disease Library" sub="Reference information about plant diseases and healthy plants" />
      <Card>
        <div className="filters"><div className="search"><Search size={17} /><input placeholder="Search disease, crop or symptom" value={f.q} onChange={e => setF({ ...f, q: e.target.value })} /></div>
          <select value={f.crop} onChange={e => setF({ ...f, crop: e.target.value })} aria-label="Crop"><option value="">All crops</option>{d?.crops.map(c => <option key={c}>{c}</option>)}</select>
          <select value={f.status} onChange={e => setF({ ...f, status: e.target.value })} aria-label="Type"><option value="">All types</option>{["Disease", "Healthy", "Pest", "Virus"].map(s => <option key={s}>{s}</option>)}</select></div>
        {d && <p className="muted small">{d.note}</p>}
        {err && <Notice tone="error">{err}</Notice>}
      </Card>
      {!d ? <Spinner /> : d.items.length === 0 ? <Card><Empty title="No matches" text="Try a different search." /></Card> : (
        <div className="lib-grid">{d.items.map(e => (
          <article className="lib-card" key={e.key}>
            <div className="lib-head"><div className="leaf-box"><Leaf size={22} /></div><div><h3>{e.title}</h3><span className="muted small">{e.crop}</span></div>
              <span className={`badge badge-${e.status === "Healthy" ? "green" : "red"}`}>{e.status}</span></div>
            <p>{e.symptoms}</p>
            <div className="chips">{e.detectable === true && <span className="chip chip-on">Detectable by current model</span>}{e.detectable === false && <span className="chip">Reference only</span>}{e.high_concern && <span className="chip chip-warn">Can spread fast / no cure</span>}</div>
            <button className="btn btn-light btn-sm" onClick={() => setOpen(open === e.key ? null : e.key)}>{open === e.key ? "Hide details" : "View details"}</button>
            {open === e.key && <dl className="info"><dt>Symptoms</dt><dd>{e.symptoms}</dd><dt>Causes</dt><dd>{e.causes}</dd><dt>Favouring conditions</dt><dd>{e.risk_factors}</dd><dt>Prevention</dt><dd>{e.prevention}</dd><dt>Management</dt><dd>{e.treatment}</dd>
              {!e.has_specific_guide && <dd className="muted small">Specific guidance for this class is not in the project's reference data.</dd>}</dl>}
          </article>))}</div>)}
      <p className="muted small">Want to check a plant? <Link to="/diagnose">Run a diagnosis</Link>. The library is general information and does not change what the model can detect.</p>
    </>
  );
}
