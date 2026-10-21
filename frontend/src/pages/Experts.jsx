import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Mail, Phone, Globe } from "lucide-react";
import { api } from "../api";
import { Card, Notice, PageHeader, fmtDate } from "../ui";
import { useAuth } from "../App";

export default function Experts() {
  const { user } = useAuth();
  const [sp] = useSearchParams();
  const pid = sp.get("prediction");
  const [dir, setDir] = useState(null);
  const [mine, setMine] = useState([]);
  const [f, setF] = useState({ name: user.name, contact: user.email, urgency: "normal", message: "" });
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const loadMine = () => api("/consultations").then(d => setMine(d.items)).catch(() => {});
  useEffect(() => { api("/experts").then(setDir).catch(() => setDir({ items: [], configured: false })); loadMine(); }, []);
  useEffect(() => {
    if (!pid) return;
    api(`/predictions/${pid}`).then(r => setF(x => ({ ...x, urgency: r.expert.level === "urgent" ? "urgent" : "normal",
      message: `Diagnosis summary: ${r.title}; model confidence ${(r.confidence * 100).toFixed(0)}%; ${r.plant_part.replace("_", " ")} photo. ${r.reasons[0] || ""}\n\nMy question: ` }))).catch(() => {});
  }, [pid]);
  async function submit(e) {
    e.preventDefault(); setMsg(null);
    if (f.message.trim().length < 5) return setMsg({ tone: "error", text: "Please describe your question (at least 5 characters)." });
    setBusy(true);
    try { const r = await api("/consultations", { method: "POST", json: { ...f, prediction_id: pid ? Number(pid) : null } }); setMsg({ tone: "info", text: r.message }); loadMine(); }
    catch (ex) { setMsg({ tone: "error", text: ex.message }); } finally { setBusy(false); }
  }
  return (
    <>
      <PageHeader title="Expert Assistance" sub="Get a human expert to confirm AI results and advise on treatment" />
      <div className="grid-2">
        <Card title="Consult an expert">
          <Notice>This form saves your request inside PlantCare AI. <b>It is not sent to anyone automatically</b> - no expert is booked. Use a contact below or your local agricultural office, and share the summary.</Notice>
          <form onSubmit={submit} noValidate>
            <label>Your name<input value={f.name} onChange={e => setF({ ...f, name: e.target.value })} maxLength={80} /></label>
            <label>Email or phone for follow-up<input value={f.contact} onChange={e => setF({ ...f, contact: e.target.value })} maxLength={200} /></label>
            <label>Urgency<select value={f.urgency} onChange={e => setF({ ...f, urgency: e.target.value })}><option value="normal">Normal</option><option value="urgent">Urgent - spreading quickly</option></select></label>
            <label>Describe the problem<textarea rows={6} value={f.message} onChange={e => setF({ ...f, message: e.target.value })} maxLength={2000} /></label>
            {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
            <button className="btn btn-primary wide" disabled={busy}>{busy ? "Saving..." : "Save consultation request"}</button>
          </form>
        </Card>
        <div className="stack">
          <Card title="Expert contacts">
            {dir?.configured ? dir.items.map(e => (
              <div className="expert-card" key={e.name}><b>{e.name}</b><span className="muted small">{[e.organisation, e.specialty, e.region].filter(Boolean).join(" - ")}</span>
                <div className="links">{e.email && <a href={`mailto:${e.email}`}><Mail size={14} /> {e.email}</a>}{e.phone && <a href={`tel:${e.phone}`}><Phone size={14} /> {e.phone}</a>}{e.url && /^https?:\/\//.test(e.url) && <a href={e.url} target="_blank" rel="noreferrer noopener"><Globe size={14} /> Website</a>}</div></div>
            )) : <p className="muted">No expert directory is configured, so none are listed. An administrator can add verified contacts in <code>backend/data/experts.json</code> (see README). Meanwhile, contact your local agricultural extension office (in India, your nearest Krishi Vigyan Kendra) or a plant pathologist.</p>}
          </Card>
          <Card title="If the problem is spreading">
            <ul className="checks"><li>Separate or mark affected plants and avoid moving plant material between fields.</li><li>Clean tools and hands after handling affected plants.</li><li>Take clear photos of leaves, stems and the whole plant, and note when symptoms started and recent weather.</li><li>Do not choose a pesticide from an AI prediction alone; ask an expert for a registered product.</li></ul>
          </Card>
        </div>
      </div>
      <Card title="Your saved requests">{mine.length === 0 ? <p className="muted">None yet.</p> : (
        <div className="table-wrap"><table><thead><tr><th>Date</th><th>Urgency</th><th>Message</th><th>Status</th></tr></thead><tbody>{mine.map(c => <tr key={c.id}><td>{fmtDate(c.created_at)}</td><td>{c.urgency}</td><td className="clip">{c.message}</td><td>Saved locally</td></tr>)}</tbody></table></div>)}</Card>
    </>
  );
}
