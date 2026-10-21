import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Download, Search, Trash2 } from "lucide-react";
import { api, qs } from "../api";
import { Card, Empty, Notice, PageHeader, Pagination, Spinner, fmtDate } from "../ui";

const TABS = [["", "All activity"], ["disease", "Disease diagnoses"], ["crop", "Crop recommendations"], ["fertilizer", "Fertilizer guidance"]];
const LABEL = { disease: "Disease", crop: "Crop", fertilizer: "Fertilizer" };

export default function HistoryPage() {
  const [f, setF] = useState({ type: "", q: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => { api("/activity" + qs({ ...f, page, page_size: 10 })).then(setD).catch(e => setErr(e.message)); }, [f, page]);
  useEffect(() => { load(); }, [load]);
  const upd = (k, v) => { setF({ ...f, [k]: v }); setPage(1); };
  async function remove(a) {
    if (!window.confirm("Delete this record?")) return;
    await api(a.type === "disease" ? `/predictions/${a.id}` : `/recommendations/${a.id}`, { method: "DELETE" }); load();
  }
  return (
    <>
      <PageHeader title="Prediction History" sub="Your diagnoses and recommendations, newest first"
        actions={<a className="btn btn-light" href={"/api/activity/export.csv" + qs({ type: f.type, date_from: f.date_from, date_to: f.date_to })}><Download size={15} /> Export CSV</a>} />
      <Card>
        <div className="tabs-row">{TABS.map(([k, t]) => <button key={k} className={f.type === k ? "on" : ""} onClick={() => upd("type", k)}>{t}</button>)}</div>
        <div className="filters"><div className="search"><Search size={17} /><input placeholder="Search results" value={f.q} onChange={e => upd("q", e.target.value)} /></div>
          <label className="inline-label">From<input type="date" value={f.date_from} onChange={e => upd("date_from", e.target.value)} /></label>
          <label className="inline-label">To<input type="date" value={f.date_to} onChange={e => upd("date_to", e.target.value)} /></label></div>
        {err && <Notice tone="error">{err}</Notice>}
        {!d ? <Spinner /> : d.items.length === 0 ? <Empty title="No records found" text="Run a diagnosis or recommendation, or adjust your filters." action={<Link className="btn btn-primary" to="/diagnose">Diagnose a plant</Link>} /> : (
          <div className="table-wrap"><table><thead><tr><th>Date &amp; time</th><th>Type</th><th>Result</th><th>Details</th><th>Action</th></tr></thead><tbody>
            {d.items.map(a => (
              <tr key={a.type + a.id}><td>{fmtDate(a.created_at)}</td><td><span className={`pill pill-${a.type}`}>{LABEL[a.type]}</span></td>
                <td className="with-thumb">{a.thumb && <img src={a.thumb} alt="" />}<span>{a.summary}</span></td><td className="muted">{a.detail}</td>
                <td className="actions"><Link className="btn btn-sm btn-primary" to={a.type === "disease" ? `/diagnosis/${a.id}` : `/record/${a.id}`}>View</Link>
                  <button className="icon-btn" aria-label="Delete record" onClick={() => remove(a)}><Trash2 size={16} /></button></td></tr>))}</tbody></table></div>)}
        {d && <Pagination page={d.page} pages={d.pages} onPage={setPage} />}
      </Card>
    </>
  );
}
