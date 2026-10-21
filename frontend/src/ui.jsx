import React from "react";
import { Leaf, Loader2 } from "lucide-react";

export const fmtDate = (iso) => iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "-";
export const pct = (v, d = 1) => (v === null || v === undefined) ? "-" : `${(v * 100).toFixed(d)}%`;

export function PageHeader({ title, sub, actions }) {
  return (
    <div className="page-header">
      <div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Card({ title, right, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || right) && <div className="card-head"><h2>{title}</h2>{right}</div>}
      {children}
    </section>
  );
}

export function Stat({ icon: Icon, label, value, tone = "blue" }) {
  return (
    <div className={`stat tone-${tone}`}>
      <div className="stat-icon"><Icon size={20} /></div>
      <div><span>{label}</span><b>{value}</b></div>
    </div>
  );
}

export function Empty({ icon: Icon = Leaf, title, text, action }) {
  return (
    <div className="empty"><Icon size={30} /><b>{title}</b>{text && <span>{text}</span>}{action}</div>
  );
}

export function Notice({ tone = "info", children }) {
  return <div className={`notice notice-${tone}`} role={tone === "error" ? "alert" : undefined}>{children}</div>;
}

export function Spinner({ label = "Loading..." }) {
  return <div className="spinner"><Loader2 className="spin" size={20} /> {label}</div>;
}

export function Pagination({ page, pages, onPage }) {
  if (pages <= 1) return null;
  return (
    <div className="pagination">
      <button className="btn btn-light" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
      <span>Page {page} of {pages}</span>
      <button className="btn btn-light" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
    </div>
  );
}

const STATUS = {
  ok: ["Model result", "green"], uncertain: ["Uncertain", "amber"], conflict: ["Models disagree", "red"], unvalidated: ["Unvalidated input", "amber"],
};
export function StatusBadge({ status }) {
  const [text, tone] = STATUS[status] || [status, "gray"];
  return <span className={`badge badge-${tone}`}>{text}</span>;
}
export const ResultBadge = ({ healthy }) => <span className={`badge badge-${healthy ? "green" : "red"}`}>{healthy ? "Healthy" : "Disease"}</span>;

/* ---------- small SVG charts (no chart library) ---------- */
export function TrendChart({ data }) {
  if (!data.length) return <Empty title="No trend yet" text="Run a few diagnoses to see activity over time." />;
  const W = 520, H = 190, pad = 28;
  const max = Math.max(1, ...data.map(d => Math.max(d.healthy, d.diseased)));
  const x = (i) => pad + (data.length === 1 ? (W - 2 * pad) / 2 : i * (W - 2 * pad) / (data.length - 1));
  const y = (v) => H - pad - (v / max) * (H - 2 * pad);
  const line = (key) => data.map((d, i) => `${i ? "L" : "M"}${x(i)},${y(d[key])}`).join(" ");
  const step = Math.max(1, Math.ceil(data.length / 6));
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Diagnoses per day">
        {[0, 0.5, 1].map(t => <g key={t}><line x1={pad} x2={W - pad} y1={y(max * t)} y2={y(max * t)} stroke="#e4ece7" /><text x={4} y={y(max * t) + 4} fontSize="10" fill="#7c8984">{Math.round(max * t)}</text></g>)}
        <path d={line("healthy")} fill="none" stroke="#2f9e5b" strokeWidth="2.5" />
        <path d={line("diseased")} fill="none" stroke="#e5533d" strokeWidth="2.5" />
        {data.map((d, i) => <g key={d.date}><circle cx={x(i)} cy={y(d.healthy)} r="3.5" fill="#2f9e5b" /><circle cx={x(i)} cy={y(d.diseased)} r="3.5" fill="#e5533d" />
          {i % step === 0 && <text x={x(i)} y={H - 8} fontSize="10" textAnchor="middle" fill="#7c8984">{d.date.slice(5)}</text>}</g>)}
      </svg>
      <div className="legend"><i style={{ background: "#2f9e5b" }} />Healthy <i style={{ background: "#e5533d" }} />Diseased</div>
    </div>
  );
}

const PALETTE = ["#1f8a5b", "#e5533d", "#3b82c4", "#e0a526", "#8b5cc4", "#4fb3a9", "#c46a8e", "#7a8a3a"];
export function Donut({ data }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  if (!total) return <Empty title="No data yet" text="Distribution appears after your first diagnosis." />;
  const R = 54, C = 2 * Math.PI * R;
  let acc = 0;
  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 140 140" className="donut" role="img" aria-label="Disease distribution">
        <g transform="rotate(-90 70 70)">
          {data.map((d, i) => { const len = (d.count / total) * C; const el = <circle key={d.label} cx="70" cy="70" r={R} fill="none" stroke={PALETTE[i % PALETTE.length]} strokeWidth="18" strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-acc} />; acc += len; return el; })}
        </g>
        <text x="70" y="68" textAnchor="middle" fontSize="22" fontWeight="800" fill="#17352b">{total}</text>
        <text x="70" y="84" textAnchor="middle" fontSize="9" fill="#7c8984">Total</text>
      </svg>
      <ul className="legend-list">{data.slice(0, 8).map((d, i) => <li key={d.label}><i style={{ background: PALETTE[i % PALETTE.length] }} />{d.label}<b>{d.count}</b></li>)}</ul>
    </div>
  );
}

export function Bars({ rows, fmt = (v) => v, max }) {
  const m = max ?? Math.max(1, ...rows.map(r => r.value));
  return (
    <div className="bars">{rows.map(r => (
      <div className="bar-row" key={r.label}><span>{r.label}</span><div><i style={{ width: `${Math.max(2, (r.value / m) * 100)}%` }} /></div><b>{fmt(r.value)}</b></div>
    ))}</div>
  );
}
