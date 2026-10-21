import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, BookOpen, Camera, CloudSun, FlaskConical, HeartPulse, Leaf, Sprout, Target, UserCheck, Bug } from "lucide-react";
import { api } from "../api";
import { Card, Donut, Empty, Notice, PageHeader, Spinner, Stat, TrendChart, fmtDate, pct } from "../ui";
import { useAuth } from "../App";

const ACTIONS = [
  ["/diagnose", "Diagnose a plant", "Upload a leaf, stem or crop photo", Camera], ["/crop", "Recommend a crop", "From soil and climate inputs", Sprout],
  ["/fertilizer", "Fertilizer guidance", "From your soil-test results", FlaskConical], ["/weather", "View weather", "Current and 5-day outlook", CloudSun],
  ["/library", "Disease information", "Symptoms, causes, prevention", BookOpen], ["/experts", "Consult an expert", "Send a consultation request", UserCheck],
];
const TYPE = { disease: "Disease diagnosis", crop: "Crop recommendation", fertilizer: "Fertilizer guidance" };

export default function Dashboard() {
  const { user } = useAuth();
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api("/dashboard").then(setD).catch(e => setErr(e.message)); }, []);
  if (err) return <Notice tone="error">{err}</Notice>;
  if (!d) return <Spinner />;
  const empty = d.total + d.crop_count + d.fertilizer_count === 0;
  return (
    <>
      <PageHeader title={`Welcome, ${user.name.split(" ")[0]}!`} sub="Monitor your plants and keep them healthy" />
      <div className="action-grid">{ACTIONS.map(([to, t, s, Icon]) => <Link to={to} key={to} className="action"><Icon size={22} /><b>{t}</b><span>{s}</span></Link>)}</div>
      <div className="stats">
        <Stat icon={Activity} label="Total diagnoses" value={d.total} tone="blue" />
        <Stat icon={Leaf} label="Healthy results" value={d.healthy} tone="green" />
        <Stat icon={Bug} label="Disease detections" value={d.diseased} tone="red" />
        <Stat icon={Target} label="Avg. model confidence" value={pct(d.avg_confidence)} tone="blue" />
        <Stat icon={Sprout} label="Crop recommendations" value={d.crop_count} tone="green" />
        <Stat icon={FlaskConical} label="Fertilizer guidance" value={d.fertilizer_count} tone="amber" />
      </div>
      {empty && <Card><Empty title="Nothing here yet" text="Your statistics appear after your first diagnosis or recommendation." action={<Link className="btn btn-primary" to="/diagnose">Diagnose your first plant</Link>} /></Card>}
      <div className="grid-2">
        <Card title="Diagnosis trend (last 30 days)"><TrendChart data={d.trend} /></Card>
        <Card title="Disease distribution"><Donut data={d.distribution} /></Card>
      </div>
      <Card title="Recent activity" right={<Link to="/history" className="link">View all</Link>}>
        {d.recent_activity.length === 0 ? <Empty icon={HeartPulse} title="No activity yet" /> : (
          <div className="table-wrap"><table><thead><tr><th>Date &amp; time</th><th>Type</th><th>Result</th><th /></tr></thead><tbody>
            {d.recent_activity.map(a => (
              <tr key={a.type + a.id}><td>{fmtDate(a.created_at)}</td><td><span className={`pill pill-${a.type}`}>{TYPE[a.type]}</span></td>
                <td className="with-thumb">{a.thumb && <img src={a.thumb} alt="" />}<span>{a.summary}<small>{a.detail}</small></span></td>
                <td><Link className="btn btn-sm btn-primary" to={a.type === "disease" ? `/diagnosis/${a.id}` : `/record/${a.id}`}>View</Link></td></tr>
            ))}</tbody></table></div>
        )}
      </Card>
    </>
  );
}
