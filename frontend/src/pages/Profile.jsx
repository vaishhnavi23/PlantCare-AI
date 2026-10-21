import React, { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { api } from "../api";
import { Card, Notice, PageHeader, Spinner, fmtDate } from "../ui";
import { useAuth } from "../App";

export default function Profile() {
  const { user, setUser, logout } = useAuth();
  const [stats, setStats] = useState(null);
  const [name, setName] = useState(user.name);
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [m1, setM1] = useState(null), [m2, setM2] = useState(null);
  useEffect(() => { api("/profile").then(d => setStats(d.stats)).catch(() => {}); }, []);
  async function save(e) {
    e.preventDefault(); setM1(null);
    try { const d = await api("/profile", { method: "PATCH", json: { name } }); setUser(d.user); setM1({ tone: "info", text: "Profile updated." }); }
    catch (ex) { setM1({ tone: "error", text: ex.message }); }
  }
  async function change(e) {
    e.preventDefault(); setM2(null);
    if (pw.new_password !== pw.confirm) return setM2({ tone: "error", text: "New passwords do not match." });
    try { await api("/profile/password", { method: "POST", json: { current_password: pw.current_password, new_password: pw.new_password } }); setPw({ current_password: "", new_password: "", confirm: "" }); setM2({ tone: "info", text: "Password changed." }); }
    catch (ex) { setM2({ tone: "error", text: ex.message }); }
  }
  return (
    <>
      <PageHeader title="Profile" />
      <div className="grid-2">
        <Card title="Account details">
          <div className="profile-head"><span className="avatar big">{user.name.slice(0, 1).toUpperCase()}</span><div><b>{user.name}</b><span className="muted">{user.email}</span></div></div>
          <dl className="info"><dt>Email</dt><dd>{user.email}</dd><dt>Member since</dt><dd>{fmtDate(user.created_at)}</dd></dl>
          <form onSubmit={save}><label>Display name<input value={name} onChange={e => setName(e.target.value)} maxLength={80} /></label>
            {m1 && <Notice tone={m1.tone}>{m1.text}</Notice>}<button className="btn btn-primary">Save changes</button></form>
        </Card>
        <Card title="Diagnosis statistics">{!stats ? <Spinner /> : <div className="stats three"><div className="mini-stat"><span>Total diagnoses</span><b>{stats.total}</b></div><div className="mini-stat"><span>Healthy</span><b className="g">{stats.healthy}</b></div><div className="mini-stat"><span>Diseased</span><b className="r">{stats.diseased}</b></div></div>}</Card>
        <Card title="Change password"><form onSubmit={change}>
          <label>Current password<input type="password" autoComplete="current-password" value={pw.current_password} onChange={e => setPw({ ...pw, current_password: e.target.value })} /></label>
          <label>New password<input type="password" autoComplete="new-password" value={pw.new_password} onChange={e => setPw({ ...pw, new_password: e.target.value })} /></label>
          <label>Confirm new password<input type="password" autoComplete="new-password" value={pw.confirm} onChange={e => setPw({ ...pw, confirm: e.target.value })} /></label>
          {m2 && <Notice tone={m2.tone}>{m2.text}</Notice>}<button className="btn btn-primary">Update password</button></form></Card>
        <Card title="Account security"><p className="muted">Passwords are stored as salted scrypt hashes. Sessions use an HttpOnly cookie.</p><button className="btn btn-light" onClick={logout}><LogOut size={15} /> Log out</button></Card>
      </div>
    </>
  );
}
