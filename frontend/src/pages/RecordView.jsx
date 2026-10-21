import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Printer, Trash2 } from "lucide-react";
import { api } from "../api";
import { Bars, Card, Notice, PageHeader, Spinner, fmtDate, pct } from "../ui";
import { FertResult } from "./Fertilizer";

export default function RecordView() {
  const { id } = useParams();
  const nav = useNavigate();
  const [r, setR] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api(`/recommendations/${id}`).then(setR).catch(e => setErr(e.message)); }, [id]);
  if (err) return <Notice tone="error">{err} <Link to="/history">Back to history</Link></Notice>;
  if (!r) return <Spinner />;
  const o = r.output;
  async function remove() { if (window.confirm("Delete this record?")) { await api(`/recommendations/${r.id}`, { method: "DELETE" }); nav("/history"); } }
  return (
    <>
      <div className="back no-print"><Link to="/history"><ArrowLeft size={16} /> Prediction History</Link></div>
      <PageHeader title={r.type === "crop" ? "Crop recommendation" : "Fertilizer guidance"} sub={`${fmtDate(r.created_at)} - ${r.model_info}`}
        actions={<><button className="btn btn-light no-print" onClick={() => window.print()}><Printer size={15} /> Print summary</button><button className="btn btn-danger no-print" onClick={remove}><Trash2 size={15} /> Delete</button></>} />
      {r.type === "crop" ? (
        <Card title={`Recommended crop: ${o.recommended}`}>
          <Bars rows={[{ label: o.recommended, value: 1 }, ...o.alternatives.map(a => ({ label: a.crop, value: a.probability }))].slice(1)} fmt={x => pct(x, 0)} max={1} />
          <h4>Inputs</h4><table className="mini"><tbody>{o.factors.map(f => <tr key={f.feature}><td>{f.label}</td><td>{f.value} {f.unit}</td><td>{f.importance == null ? "-" : `${pct(f.importance, 0)} overall importance`}</td></tr>)}</tbody></table>
          {o.warnings.map((w, i) => <Notice key={i} tone="warn">{w}</Notice>)}<p className="muted small">{o.note}</p>
        </Card>
      ) : <Card title={`Guidance for ${o.crop}`}><FertResult res={o} /></Card>}
    </>
  );
}
