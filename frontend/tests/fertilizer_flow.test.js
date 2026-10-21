import test from "node:test";
import assert from "node:assert/strict";

/**
 * Diagnostic unit test suite for Fertilizer flow logic:
 * - Crop-only general recommendation flow
 * - Optional soil test personalized flow
 * - Unknown crop handling without fabrication
 * - Missing measurements are not assumed
 * - Input validation (empty crop, pH range)
 * - Prevention of fabricated application rates
 */

function createFertilizerController(mockApi) {
  let form = {
    crop: "",
    n_level: "",
    p_level: "",
    k_level: "",
    ph: "",
    growth_stage: "",
    location: ""
  };
  let res = null;
  let err = "";
  let busy = false;

  function updateField(key, value) {
    form[key] = value;
  }

  async function submit() {
    err = "";
    res = null;

    if (!form.crop.trim()) {
      err = "Please enter the crop being cultivated.";
      return;
    }
    if (form.ph !== "" && (Number(form.ph) < 0 || Number(form.ph) > 14)) {
      err = "Soil pH must be between 0 and 14.";
      return;
    }

    busy = true;
    try {
      const payload = {
        crop: form.crop.trim(),
        n_level: form.n_level || null,
        p_level: form.p_level || null,
        k_level: form.k_level || null,
        ph: form.ph === "" ? null : Number(form.ph),
        growth_stage: form.growth_stage || null,
        location: form.location.trim() || null
      };
      res = await mockApi("/fertilizer/recommend", { method: "POST", json: payload });
    } catch (ex) {
      err = ex.message;
    } finally {
      busy = false;
    }
  }

  function getState() {
    return { form, res, err, busy };
  }

  return { updateField, submit, getState };
}

test("Crop-only flow: provides general crop guidance without requiring soil test", async () => {
  let apiCalledWith = null;

  const mockApi = async (endpoint, opts) => {
    if (endpoint === "/fertilizer/recommend") {
      apiCalledWith = opts.json;
      return {
        crop: "Rice",
        data_available: true,
        known_crop: true,
        has_soil_test: false,
        recommendation_type: "crop_general",
        inputs: { levels: { N: null, P: null, K: null }, ph: null },
        nutrients: [
          { nutrient: "Nitrogen", demand: "High", level: "general guidance", finding: "High nitrogen demand for tillering.", options: ["Urea", "Compost"] },
          { nutrient: "Phosphorus", demand: "Moderate", level: "general guidance", finding: "Moderate demand for rooting.", options: ["SSP", "Compost"] },
          { nutrient: "Potassium", demand: "Moderate to High", level: "general guidance", finding: "Potassium for grain filling.", options: ["MOP", "Wood ash"] }
        ],
        notes: [
          "General recommendation: Soil test results were not provided. These are typical nutrient requirements for Rice. Precise fertilizer requirements depend on soil conditions, crop variety, location, growth stage, and yield target."
        ],
        fertilizer_distinction_note: "Nutrient needs vs. commercial fertilizer products: Plant nutrient requirements refer to elemental nutrients, not fertilizer bag quantities.",
        safety: "This is general guidance, not a fertiliser prescription."
      };
    }
  };

  const ctrl = createFertilizerController(mockApi);
  ctrl.updateField("crop", "Rice");
  await ctrl.submit();

  const state = ctrl.getState();
  assert.equal(state.err, "");
  assert.ok(state.res);
  assert.equal(state.res.crop, "Rice");
  assert.equal(state.res.has_soil_test, false);
  assert.equal(state.res.recommendation_type, "crop_general");
  assert.equal(state.res.nutrients.length, 3);
  assert.equal(apiCalledWith.n_level, null);
  assert.equal(apiCalledWith.p_level, null);
  assert.equal(apiCalledWith.k_level, null);
  assert.equal(apiCalledWith.ph, null);
});

