import test from "node:test";
import assert from "node:assert/strict";

/**
 * Diagnostic unit test suite for Diagnose flow logic:
 * - Leaf image detection & analysis
 * - Stem image detection & limitation warning
 * - Whole crop image detection & limitation warning
 * - Uncertain image detection prompt for clearer photo
 * - Non-plant image rejection error display
 * - Client-side file validation checks
 */

// Helper replicating the state machine and logic from Diagnose.jsx
function createDiagnoseController(mockApi) {
  let file = null;
  let preview = "";
  let err = "";
  let partErr = "";
  let detecting = false;
  let detectedPart = null;
  let busy = false;
  let navigatedTo = null;

  const MAX_MB = 5;
  const OK = ["image/jpeg", "image/png", "image/webp"];

  async function choose(f) {
    err = "";
    partErr = "";
    detectedPart = null;
    if (!f) return;
    if (!OK.includes(f.type)) {
      err = "Unsupported file type. Please choose a JPG, PNG or WEBP image.";
      return;
    }
    if (f.size === 0) {
      err = "That file is empty.";
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      err = `That image is larger than ${MAX_MB} MB.`;
      return;
    }

    file = f;
    preview = `blob:${f.name}`;

    detecting = true;
    try {
      const res = await mockApi("/detect-part", { method: "POST" });
      detectedPart = res;
      if (res.plant_part === "uncertain") {
        partErr = res.limitation_warning || res.message || "Plant part detection uncertain. Please upload a clearer close-up image.";
      }
    } catch (e) {
      err = e.message;
      detectedPart = null;
    } finally {
      detecting = false;
    }
  }

  async function analyze() {
    if (!file || !detectedPart || detectedPart.plant_part === "uncertain") return;
    busy = true;
    err = "";
    try {
      const r = await mockApi("/predict", { method: "POST", plant_part: detectedPart.plant_part });
      navigatedTo = `/diagnosis/${r.id}`;
    } catch (e) {
      err = e.message;
    } finally {
      busy = false;
    }
  }

  function getState() {
    const canAnalyze = Boolean(file && !busy && !detecting && detectedPart && detectedPart.plant_part !== "uncertain" && !err);
    const showsLimitation = Boolean(detectedPart && detectedPart.plant_part !== "uncertain" && detectedPart.plant_part !== "leaf");
    return { file, err, partErr, detecting, detectedPart, busy, canAnalyze, showsLimitation, navigatedTo };
  }

  return { choose, analyze, getState };
}

test("Leaf image flow: automatically detects leaf and enables disease analysis", async () => {
  let predictCalled = false;
  let partPassed = null;

  const mockApi = async (endpoint, opts) => {
    if (endpoint === "/detect-part") {
      return {
        plant_part: "leaf",
        label: "Leaf",
        confidence: 0.98,
        probabilities: { leaf: 0.98, stem: 0.01, whole_plant: 0.01 },
        supported_for_disease_model: true,
        message: "Detected plant part: Leaf",
        limitation_warning: null,
      };
    }
    if (endpoint === "/predict") {
      predictCalled = true;
      partPassed = opts.plant_part;
      return { id: 42, label: "Apple___Black_rot", status: "ok" };
    }
  };

  const ctrl = createDiagnoseController(mockApi);
  await ctrl.choose({ name: "leaf.png", type: "image/png", size: 102400 });

  const state = ctrl.getState();
  assert.equal(state.err, "");
  assert.equal(state.partErr, "");
  assert.equal(state.detectedPart.plant_part, "leaf");
  assert.equal(state.detectedPart.label, "Leaf");
  assert.equal(state.showsLimitation, false);
  assert.equal(state.canAnalyze, true);

  await ctrl.analyze();
  assert.equal(predictCalled, true);
  assert.equal(partPassed, "leaf");
  assert.equal(ctrl.getState().navigatedTo, "/diagnosis/42");
});

test("Stem image flow: automatically detects stem and displays leaf model limitation warning", async () => {
  let partPassed = null;

  const mockApi = async (endpoint, opts) => {
    if (endpoint === "/detect-part") {
      return {
        plant_part: "stem",
        label: "Stem",
        confidence: 0.91,
        probabilities: { leaf: 0.05, stem: 0.91, whole_plant: 0.04 },
        supported_for_disease_model: false,
        message: "Detected plant part: Stem",
        limitation_warning: "Limitation notice: The disease classification model was trained exclusively on single-leaf images.",
      };
    }
    if (endpoint === "/predict") {
      partPassed = opts.plant_part;
      return { id: 43, label: "Apple___Black_rot", status: "unvalidated" };
    }
  };

  const ctrl = createDiagnoseController(mockApi);
  await ctrl.choose({ name: "stem.jpg", type: "image/jpeg", size: 120000 });

  const state = ctrl.getState();
  assert.equal(state.detectedPart.plant_part, "stem");
  assert.equal(state.showsLimitation, true, "Should display model limitation warning for stem images");
  assert.equal(state.canAnalyze, true);

  await ctrl.analyze();
  assert.equal(partPassed, "stem");
  assert.equal(ctrl.getState().navigatedTo, "/diagnosis/43");
});

