import React, { createContext, useContext, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { BarChart3, BookOpen, Camera, CloudSun, FlaskConical, History, LayoutDashboard, LogOut, Menu, Sprout, UserCircle, UserCheck, X, Leaf } from "lucide-react";
import { api } from "./api";
import { Spinner } from "./ui";
import AuthPage from "./pages/AuthPage";
import Dashboard from "./pages/Dashboard";
import Diagnose from "./pages/Diagnose";
import Result from "./pages/Result";
import CropRec from "./pages/CropRec";
import Fertilizer from "./pages/Fertilizer";
import Weather from "./pages/Weather";
import HistoryPage from "./pages/HistoryPage";
import RecordView from "./pages/RecordView";
import Library from "./pages/Library";
import Analytics from "./pages/Analytics";
import Experts from "./pages/Experts";
import Profile from "./pages/Profile";

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

const NAV = [
  ["/", "Dashboard", LayoutDashboard], ["/diagnose", "Disease Detection", Camera], ["/crop", "Crop Recommendation", Sprout],
  ["/fertilizer", "Fertilizer Recommendation", FlaskConical], ["/history", "Prediction History", History], ["/library", "Disease Library", BookOpen],
  ["/weather", "Weather Insights", CloudSun], ["/analytics", "Analytics", BarChart3], ["/experts", "Expert Assistance", UserCheck], ["/profile", "Profile", UserCircle],
];

function Shell({ children }) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand"><Leaf size={26} /><span>PlantCare <em>AI</em></span><button className="icon-btn close-mobile" onClick={() => setOpen(false)} aria-label="Close menu"><X /></button></div>
        <nav>{NAV.map(([to, label, Icon]) => (
          <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}><Icon size={17} />{label}</NavLink>
        ))}</nav>
        <button className="logout" onClick={logout}><LogOut size={17} />Logout</button>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Open menu"><Menu /></button>
          <div className="tagline">Smart Detection <i>•</i> Healthy Plants <i>•</i> Better Tomorrow</div>
          <div className="who"><span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span>{user.name}</div>
        </header>
        <main className="content">{children}</main>
      </div>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(undefined);
  const nav = useNavigate();
  useEffect(() => { api("/auth/me").then(d => setUser(d.user)).catch(() => setUser(null)); }, []);
  const logout = async () => { try { await api("/auth/logout", { method: "POST" }); } finally { setUser(null); nav("/login"); } };
  if (user === undefined) return <div className="boot"><Spinner label="Starting PlantCare AI..." /></div>;
  return (
    <AuthCtx.Provider value={{ user, setUser, logout }}>
      {!user ? (
        <Routes><Route path="/login" element={<AuthPage mode="login" />} /><Route path="/register" element={<AuthPage mode="register" />} /><Route path="*" element={<Navigate to="/login" replace />} /></Routes>
      ) : (
        <Shell><Routes>
          <Route path="/" element={<Dashboard />} /><Route path="/diagnose" element={<Diagnose />} /><Route path="/diagnosis/:id" element={<Result />} />
          <Route path="/crop" element={<CropRec />} /><Route path="/fertilizer" element={<Fertilizer />} /><Route path="/weather" element={<Weather />} />
          <Route path="/history" element={<HistoryPage />} /><Route path="/record/:id" element={<RecordView />} /><Route path="/library" element={<Library />} />
          <Route path="/analytics" element={<Analytics />} /><Route path="/experts" element={<Experts />} /><Route path="/profile" element={<Profile />} />
          <Route path="/login" element={<Navigate to="/" replace />} /><Route path="/register" element={<Navigate to="/" replace />} /><Route path="*" element={<Navigate to="/" replace />} />
        </Routes></Shell>
      )}
    </AuthCtx.Provider>
  );
}