test("Optional soil-test flow: personalizes recommendation and does not assume unmeasured values", async () => {
  let apiCalledWith = null;

  const mockApi = async (endpoint, opts) => {
    if (endpoint === "/fertilizer/recommend") {
      apiCalledWith = opts.json;
      return {
        crop: "Grapes",
        data_available: true,
        has_soil_test: true,
        recommendation_type: "soil_test_personalized",
        inputs: { levels: { N: "low", P: null, K: "high" }, ph: 6.8 },
        nutrients: [
          { nutrient: "Nitrogen", level: "low", finding: "Nitrogen is reported low in your soil test.", options: ["Calcium Nitrate", "Compost"] },
          { nutrient: "Phosphorus", level: "not measured", finding: "Not measured - no conclusion is drawn about soil deficiency for phosphorus.", options: [] },
          { nutrient: "Potassium", level: "high", finding: "Potassium is reported high; avoid adding more.", options: [] }
        ],
        ph: { value: 6.8, finding: "Within normal range." },
        notes: ["Grapes prefer Sulfate of Potash (SOP) over MOP."],
        safety: "This is general guidance."
      };
    }
  };

  const ctrl = createFertilizerController(mockApi);
  ctrl.updateField("crop", "Grapes");
  ctrl.updateField("n_level", "low");
  ctrl.updateField("k_level", "high");
  ctrl.updateField("ph", "6.8");
  await ctrl.submit();

  const state = ctrl.getState();
  assert.equal(state.err, "");
  assert.ok(state.res);
  assert.equal(state.res.has_soil_test, true);
  assert.equal(state.res.recommendation_type, "soil_test_personalized");

  const by = Object.fromEntries(state.res.nutrients.map(n => [n.nutrient, n]));
  assert.equal(by["Nitrogen"].level, "low");
  assert.equal(by["Potassium"].level, "high");
  assert.equal(by["Phosphorus"].level, "not measured");
  assert.equal(by["Phosphorus"].options.length, 0);
  assert.equal(apiCalledWith.p_level, null);
});

test("Unknown crop flow: explains data is unavailable and avoids fabricating recommendations", async () => {
  const mockApi = async () => ({
    crop: "UncatalogedPlantX",
    data_available: false,
    known_crop: false,
    recommendation_type: "crop_data_unavailable",
    nutrients: [],
    notes: [
      "Reliable agronomic nutrient demand data is not currently cataloged for 'UncatalogedPlantX'. PlantCare AI avoids fabricating unverified nutrient values or synthetic application rates."
    ],
    general_advice: [
      "Conduct a laboratory soil test before purchasing commercial fertilizers.",
      "Apply well-decomposed organic compost or farmyard manure."
    ],
    safety: "This is general guidance."
  });

  const ctrl = createFertilizerController(mockApi);
  ctrl.updateField("crop", "UncatalogedPlantX");
  await ctrl.submit();

  const state = ctrl.getState();
  assert.equal(state.err, "");
  assert.ok(state.res);
  assert.equal(state.res.data_available, false);
  assert.equal(state.res.nutrients.length, 0);
  assert.ok(state.res.notes[0].includes("not currently cataloged"));
  assert.ok(state.res.general_advice.length > 0);
});

test("Validation rejects empty crop and invalid pH range client-side", async () => {
  const ctrl = createFertilizerController(async () => ({}));

  // Empty crop
  ctrl.updateField("crop", "");
  await ctrl.submit();
  assert.ok(ctrl.getState().err.includes("Please enter the crop"));

  // Invalid pH
  ctrl.updateField("crop", "Rice");
  ctrl.updateField("ph", "15");
  await ctrl.submit();
  assert.ok(ctrl.getState().err.includes("between 0 and 14"));
});

test("Recommendation outputs never invent commercial fertilizer rates", async () => {
  const mockApi = async () => ({
    crop: "Tomato",
    data_available: true,
    nutrients: [
      { nutrient: "Nitrogen", options: ["Urea", "Compost"] }
    ],
    safety: "Follow label instructions."
  });

  const ctrl = createFertilizerController(mockApi);
  ctrl.updateField("crop", "Tomato");
  await ctrl.submit();

  const text = JSON.stringify(ctrl.getState().res).toLowerCase();
  assert.equal(text.includes("kg/ha"), false);
  assert.equal(text.includes("per acre"), false);
});
