import React, { useEffect, useState } from "react";
import { CloudSun, Droplets, Search, Thermometer, CloudRain } from "lucide-react";
import { api } from "../api";
import { Card, Empty, Notice, PageHeader, Spinner, Stat, fmtDate } from "../ui";

export default function Weather() {
  const [status, setStatus] = useState(null);
  const [loc, setLoc] = useState(() => { try { return localStorage.getItem("pc_loc") || ""; } catch { return ""; } });
  const [w, setW] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api("/weather/status").then(setStatus).catch(() => {}); }, []);
  async function search(e) {
    e && e.preventDefault(); setErr(""); setW(null);
    if (loc.trim().length < 2) return setErr("Please enter a location.");
    setBusy(true);
    try { setW(await api(`/weather?location=${encodeURIComponent(loc.trim())}`)); try { localStorage.setItem("pc_loc", loc.trim()); } catch { /* storage unavailable */ } }
    catch (ex) { setErr(ex.message); } finally { setBusy(false); }
  }
  const val = (x, u) => (x === null || x === undefined ? "n/a" : `${Math.round(x * 10) / 10}${u}`);
  return (
    <>
      <PageHeader title="Weather Insights" sub="Current conditions and a short forecast for a location you choose" />
      <Card>
        <form className="inline" onSubmit={search}><div className="search"><Search size={17} /><input value={loc} onChange={e => setLoc(e.target.value)} placeholder="Enter a city, e.g. Davangere" maxLength={100} /></div>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Fetching..." : "Get weather"}</button></form>
        {status && <p className="muted small">Data provider: {status.provider}{status.api_key_configured ? "" : " (no API key needed). Set OPENWEATHER_API_KEY in backend/.env to use OpenWeatherMap instead."} Your precise location is never requested.</p>}
        {err && <Notice tone="error">{err}</Notice>}
      </Card>
      {busy && <Spinner label="Contacting weather service..." />}
      {!w && !busy && !err && <Card><Empty icon={CloudSun} title="Search for a location" text="Weather values are shown only when fetched live from the provider." /></Card>}
      {w && <>
        <Card title={`${w.location.name}${w.location.region ? ", " + w.location.region : ""}${w.location.country ? ", " + w.location.country : ""}`}
          right={<span className="muted small">Observed {w.observed_at || "n/a"} - fetched {fmtDate(w.fetched_at)} - {w.provider}</span>}>
          <div className="stats four">
            <Stat icon={Thermometer} label="Temperature" value={val(w.current.temperature_c, " \u00b0C")} tone="amber" />
            <Stat icon={Droplets} label="Humidity" value={val(w.current.humidity_pct, "%")} tone="blue" />
            <Stat icon={CloudRain} label="Precipitation (now)" value={val(w.current.precipitation_mm, " mm")} tone="blue" />
            <Stat icon={CloudSun} label="Conditions" value={w.current.conditions || "n/a"} tone="green" />
          </div>
        </Card>
        <Card title="Forecast">
          <div className="forecast">{w.forecast.map(d => (
            <div key={d.date} className="fday"><b>{new Date(d.date).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}</b>
              <span>{d.conditions || "n/a"}</span><span>{val(d.min_c, "\u00b0")} / {val(d.max_c, "\u00b0")}</span><span>{val(d.precip_mm, " mm")}</span></div>))}</div>
          {w.forecast.length === 0 && <p className="muted">No forecast data returned.</p>}
        </Card>
      </>}
    </>
  );
}
