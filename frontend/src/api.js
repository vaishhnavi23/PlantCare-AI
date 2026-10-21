// Thin fetch wrapper. All calls go to /api (proxied to FastAPI in dev, same origin in production).
export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function api(path, { method = "GET", json, form } = {}) {
  const opts = { method, credentials: "include", headers: {} };
  if (json !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(json); }
  if (form) opts.body = form;
  let res;
  try { res = await fetch("/api" + path, opts); }
  catch { throw new ApiError("Cannot reach the PlantCare AI server. Is the backend running?", 0); }
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok) throw new ApiError((data && data.detail) || `Request failed (${res.status}).`, res.status);
  return data;
}

export const qs = (obj) => {
  const p = new URLSearchParams();
  Object.entries(obj).forEach(([k, v]) => { if (v !== "" && v !== null && v !== undefined) p.set(k, v); });
  const s = p.toString();
  return s ? "?" + s : "";
};
