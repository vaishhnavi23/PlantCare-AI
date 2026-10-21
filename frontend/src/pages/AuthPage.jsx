import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Leaf } from "lucide-react";
import { api } from "../api";
import { Notice } from "../ui";
import { useAuth } from "../App";

export default function AuthPage({ mode }) {
  const isLogin = mode === "login";
  const { setUser } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ name: "", email: "", password: "", confirm: "" });
  const [show, setShow] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault(); setErr("");
    if (!isLogin) {
      if (!f.name.trim()) return setErr("Please enter your name.");
      if (f.password !== f.confirm) return setErr("Passwords do not match.");
    }
    setBusy(true);
    try {
      const d = await api(isLogin ? "/auth/login" : "/auth/register", { method: "POST", json: isLogin ? { email: f.email, password: f.password } : { name: f.name, email: f.email, password: f.password } });
      setUser(d.user); nav("/");
    } catch (ex) { setErr(ex.message); } finally { setBusy(false); }
  }

  return (
    <div className="auth">
      <div className="auth-hero">
        <Leaf size={46} /><h1>PlantCare <em>AI</em></h1>
        <p className="big">Healthy Plants<br />Healthy Future</p>
        <p>AI-powered plant disease detection, crop and fertilizer guidance, and expert assistance for better crop health.</p>
      </div>
      <form className="auth-card" onSubmit={submit} noValidate>
        <div className="tabs"><Link to="/login" className={isLogin ? "on" : ""}>Login</Link><Link to="/register" className={!isLogin ? "on" : ""}>Register</Link></div>
        <h2>{isLogin ? "Welcome Back!" : "Create your account"}</h2>
        <p className="muted">{isLogin ? "Login to your account to continue" : "Register to start diagnosing plants"}</p>
        {err && <Notice tone="error">{err}</Notice>}
        {!isLogin && <label>Full name<input value={f.name} onChange={set("name")} autoComplete="name" maxLength={80} /></label>}
        <label>Email address<input type="email" value={f.email} onChange={set("email")} placeholder="Enter your email" autoComplete="email" required /></label>
        <label>Password
          <span className="pw"><input type={show ? "text" : "password"} value={f.password} onChange={set("password")} placeholder="Enter your password" autoComplete={isLogin ? "current-password" : "new-password"} required />
            <button type="button" className="icon-btn" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"}>{show ? <EyeOff size={17} /> : <Eye size={17} />}</button></span>
        </label>
        {!isLogin && <><label>Confirm password<input type={show ? "text" : "password"} value={f.confirm} onChange={set("confirm")} autoComplete="new-password" /></label><p className="hint">At least 8 characters, with a letter and a number.</p></>}
        <button className="btn btn-primary wide" disabled={busy}>{busy ? "Please wait..." : isLogin ? "Login" : "Create account"}</button>
        <p className="muted center">{isLogin ? <>Don't have an account? <Link to="/register">Register</Link></> : <>Already registered? <Link to="/login">Login</Link></>}</p>
      </form>
    </div>
  );
}
