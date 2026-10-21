import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, AlertTriangle, CheckCircle2, Flower2, Leaf, Sprout, UploadCloud } from "lucide-react";
import { api } from "../api";
import { Card, Notice, PageHeader, Spinner, pct } from "../ui";

const PART_ICONS = { leaf: Leaf, stem: Sprout, whole_plant: Flower2, uncertain: AlertCircle };
const MAX_MB = 5, OK = ["image/jpeg", "image/png", "image/webp"];

export default function Diagnose() {
  const nav = useNavigate();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState("");
  const [err, setErr] = useState("");
  const [partErr, setPartErr] = useState("");
  const [detecting, setDetecting] = useState(false);
  const [detectedPart, setDetectedPart] = useState(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const input = useRef(null);

  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  async function choose(f) {
    setErr("");
    setPartErr("");
    setDetectedPart(null);
    if (!f) return;
    if (!OK.includes(f.type)) return setErr("Unsupported file type. Please choose a JPG, PNG or WEBP image.");
    if (f.size === 0) return setErr("That file is empty.");
    if (f.size > MAX_MB * 1024 * 1024) return setErr(`That image is larger than ${MAX_MB} MB.`);

    setFile(f);
    setPreview(URL.createObjectURL(f));

    // Automatically detect plant part from uploaded image
    setDetecting(true);
    const form = new FormData();
    form.append("file", f);
    try {
      const res = await api("/detect-part", { method: "POST", form });
      setDetectedPart(res);
      if (res.plant_part === "uncertain") {
        setPartErr(res.limitation_warning || res.message || "Plant part detection uncertain. Please upload a clearer close-up image.");
      }
    } catch (e) {
      setErr(e.message);
      setDetectedPart(null);
    } finally {
      setDetecting(false);
    }
  }

  async function analyze() {
    if (!file || !detectedPart || detectedPart.plant_part === "uncertain") return;
    setBusy(true);
    setErr("");
    const form = new FormData();
    form.append("file", file);
    form.append("plant_part", detectedPart.plant_part);
    try {
      const r = await api("/predict", { method: "POST", form });
      nav(`/diagnosis/${r.id}`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  const PartIcon = detectedPart && PART_ICONS[detectedPart.plant_part] ? PART_ICONS[detectedPart.plant_part] : Leaf;
  const canAnalyze = Boolean(file && !busy && !detecting && detectedPart && detectedPart.plant_part !== "uncertain" && !err);

  return (
    <>
      <PageHeader title="Upload Plant Image" sub="Upload a plant photo for automatic plant-part detection and disease diagnosis" />
      <div className="grid-2 wide-left">
        <Card>
          <div className={`dropzone ${drag ? "drag" : ""} ${preview ? "has" : ""}`} onClick={() => !preview && input.current.click()}
            onDragOver={e => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={e => { e.preventDefault(); setDrag(false); choose(e.dataTransfer.files[0]); }} role="button" tabIndex={0}
            onKeyDown={e => e.key === "Enter" && input.current.click()} aria-label="Upload area">
            {preview ? <img src={preview} alt="Selected plant" /> : <>
              <UploadCloud size={44} /><b>Drag and drop an image here</b><span>or</span>
              <button type="button" className="btn btn-primary" onClick={e => { e.stopPropagation(); input.current.click(); }}>Choose File</button>
              <small>Supports JPG, PNG, WEBP (max {MAX_MB} MB)</small></>}
          </div>
          <input ref={input} type="file" hidden accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" onChange={e => { choose(e.target.files[0]); e.target.value = ""; }} />
          {err && <Notice tone="error">{err}</Notice>}
          <div className="row-actions">
            {file && <button className="btn btn-light" onClick={() => { setFile(null); setPreview(""); setDetectedPart(null); setPartErr(""); setErr(""); input.current.click(); }} disabled={busy || detecting}>Replace image</button>}
            <button className="btn btn-primary grow" disabled={!canAnalyze} onClick={analyze}>
              {busy ? "Analysing disease..." : detecting ? "Detecting plant part..." : "Analyse Disease"}
            </button>
          </div>
          {(busy || detecting) && <div className="progress"><i /></div>}
        </Card>

        <Card title="Plant Part Analysis">
          {!file && (
            <Notice>Upload an image to automatically detect whether the plant part is a <b>Leaf</b>, <b>Stem</b>, or <b>Whole Crop</b>.</Notice>
          )}

          {detecting && (
            <div className="detecting-box">
              <Spinner size={20} />
              <span>Analyzing image and detecting plant part automatically...</span>
            </div>
          )}

          {partErr && (
            <Notice tone="warn">
              <b><AlertTriangle size={15} /> Plant part detection uncertain</b>
              <p>{partErr}</p>
              <p>Please upload a clearer, well-lit close-up photo of the plant leaf or affected area.</p>
            </Notice>
          )}

          {detectedPart && detectedPart.plant_part !== "uncertain" && (
            <div className="detected-part-box">
              <div className="detected-part-row">
                <div className="detected-part-icon">
                  <PartIcon size={26} />
                </div>
                <div>
                  <span className="muted small">Automatic classification</span>
                  <h3 className="detected-title">Detected plant part: <b>{detectedPart.label}</b></h3>
                </div>
                <span className="conf-pill">{pct(detectedPart.confidence)} confidence</span>
              </div>
              {detectedPart.plant_part !== "leaf" ? (
                <Notice tone="warn">
                  <b>Limitation notice:</b> The disease classification model was trained exclusively on single-leaf images and has not been validated for stem or whole-crop images. Accurate disease diagnosis cannot be claimed for non-leaf parts; please confirm any symptoms with an agricultural expert.
                </Notice>
              ) : (
                <Notice tone="info">
                  Take a sharp, well-lit close-up of one affected leaf against a plain background for the most reliable disease diagnosis.
                </Notice>
              )}
            </div>
          )}

          <h3>Image checks</h3>
          <ul className="checks">
            <li>Non-plant images (portraits of people, cartoons, vehicles) are rejected before disease inference.</li>
            <li>Plant part (Leaf, Stem, Whole Crop) is automatically classified directly from the image.</li>
            <li>If detection is uncertain, you will be prompted to upload a clearer image rather than silently guessing.</li>
            <li>Disease diagnosis is validated for leaf images; non-leaf parts clearly disclose model limitations.</li>
          </ul>
        </Card>
      </div>
    </>
  );
}