test("Whole crop image flow: automatically detects whole_plant and displays limitation warning", async () => {
  let partPassed = null;

  const mockApi = async (endpoint, opts) => {
    if (endpoint === "/detect-part") {
      return {
        plant_part: "whole_plant",
        label: "Whole Crop",
        confidence: 0.84,
        probabilities: { leaf: 0.08, stem: 0.08, whole_plant: 0.84 },
        supported_for_disease_model: false,
        message: "Detected plant part: Whole Crop",
        limitation_warning: "Limitation notice: The disease classification model was trained exclusively on single-leaf images.",
      };
    }
    if (endpoint === "/predict") {
      partPassed = opts.plant_part;
      return { id: 44, label: "Tomato___Late_blight", status: "unvalidated" };
    }
  };

  const ctrl = createDiagnoseController(mockApi);
  await ctrl.choose({ name: "crop.webp", type: "image/webp", size: 150000 });

  const state = ctrl.getState();
  assert.equal(state.detectedPart.plant_part, "whole_plant");
  assert.equal(state.showsLimitation, true);
  assert.equal(state.canAnalyze, true);

  await ctrl.analyze();
  assert.equal(partPassed, "whole_plant");
  assert.equal(ctrl.getState().navigatedTo, "/diagnosis/44");
});

test("Uncertain image flow: asks user to upload clearer photo and disables disease analysis", async () => {
  let predictCalled = false;

  const mockApi = async (endpoint) => {
    if (endpoint === "/detect-part") {
      return {
        plant_part: "uncertain",
        label: "Uncertain",
        confidence: 0.33,
        probabilities: { leaf: 0.33, stem: 0.33, whole_plant: 0.33 },
        supported_for_disease_model: false,
        message: "Plant part detection is uncertain.",
        limitation_warning: "Please upload a clearer close-up photo of the affected plant.",
      };
    }
    if (endpoint === "/predict") {
      predictCalled = true;
      return { id: 99 };
    }
  };

  const ctrl = createDiagnoseController(mockApi);
  await ctrl.choose({ name: "blurry.png", type: "image/png", size: 50000 });

  const state = ctrl.getState();
  assert.equal(state.detectedPart.plant_part, "uncertain");
  assert.ok(state.partErr.includes("clearer"));
  assert.equal(state.canAnalyze, false, "Analysis button must be disabled for uncertain images");

  await ctrl.analyze();
  assert.equal(predictCalled, false, "Predict must not be invoked when plant part is uncertain");
  assert.equal(state.navigatedTo, null);
});

test("Non-plant image rejection: rejects person or illustration and shows error banner", async () => {
  let predictCalled = false;

  const mockApi = async (endpoint) => {
    if (endpoint === "/detect-part") {
      throw new Error("The uploaded image appears to be a photo of a person or face. Please upload a clear photo of a plant leaf, stem, or whole plant.");
    }
    if (endpoint === "/predict") {
      predictCalled = true;
      return {};
    }
  };

  const ctrl = createDiagnoseController(mockApi);
  await ctrl.choose({ name: "person.jpg", type: "image/jpeg", size: 90000 });

  const state = ctrl.getState();
  assert.ok(state.err.includes("person or face"));
  assert.equal(state.detectedPart, null);
  assert.equal(state.canAnalyze, false, "Analysis button must be disabled when non-plant upload is rejected");

  await ctrl.analyze();
  assert.equal(predictCalled, false);
});

test("Client-side validation rejects unsupported files, empty files, and oversized files", async () => {
  const ctrl = createDiagnoseController(async () => {});

  // Unsupported file type
  await ctrl.choose({ name: "doc.pdf", type: "application/pdf", size: 1000 });
  assert.ok(ctrl.getState().err.includes("Unsupported file type"));
  assert.equal(ctrl.getState().canAnalyze, false);

  // Empty file
  await ctrl.choose({ name: "empty.png", type: "image/png", size: 0 });
  assert.ok(ctrl.getState().err.includes("empty"));
  assert.equal(ctrl.getState().canAnalyze, false);

  // Oversized file (> 5 MB)
  await ctrl.choose({ name: "huge.jpg", type: "image/jpeg", size: 6 * 1024 * 1024 });
  assert.ok(ctrl.getState().err.includes("larger than 5 MB"));
  assert.equal(ctrl.getState().canAnalyze, false);
});
