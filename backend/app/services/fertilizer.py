"""Fertilizer / soil-nutrient guidance - transparent, rule-based agronomic method.

Crop nutrient guidance is based on documented agronomic uptake profiles (synthesized from
FAO Fertilizer and Plant Nutrition Bulletins and ICAR Package of Practices guidelines).

Farmers can request guidance primarily from the crop name alone.
Optional soil-test categories (Low / Medium / High / pH) can be provided under an expandable
section to personalize the guidance without guessing unmeasured values.

No commercial fertilizer application rates or quantities are produced: exact amounts require
soil-test calibration, crop variety, growth stage, and target yield from local agricultural
extension services.
"""

from __future__ import annotations

import re
from typing import Optional

LEVELS = {"low", "medium", "high"}

NUTRIENTS = {
    "N": "Nitrogen",
    "P": "Phosphorus",
    "K": "Potassium",
}

LEGUMES = {
    "soybean", "chickpea", "lentil", "pigeonpea", "mungbean",
    "mothbeans", "blackgram", "kidneybeans", "groundnut", "peas",
    "beans", "peanut", "cowpea", "field pea", "green gram",
    "black gram", "red gram", "horse gram",
}

LOW_OPTIONS = {
    "N": {
        "mineral": (
            "Nitrogen fertilisers such as urea, ammonium sulfate "
            "or calcium ammonium nitrate."
        ),
        "organic": (
            "Compost or well-rotted manure; legume rotation "
            "or green manure."
        ),
    },
    "P": {
        "mineral": (
            "Phosphorus fertilisers such as single or triple "
            "superphosphate, or DAP (which also supplies nitrogen)."
        ),
        "organic": (
            "Compost or well-rotted manure; bone meal where available."
        ),
    },
    "K": {
        "mineral": (
            "Potassium fertilisers such as muriate of potash (MOP) "
            "or sulfate of potash (preferred for chloride-sensitive crops)."
        ),
        "organic": "Compost or well-rotted manure.",
    },
}

SAFETY = (
    "This is general guidance, not a fertiliser prescription. Exact products "
    "and amounts depend on your crop, soil-test method, target yield and local "
    "conditions. Always follow product labels and consult your local "
    "agricultural extension office or an agronomist."
)

FERTILIZER_DISTINCTION_NOTE = (
    "Nutrient needs vs. commercial fertilizer products: Plant nutrient requirements (N, P₂O₅, K₂O) "
    "refer to elemental or oxide nutrients needed by the plant, NOT the total weight of a commercial "
    "fertilizer product. For example, 100 kg of Urea provides approximately 46 kg of N, and 100 kg of "
    "DAP provides 18 kg of N and 46 kg of P₂O₅. Never apply commercial fertilizer quantities equal "
    "to nutrient requirement figures."
)

# Documented agronomic crop database synthesized from FAO Fertilizer and Plant Nutrition Bulletins
# and Indian Council of Agricultural Research (ICAR) crop management standards.
CROP_DATABASE: dict[str, dict] = {
    "rice": {
        "display_name": "Rice",
        "aliases": ["paddy", "oryza"],
        "category": "Cereal / Grain",
        "ph_range": (5.5, 7.0),
        "demands": {"N": "High", "P": "Moderate", "K": "Moderate to High"},
        "demand_details": {
            "N": "High nitrogen demand to support tillering, canopy development, and panicle initiation.",
            "P": "Moderate phosphorus demand, critical at transplanting/early rooting for vigorous root systems.",
            "K": "Moderate to high potassium requirement for stem strength, lodging resistance, and grain filling.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Urea or Ammonium Sulfate (ammonium forms are better retained in flooded anaerobic soils).",
                "organic": "Well-decomposed farmyard manure, compost, or green manuring (e.g. Sesbania/Dhaincha, Azolla).",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or Diammonium Phosphate (DAP, applied at planting).",
                "organic": "Decomposed farmyard manure, bone meal, or rock phosphate.",
            },
            "K": {
                "mineral": "Muriate of Potash (MOP / Potassium Chloride).",
                "organic": "Wood ash, farmyard manure, or paddy straw compost.",
            },
        },
        "growth_stages": {
            "planting": "Apply all phosphorus and a basal portion of nitrogen and potassium during final land preparation.",
            "vegetative": "Top-dress nitrogen during active tillering (20-25 days after transplanting) to maximize productive tillers.",
            "flowering": "Apply final split of nitrogen and potassium at panicle initiation to enhance spikelet count and grain filling.",
            "fruiting": "Maintain shallow standing water; avoid late excess nitrogen that prolongs vegetative growth.",
            "maturity": "Withhold fertilizers; drain water 10-14 days prior to harvest to promote uniform ripening.",
        },
        "is_legume": False,
        "special_notes": [
            "In flooded paddy, split nitrogen applications reduce leaching and ammonia volatilization losses.",
        ],
    },
    "wheat": {
        "display_name": "Wheat",
        "aliases": ["triticum"],
        "category": "Cereal / Grain",
        "ph_range": (6.0, 7.5),
        "demands": {"N": "High", "P": "Moderate to High", "K": "Moderate"},
        "demand_details": {
            "N": "High nitrogen demand for vegetative tillering, leaf area index, and grain protein development.",
            "P": "Critical during crown root initiation (CRI) and early tillering for root anchorage and head size.",
            "K": "Supports osmotic regulation, drought tolerance, and straw strength against lodging.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Urea or Calcium Ammonium Nitrate (CAN).",
                "organic": "Well-rotted farmyard manure or vermicompost.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or Diammonium Phosphate (DAP) placed at sowing.",
                "organic": "Compost or bone meal.",
            },
            "K": {
                "mineral": "Muriate of Potash (MOP).",
                "organic": "Compost or wood ash.",
            },
        },
        "growth_stages": {
            "planting": "Apply all phosphorus, potassium, and one-third of nitrogen as basal fertilizer at sowing.",
            "vegetative": "Apply first top-dressing of nitrogen at crown root initiation (first irrigation, 20-25 DAS).",
            "flowering": "Apply second nitrogen split prior to jointing/booting stage to assist grain formation.",
            "fruiting": "Avoid high moisture stress or excessive late nitrogen which causes lodging.",
            "maturity": "Withhold fertilizer applications; allow grain to dry and mature naturally.",
        },
        "is_legume": False,
        "special_notes": [
            "Band application of phosphorus near the seed line is substantially more effective than surface broadcast.",
        ],
    },
    "maize": {
        "display_name": "Maize",
        "aliases": ["corn", "zea mays"],
        "category": "Cereal / Coarse Grain",
        "ph_range": (5.8, 7.2),
        "demands": {"N": "Very High", "P": "Moderate to High", "K": "High"},
        "demand_details": {
            "N": "Heavy nitrogen feeder requiring sustained supply throughout vegetative development and silking.",
            "P": "Crucial for early seedling vigor, root architecture, and ear establishment.",
            "K": "Vital for stalk rigidity, vascular transport, and preventing lodging during cob development.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Urea, Ammonium Nitrate, or Ammonium Sulfate.",
                "organic": "Farmyard manure, poultry manure, or compost.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or DAP.",
                "organic": "Bone meal, rock phosphate, or compost.",
            },
            "K": {
                "mineral": "Muriate of Potash (MOP) or Potassium Sulfate (SOP).",
                "organic": "Farmyard manure or wood ash.",
            },
        },
        "growth_stages": {
            "planting": "Apply all phosphorus and potassium with one-third nitrogen at sowing.",
            "vegetative": "Side-dress nitrogen at knee-high stage (V6) when rapid nutrient uptake begins.",
            "flowering": "Apply final nitrogen split at tasseling/silking to maximize kernel count per cob.",
            "fruiting": "Ensure steady soil moisture during blister and milk stages for proper grain filling.",
            "maturity": "Withhold additional nutrients; monitor cob maturity.",
        },
        "is_legume": False,
        "special_notes": [
            "Zinc deficiency (white bud of maize) is common in alkaline or high-phosphorus soils; consider soil zinc status.",
        ],
    },
    "grapes": {
        "display_name": "Grapes",
        "aliases": ["grape", "vineyard", "grapevine"],
        "category": "Fruit / Vine",
        "ph_range": (6.0, 7.5),
        "demands": {"N": "Moderate", "P": "Low to Moderate", "K": "High to Very High"},
        "demand_details": {
            "N": "Moderate nitrogen demand. Must be strictly managed; excessive N induces excessive canopy shade, poor fruit set, and fungal susceptibility.",
            "P": "Modest phosphorus requirements, important for root activity and early bunch differentiation.",
            "K": "High to very high potassium demand for berry sizing, sugar accumulation, berry color development, and cane hardiness.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Calcium Nitrate (preferred for supplying calcium without excess acidity) or Urea.",
                "organic": "Well-aged farmyard manure, compost, or bio-fertilizers applied during winter pruning.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or DAP banded into root zone.",
                "organic": "Well-rotted compost, bone meal, or rock phosphate.",
            },
            "K": {
                "mineral": "Sulfate of Potash (SOP / Potassium Sulfate) is strongly preferred over MOP to avoid chloride toxicity.",
                "organic": "Well-decomposed compost or organic vine mulches.",
            },
        },
        "growth_stages": {
            "planting": "Deeply incorporate well-decomposed manure and phosphorus into the vine trench before planting.",
            "vegetative": "Apply modest nitrogen during early spring shoot flush; cease nitrogen well ahead of flowering.",
            "flowering": "Monitor boron, zinc, and balanced phosphorus for uniform bloom and fruit set.",
            "fruiting": "Apply potassium progressively from pea-size stage through veraison (softening and color transition).",
            "maturity": "Avoid nitrogen late in the season to encourage cane wood lignification and winter dormancy.",
        },
        "is_legume": False,
        "special_notes": [
            "Grapes are sensitive to chloride accumulation; prefer Sulfate of Potash (SOP) over Muriate of Potash (MOP).",
            "Excessive nitrogen leads to dense shading, loose bunch structures, and severe powdery or downy mildew outbreaks.",
        ],
    },
    "pears": {
        "display_name": "Pears",
        "aliases": ["pear", "pyrus"],
        "category": "Fruit / Orchard Tree",
        "ph_range": (6.0, 7.0),
        "demands": {"N": "Moderate", "P": "Moderate", "K": "Moderate to High"},
        "demand_details": {
            "N": "Moderate nitrogen demand. Excess nitrogen promotes lush shoot growth highly susceptible to fire blight.",
            "P": "Moderate requirement for strong root system and floral bud development.",
            "K": "Supports fruit sizing, sugar content, fruit firmness, and winter tree hardiness.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Calcium Ammonium Nitrate (CAN) or Urea applied in early spring around budbreak.",
                "organic": "Compost or well-aged farmyard manure applied around the tree dripline.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or DAP applied in the root zone.",
                "organic": "Bone meal or well-decomposed compost.",
            },
            "K": {
                "mineral": "Potassium Sulfate (SOP) or Muriate of Potash (MOP).",
                "organic": "Compost or wood ash.",
            },
        },
        "growth_stages": {
            "planting": "Mix compost and phosphorus into subsoil below root ball when setting young trees.",
            "vegetative": "Apply moderate nitrogen early in spring before flowering to support early leaf canopy.",
            "flowering": "Check for adequate boron and calcium during petal fall and fruit set.",
            "fruiting": "Supply potassium during fruit development to promote fruit sizing and firmness.",
            "maturity": "Withhold nitrogen by mid-summer to harden shoots and prevent late-season fire blight strikes.",
        },
        "is_legume": False,
        "special_notes": [
            "Avoid high nitrogen rates in pears; vigorous, succulent shoots are markedly more susceptible to fire blight (Erwinia amylovora).",
            "Maintain calcium balance to reduce risk of internal corking and storage disorders.",
        ],
    },
    "tomato": {
        "display_name": "Tomato",
        "aliases": ["tomatoes", "solanum lycopersicum"],
        "category": "Vegetable / Solanaceous",
        "ph_range": (6.0, 6.8),
        "demands": {"N": "Moderate to High", "P": "High", "K": "Very High"},
        "demand_details": {
            "N": "Moderate nitrogen initially, increasing during canopy establishment; excess causes foliage overgrowth with delayed flowering.",
            "P": "High phosphorus demand at transplanting for rapid root establishment and early blossom set.",
            "K": "Very high potassium demand during flowering and fruit ripening for fruit sizing, coloration, and flavor.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Calcium Nitrate (supplies vital calcium to prevent blossom end rot), Urea, or Ammonium Nitrate.",
                "organic": "Well-composted farmyard manure or vermicompost.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or DAP incorporated at bed preparation.",
                "organic": "Bone meal or compost.",
            },
            "K": {
                "mineral": "Sulfate of Potash (SOP) or MOP (SOP is preferred for fruit quality and low salinity).",
                "organic": "Compost or wood ash.",
            },
        },
        "growth_stages": {
            "planting": "Incorporate phosphorus, organic compost, and modest basal nitrogen at transplanting.",
            "vegetative": "Supply balanced nitrogen to build a sturdy framework without excessive lush growth.",
            "flowering": "Shift emphasis to potassium and maintain steady calcium availability.",
            "fruiting": "Maintain high potassium levels through multiple split applications to support continuous fruit sizing.",
            "maturity": "Avoid water stress or sudden nitrogen pulses that cause fruit cracking or blotchy ripening.",
        },
        "is_legume": False,
        "special_notes": [
            "Blossom end rot is caused by localized calcium deficiency in fruit tissue, often worsened by irregular watering or excess nitrogen/ammonium.",
        ],
    },
    "potato": {
        "display_name": "Potato",
        "aliases": ["potatoes", "solanum tuberosum"],
        "category": "Tuber / Root Crop",
        "ph_range": (5.0, 6.5),
        "demands": {"N": "High", "P": "High", "K": "Very High"},
        "demand_details": {
            "N": "High nitrogen demand for rapid canopy development; excess late nitrogen delays tuber bulking.",
            "P": "High phosphorus requirement for root proliferation, stolon formation, and tuber set.",
            "K": "Very high potassium feeder; vital for carbohydrate translocation, tuber sizing, and dry matter accumulation.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Urea or Calcium Ammonium Nitrate.",
                "organic": "Well-rotted farmyard manure applied well ahead of planting.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or DAP banded at planting.",
                "organic": "Bone meal or compost.",
            },
            "K": {
                "mineral": "Sulfate of Potash (SOP) is preferred over MOP to maximize tuber specific gravity and processing quality.",
                "organic": "Compost or wood ash.",
            },
        },
        "growth_stages": {
            "planting": "Apply all phosphorus, half the nitrogen, and half the potassium in furrows at planting.",
            "vegetative": "Top-dress remaining nitrogen at first earthing-up (approx. 25-30 days after emergence).",
            "flowering": "Supply remaining potassium during tuber initiation and early bulking.",
            "fruiting": "Ensure steady soil moisture during tuber bulking to avoid hollow heart and cracking.",
            "maturity": "Withhold fertilizer and desicate vines 10-14 days before harvest to firm tuber skins.",
        },
        "is_legume": False,
        "special_notes": [
            "Sulfate of Potash (SOP) produces higher dry matter content and less internal bruising than Muriate of Potash (MOP).",
            "Maintain soil pH below 6.5 where potato common scab (Streptomyces scabies) is prevalent.",
        ],
    },
    "cotton": {
        "display_name": "Cotton",
        "aliases": ["gossypium"],
        "category": "Commercial / Fiber",
        "ph_range": (6.0, 8.0),
        "demands": {"N": "High", "P": "Moderate", "K": "High"},
        "demand_details": {
            "N": "High demand, must be synchronized with square formation and boll development to prevent shedding.",
            "P": "Moderate demand; essential early for deep taproot development.",
            "K": "High potassium demand; critical for fiber elongation, boll wall thickness, and disease resistance.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Urea or Ammonium Sulfate applied in splits.",
                "organic": "Farmyard manure or compost.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or DAP.",
                "organic": "Compost or rock phosphate.",
            },
            "K": {
                "mineral": "Muriate of Potash (MOP).",
                "organic": "Compost or crop residues.",
            },
        },
        "growth_stages": {
            "planting": "Apply all phosphorus and one-third nitrogen as basal placement.",
            "vegetative": "Top-dress one-third nitrogen at square initiation.",
            "flowering": "Apply final nitrogen and potassium split at peak flowering and boll formation.",
            "fruiting": "Avoid nitrogen application once major boll set is complete to prevent vegetative regrowth.",
            "maturity": "Withhold fertilizers; allow bolls to burst and dry.",
        },
        "is_legume": False,
        "special_notes": [
            "Potassium deficiency during boll filling leads to premature senescence and weak fiber strength.",
        ],
    },
    "sugarcane": {
        "display_name": "Sugarcane",
        "aliases": ["cane", "saccharum"],
        "category": "Commercial / Cash Crop",
        "ph_range": (6.0, 7.5),
        "demands": {"N": "Very High", "P": "Moderate", "K": "High"},
        "demand_details": {
            "N": "Heavy nitrogen consumer during tillering and formative phases.",
            "P": "Essential for early root establishment and tillering.",
            "K": "Vital for sucrose synthesis, sugar translocation to stalks, and drought resistance.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Urea or Ammonium Sulfate.",
                "organic": "Filter cake / press mud, farmyard manure, or compost.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or DAP.",
                "organic": "Press mud or compost.",
            },
            "K": {
                "mineral": "Muriate of Potash (MOP).",
                "organic": "Press mud or wood ash.",
            },
        },
        "growth_stages": {
            "planting": "Apply all phosphorus, one-third potassium, and one-fourth nitrogen in furrows at planting.",
            "vegetative": "Apply nitrogen in splits at 45 and 90 days during formative tillering phase.",
            "flowering": "Complete all fertilizer applications before 120-150 days from planting.",
            "fruiting": "Do not apply late nitrogen as it lowers cane juice purity and sugar recovery percentage.",
            "maturity": "Withhold all nutrients and irrigation appropriately before harvest.",
        },
        "is_legume": False,
        "special_notes": [
            "Late nitrogen applications prolong vegetative growth and significantly reduce sugar recovery percentage.",
        ],
    },
    "chickpea": {
        "display_name": "Chickpea",
        "aliases": ["gram", "bengal gram", "chana", "cicer arietinum"],
        "category": "Legume / Pulse",
        "ph_range": (6.0, 8.0),
        "demands": {"N": "Low", "P": "Moderate to High", "K": "Moderate"},
        "demand_details": {
            "N": "Low nitrogen requirement. Biological nitrogen fixation in root nodules meets 70-80% of plant needs; only starter N is beneficial.",
            "P": "Moderate to high requirement; essential for active root nodulation and energy transfer (ATP).",
            "K": "Provides drought tolerance and cold resistance during pod filling.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Starter dose via Diammonium Phosphate (DAP) or light Urea at sowing only.",
                "organic": "Inoculation with Rhizobium and Phosphate Solubilizing Bacteria (PSB) cultures.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP - also provides 11% Sulfur) or DAP.",
                "organic": "Compost, bone meal, or rock phosphate.",
            },
            "K": {
                "mineral": "Muriate of Potash (MOP).",
                "organic": "Farmyard manure.",
            },
        },
        "growth_stages": {
            "planting": "Apply starter nitrogen, all phosphorus, and potassium at sowing; inoculate seed with Rhizobium.",
            "vegetative": "Ensure weed-free conditions; do not apply top-dressed nitrogen as it suppresses root nodule formation.",
            "flowering": "Avoid waterlogging during flowering and pod development.",
            "fruiting": "Ensure adequate soil moisture at pod development.",
            "maturity": "Withhold nutrients; allow pods to dry uniformly.",
        },
        "is_legume": True,
        "special_notes": [
            "Chickpea is a legume that fixes atmospheric nitrogen. Applying heavy nitrogen suppresses nodule development and wastes money.",
            "Single Superphosphate (SSP) is preferred over DAP because it provides sulfur, which is essential for pulse protein synthesis.",
        ],
    },
    "soybean": {
        "display_name": "Soybean",
        "aliases": ["soya", "glycine max"],
        "category": "Legume / Oilseed",
        "ph_range": (6.0, 7.0),
        "demands": {"N": "Low", "P": "Moderate to High", "K": "Moderate to High"},
        "demand_details": {
            "N": "Low fertilizer N demand; Bradyrhizobium root nodules fix up to 75% of total nitrogen required.",
            "P": "Essential for nodulation, root system expansion, and energy transfer.",
            "K": "Important for pod filling, seed protein and oil content, and drought tolerance.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Starter nitrogen via DAP or light Urea at sowing.",
                "organic": "Bradyrhizobium japonicum seed inoculation and organic compost.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP, provides sulfur) or DAP.",
                "organic": "Compost or rock phosphate.",
            },
            "K": {
                "mineral": "Muriate of Potash (MOP).",
                "organic": "Farmyard manure or compost.",
            },
        },
        "growth_stages": {
            "planting": "Band starter nitrogen, all phosphorus, and potassium at planting alongside inoculated seed.",
            "vegetative": "Monitor nodulation (active nodules have pink/red internal color).",
            "flowering": "Avoid drought stress during flowering (R1-R2) and pod development.",
            "fruiting": "Maintain adequate moisture during seed filling (R5-R6).",
            "maturity": "Withhold inputs as leaves yellow and drop naturally.",
        },
        "is_legume": True,
        "special_notes": [
            "As a nitrogen-fixing legume, heavy nitrogen application is counterproductive and suppresses nodulation.",
        ],
    },
    "groundnut": {
        "display_name": "Groundnut",
        "aliases": ["peanut", "arachis hypogaea"],
        "category": "Legume / Oilseed",
        "ph_range": (5.8, 6.8),
        "demands": {"N": "Low", "P": "Moderate", "K": "Moderate to High"},
        "demand_details": {
            "N": "Low nitrogen demand; symbiotic nodulation fixes nitrogen.",
            "P": "Supports root growth and peg development.",
            "K": "Assists pod development, kernel filling, and oil synthesis.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Starter dose at sowing only.",
                "organic": "Rhizobium inoculation and compost.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP).",
                "organic": "Compost.",
            },
            "K": {
                "mineral": "Muriate of Potash (MOP).",
                "organic": "Farmyard manure.",
            },
        },
        "growth_stages": {
            "planting": "Apply starter nitrogen, all phosphorus, and potassium as basal application.",
            "vegetative": "Weed carefully before pegging begins.",
            "flowering": "Apply gypsum (calcium sulfate) at pegging to ensure pod wall development and prevent 'pops' (empty shells).",
            "fruiting": "Avoid soil compaction during pod development.",
            "maturity": "Withhold water and fertilizers before lifting pods.",
        },
        "is_legume": True,
        "special_notes": [
            "Gypsum application at flowering/pegging is essential to supply calcium directly to the developing subterranean pods.",
        ],
    },
    "apple": {
        "display_name": "Apple",
        "aliases": ["apples", "malus"],
        "category": "Fruit / Orchard Tree",
        "ph_range": (6.0, 7.0),
        "demands": {"N": "Moderate", "P": "Low to Moderate", "K": "High"},
        "demand_details": {
            "N": "Moderate demand; excess nitrogen causes poor fruit red color, soft flesh, and storage bitter pit.",
            "P": "Moderate requirement for root and spur development.",
            "K": "High potassium demand for fruit sizing, red anthocyanin pigmentation, and winter hardiness.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Calcium Ammonium Nitrate (CAN) or Urea applied in early spring.",
                "organic": "Compost or aged farmyard manure applied around dripline.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or DAP.",
                "organic": "Bone meal or compost.",
            },
            "K": {
                "mineral": "Potassium Sulfate (SOP) or Muriate of Potash (MOP).",
                "organic": "Compost or wood ash.",
            },
        },
        "growth_stages": {
            "planting": "Incorporate compost and phosphorus into planting pit.",
            "vegetative": "Apply nitrogen in early spring before budburst.",
            "flowering": "Monitor boron and calcium availability.",
            "fruiting": "Apply potassium during fruit expansion; spray calcium to prevent bitter pit.",
            "maturity": "Withhold nitrogen after midsummer to allow trees to prepare for winter dormancy.",
        },
        "is_legume": False,
        "special_notes": [
            "Excessive nitrogen reduces fruit storage life and increases bitter pit incidence.",
        ],
    },
    "banana": {
        "display_name": "Banana",
        "aliases": ["bananas", "musa"],
        "category": "Fruit / Giant Herb",
        "ph_range": (6.0, 7.5),
        "demands": {"N": "High", "P": "Low to Moderate", "K": "Very High"},
        "demand_details": {
            "N": "High nitrogen demand to support massive pseudostem and leaf canopy development.",
            "P": "Moderate requirement applied during early establishment.",
            "K": "Extremely high potassium consumer; potassium is crucial for bunch weight, finger length, and stalk strength.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Urea or Calcium Ammonium Nitrate.",
                "organic": "Compost, farmyard manure, or vermicompost.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or DAP.",
                "organic": "Compost or rock phosphate.",
            },
            "K": {
                "mineral": "Muriate of Potash (MOP) or Sulfate of Potash (SOP).",
                "organic": "Compost or wood ash.",
            },
        },
        "growth_stages": {
            "planting": "Apply generous organic manure and all phosphorus in planting pit.",
            "vegetative": "Apply nitrogen and potassium in regular monthly splits during vegetative flush.",
            "flowering": "Ensure high potassium availability at bunch shooting.",
            "fruiting": "Continue potassium through bunch development to maximize finger filling.",
            "maturity": "Withhold fertilizer as bunch reaches harvest maturity.",
        },
        "is_legume": False,
        "special_notes": [
            "Bananas require more potassium than almost any other cultivated crop; deficiency leads to choke throat and small bunches.",
        ],
    },
    "mango": {
        "display_name": "Mango",
        "aliases": ["mangoes", "mangifera indica"],
        "category": "Fruit / Orchard Tree",
        "ph_range": (5.5, 7.5),
        "demands": {"N": "Moderate", "P": "Moderate", "K": "High"},
        "demand_details": {
            "N": "Moderate demand; applied after harvest to induce post-harvest vegetative flush.",
            "P": "Supports deep taproot system and floral panicle development.",
            "K": "High demand for fruit sizing, sweetness, and reducing internal fruit breakdown.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Urea or Calcium Ammonium Nitrate.",
                "organic": "Farmyard manure or compost applied in circular trenches around dripline.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or DAP.",
                "organic": "Bone meal or compost.",
            },
            "K": {
                "mineral": "Muriate of Potash (MOP) or SOP.",
                "organic": "Compost or wood ash.",
            },
        },
        "growth_stages": {
            "planting": "Incorporate well-rotted manure and phosphorus into planting pit.",
            "vegetative": "Apply fertilizer post-harvest to promote new shoot growth for next year's crop.",
            "flowering": "Withhold fertilizer and irrigation prior to flowering to encourage floral bud differentiation.",
            "fruiting": "Provide light potassium and irrigation after fruit set (pea size) to reduce fruit drop.",
            "maturity": "Withhold fertilizers prior to harvest.",
        },
        "is_legume": False,
        "special_notes": [
            "Do not apply nitrogen or heavy water during the pre-flowering resting phase, as this triggers vegetative shoots instead of flower panicles.",
        ],
    },
    "onion": {
        "display_name": "Onion",
        "aliases": ["onions", "allium cepa"],
        "category": "Vegetable / Bulb",
        "ph_range": (6.0, 7.0),
        "demands": {"N": "Moderate to High", "P": "High", "K": "Moderate to High"},
        "demand_details": {
            "N": "Moderate to high demand; shallow root system requires easily accessible nutrients.",
            "P": "High demand; critical for early root development and uniform bulb formation.",
            "K": "Supports bulb firmness, storage longevity, and disease resistance.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Ammonium Sulfate (preferred for supplying essential sulfur) or Urea.",
                "organic": "Well-rotted farmyard manure or vermicompost.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP - supplies sulfur).",
                "organic": "Bone meal or compost.",
            },
            "K": {
                "mineral": "Sulfate of Potash (SOP) or MOP.",
                "organic": "Compost or wood ash.",
            },
        },
        "growth_stages": {
            "planting": "Apply all phosphorus, half potassium, and one-third nitrogen at transplanting.",
            "vegetative": "Top-dress nitrogen in splits up to 45 days after transplanting.",
            "flowering": "Avoid late nitrogen that causes thick necks and poor bulb keeping quality.",
            "fruiting": "Apply remaining potassium as bulb swelling begins.",
            "maturity": "Withhold water and nutrients 15-20 days before harvest to allow tops to fall and neck to dry.",
        },
        "is_legume": False,
        "special_notes": [
            "Sulfur is critical for onion pungency and storage life; fertilizers containing sulfur (SSP, ammonium sulfate) are beneficial.",
        ],
    },
    "chili": {
        "display_name": "Chili",
        "aliases": ["chilli", "chilies", "chilly", "pepper", "capsicum"],
        "category": "Vegetable / Solanaceous",
        "ph_range": (6.0, 7.0),
        "demands": {"N": "Moderate to High", "P": "Moderate to High", "K": "High"},
        "demand_details": {
            "N": "Moderate nitrogen throughout canopy development; avoid early excess.",
            "P": "Important for root branching and profuse flowering.",
            "K": "High demand for pod development, red pungency, and fruit firmness.",
        },
        "suitable_fertilizers": {
            "N": {
                "mineral": "Urea or Calcium Ammonium Nitrate.",
                "organic": "Farmyard manure or vermicompost.",
            },
            "P": {
                "mineral": "Single Superphosphate (SSP) or DAP.",
                "organic": "Compost or bone meal.",
            },
            "K": {
                "mineral": "Muriate of Potash (MOP) or SOP.",
                "organic": "Compost or wood ash.",
            },
        },
        "growth_stages": {
            "planting": "Apply basal phosphorus, half potassium, and one-third nitrogen at planting.",
            "vegetative": "Top-dress nitrogen at 30 days during active branching.",
            "flowering": "Apply balanced split at first flower flush.",
            "fruiting": "Apply potassium and light nitrogen after each picking to sustain continuous fruiting.",
            "maturity": "Maintain moderate moisture.",
        },
        "is_legume": False,
        "special_notes": [
            "Excessive nitrogen leads to vegetative overgrowth with heavy flower and fruitlet shedding.",
        ],
    },
    "papaya": {
        "display_name": "Papaya",
        "aliases": ["carica papaya"],
        "category": "Fruit / Rapid Perennial",
        "ph_range": (6.0, 7.0),
        "demands": {"N": "High", "P": "Moderate to High", "K": "High"},
        "demand_details": {
            "N": "High nitrogen demand to sustain continuous vegetative flush alongside flowering.",
            "P": "Important for early root establishment and continuous floral bud set.",
            "K": "Vital for fruit sugar content, pulp firmness, and fruit sizing.",
        },
        "suitable_fertilizers": {
            "N": {"mineral": "Urea or Calcium Nitrate.", "organic": "Farmyard manure or vermicompost."},
            "P": {"mineral": "SSP or DAP.", "organic": "Bone meal or compost."},
            "K": {"mineral": "SOP or MOP.", "organic": "Compost or wood ash."},
        },
        "growth_stages": {
            "planting": "Fill pit with organic manure and phosphorus before planting.",
            "vegetative": "Apply bimonthly split applications of nitrogen and potassium.",
            "flowering": "Maintain regular feeding as flowering and fruiting occur continuously.",
            "fruiting": "Provide consistent potassium for fruit sweetness.",
            "maturity": "Harvest mature fruits when blossom end turns yellow.",
        },
        "is_legume": False,
        "special_notes": [
            "Papaya is extremely sensitive to waterlogging; ensure well-drained soil.",
        ],
    },
    "coconut": {
        "display_name": "Coconut",
        "aliases": ["cocos nucifera"],
        "category": "Plantation / Palm",
        "ph_range": (5.5, 7.5),
        "demands": {"N": "Moderate", "P": "Moderate", "K": "Very High"},
        "demand_details": {
            "N": "Moderate demand to maintain healthy frond canopy and inflorescence emergence.",
            "P": "Moderate requirement for root maintenance and nut set.",
            "K": "Very high potassium demand; essential for nut yield, copra weight, and drought resistance.",
        },
        "suitable_fertilizers": {
            "N": {"mineral": "Urea.", "organic": "Farmyard manure or green leaf manure."},
            "P": {"mineral": "Rock phosphate or SSP.", "organic": "Bone meal or compost."},
            "K": {"mineral": "Muriate of Potash (MOP).", "organic": "Wood ash or compost."},
        },
        "growth_stages": {
            "planting": "Incorporate organic matter and phosphorus in the planting pit.",
            "vegetative": "Apply regular splits around the circular basin of young palms.",
            "flowering": "Maintain regular pre-monsoon and post-monsoon fertilizer splits for bearing palms.",
            "fruiting": "Ensure high potassium to maximize nut retention and copra oil yield.",
            "maturity": "Maintain circular mulching to retain soil moisture.",
        },
        "is_legume": False,
        "special_notes": [
            "Chlorine in Muriate of Potash (MOP) is beneficial for coconut palms, enhancing nut retention and drought tolerance.",
        ],
    },
    "pineapple": {
        "display_name": "Pineapple",
        "aliases": ["ananas comosus"],
        "category": "Fruit / Bromeliad",
        "ph_range": (4.5, 6.0),
        "demands": {"N": "Moderate to High", "P": "Low to Moderate", "K": "High to Very High"},
        "demand_details": {
            "N": "Essential for leaf biomass and early fruit size.",
            "P": "Low requirement; pineapples utilize soil phosphorus efficiently.",
            "K": "High demand for fruit weight, sugar-to-acid balance, and firm flesh.",
        },
        "suitable_fertilizers": {
            "N": {"mineral": "Urea or Ammonium Sulfate.", "organic": "Compost."},
            "P": {"mineral": "SSP or rock phosphate.", "organic": "Bone meal."},
            "K": {"mineral": "Sulfate of Potash (SOP) or MOP.", "organic": "Wood ash or compost."},
        },
        "growth_stages": {
            "planting": "Basal organic matter and phosphorus at planting.",
            "vegetative": "Apply nitrogen in splits during active vegetative leaf development.",
            "flowering": "Cease nitrogen before flower induction to prevent deformed fruit.",
            "fruiting": "Supply potassium during fruit growth for optimal sweetness.",
            "maturity": "Harvest when base of fruit begins yellowing.",
        },
        "is_legume": False,
        "special_notes": [
            "Pineapples prefer naturally acidic soil (pH 4.5 - 5.5).",
        ],
    },
}

# Alias lookup mapping for fast resolution of plurals and common alternative names
CROP_ALIASES: dict[str, str] = {
    "grapes": "grapes", "grape": "grapes", "grapevines": "grapes", "vineyard": "grapes",
    "pears": "pears", "pear": "pears",
    "rice": "rice", "paddy": "rice",
    "wheat": "wheat",
    "maize": "maize", "corn": "maize",
    "tomato": "tomato", "tomatoes": "tomato",
    "potato": "potato", "potatoes": "potato",
    "cotton": "cotton",
    "sugarcane": "sugarcane", "cane": "sugarcane",
    "chickpea": "chickpea", "chickpeas": "chickpea", "chana": "chickpea", "gram": "chickpea",
    "soybean": "soybean", "soybeans": "soybean", "soya": "soybean",
    "groundnut": "groundnut", "peanut": "groundnut", "peanuts": "groundnut",
    "apple": "apple", "apples": "apple",
    "banana": "banana", "bananas": "banana",
    "mango": "mango", "mangoes": "mango",
    "onion": "onion", "onions": "onion",
    "chili": "chili", "chilli": "chili", "chilies": "chili", "pepper": "chili", "peppers": "chili",
    "papaya": "papaya", "papayas": "papaya",
    "coconut": "coconut", "coconuts": "coconut",
    "pineapple": "pineapple", "pineapples": "pineapple",
    "peas": "chickpea", "pea": "chickpea",
    "beans": "soybean", "bean": "soybean",
    "lentil": "chickpea", "lentils": "chickpea",
    "pigeonpea": "chickpea", "mungbean": "chickpea", "blackgram": "chickpea", "kidneybeans": "chickpea",
}


class FertInputError(ValueError):
    """Raised when fertilizer recommendation input is invalid."""


def validate_crop_name(crop: str) -> str:
    """Validate crop-name format without restricting names to a fixed list."""
    crop = " ".join((crop or "").split())

    if not crop:
        raise FertInputError("Please enter the plant or crop name.")

    if len(crop) > 100:
        raise FertInputError("Plant or crop name must be 100 characters or fewer.")

    if not any(ch.isalpha() for ch in crop):
        raise FertInputError("Please enter a valid plant or crop name.")

    if not re.fullmatch(r"[^\W\d_][\w\s.'’()/-]*", crop, flags=re.UNICODE):
        raise FertInputError("Please enter a valid plant or crop name using letters.")

    return crop


def find_crop_profile(crop_name: str) -> tuple[str, dict | None]:
    """Look up crop in documented agronomic database, resolving aliases and plurals."""
    cleaned = " ".join(crop_name.strip().lower().split())

    # Direct match in aliases
    canonical = CROP_ALIASES.get(cleaned)
    if canonical and canonical in CROP_DATABASE:
        return canonical, CROP_DATABASE[canonical]

    # Direct match in database
    if cleaned in CROP_DATABASE:
        return cleaned, CROP_DATABASE[cleaned]

    # Singular strip
    if cleaned.endswith("s") and cleaned[:-1] in CROP_DATABASE:
        return cleaned[:-1], CROP_DATABASE[cleaned[:-1]]

    # Check database aliases
    for key, profile in CROP_DATABASE.items():
        if cleaned == key or cleaned in profile.get("aliases", []):
            return key, profile

    return cleaned, None


def recommend(
    crop: str,
    levels: dict | None = None,
    ph: float | str | None = None,
    growth_stage: str | None = None,
    location: str | None = None,
) -> dict:
    """Generate crop-specific fertilizer guidance with optional soil-test personalization.

    Parameters:
    - crop: Required plant or crop name.
    - levels: Optional dictionary with soil-test nutrient categories (N, P, K).
    - ph: Optional soil pH (0-14).
    - growth_stage: Optional crop growth stage.
    - location: Optional geographical context.
    """
    crop = validate_crop_name(crop)
    canonical_key, crop_profile = find_crop_profile(crop)
    normalized_crop = " ".join(crop.casefold().split())

    # Validate and sanitize nutrient levels if provided
    clean = {"N": None, "P": None, "K": None}
    has_soil_nutrient_test = False

    if isinstance(levels, dict):
        for key in NUTRIENTS:
            raw_val = levels.get(key)
            val = (
                None
                if raw_val is None or str(raw_val).strip().lower() in ("", "unknown", "not measured", "none")
                else str(raw_val).strip().lower()
            )
            if val is not None:
                if val not in LEVELS:
                    raise FertInputError(f"{NUTRIENTS[key]} level must be low, medium, high or not measured.")
                clean[key] = val
                has_soil_nutrient_test = True

    # Validate soil pH if provided
    ph_val = None
    if ph not in (None, ""):
        try:
            ph_val = float(ph)
        except (TypeError, ValueError):
            raise FertInputError("Soil pH must be a number.")
        if not 0 <= ph_val <= 14:
            raise FertInputError("Soil pH must be between 0 and 14.")

    has_soil_test = bool(has_soil_nutrient_test or ph_val is not None)

    # ---------------------------------------------------------------------------------
    # Case 1: Unknown crop without cataloged agronomic data
    # ---------------------------------------------------------------------------------
    if not crop_profile:
        # If the crop is completely unknown and no soil test was provided:
        # Explain this clearly and avoid fabricating a recommendation.
        if not has_soil_test:
            return {
                "crop": crop,
                "data_available": False,
                "known_crop": False,
                "recommendation_type": "crop_data_unavailable",
                "inputs": {
                    "levels": clean,
                    "ph": ph_val,
                    "growth_stage": growth_stage,
                    "location": location,
                },
                "nutrients": [],
                "ph": None,
                "notes": [
                    f"Reliable agronomic nutrient demand data is not currently cataloged for '{crop}'. "
                    "PlantCare AI avoids fabricating unverified nutrient values or synthetic application rates.",
                    "Precise fertilizer requirements depend on existing soil conditions, crop variety, location, growth stage, and targeted yield.",
                    "We recommend obtaining a laboratory soil test and consulting your local agricultural extension service or university horticulture department.",
                ],
                "general_advice": [
                    "Conduct a laboratory soil test before purchasing commercial fertilizers.",
                    "Apply well-decomposed organic compost or farmyard manure to improve soil biology and moisture retention safely.",
                    "Follow localized agricultural extension bulletins for this crop.",
                ],
                "method": "Crop catalog lookup. No unverified data is fabricated.",
                "safety": SAFETY,
            }

    # Determine whether crop is a legume
    is_legume = False
    if crop_profile and crop_profile.get("is_legume"):
        is_legume = True
    elif normalized_crop in LEGUMES or normalized_crop.replace(" ", "") in LEGUMES:
        is_legume = True

    # Build nutrient items
    nutrients = []
    crop_demands = crop_profile.get("demands", {}) if crop_profile else {}
    crop_sources = crop_profile.get("suitable_fertilizers", {}) if crop_profile else {}
    demand_details = crop_profile.get("demand_details", {}) if crop_profile else {}

    # ---------------------------------------------------------------------------------
    # Case 2: Farmer provided soil-test measurements (Personalized recommendation)
    # ---------------------------------------------------------------------------------
    if has_soil_test:
        recommendation_type = "soil_test_personalized"
        for key, name in NUTRIENTS.items():
            level = clean[key]
            default_opt = LOW_OPTIONS[key]
            opt = crop_sources.get(key, default_opt)

            if level is None:
                nutrients.append({
                    "nutrient": name,
                    "level": "not measured",
                    "finding": f"Not measured - no conclusion is drawn about soil deficiency for {name.lower()}.",
                    "options": [],
                    "suitable_sources": opt,
                })
            elif level == "low":
                crop_ctx = f" (typical demand for {crop.title()} is {crop_demands.get(key, 'significant')})" if crop_profile else ""
                nutrients.append({
                    "nutrient": name,
                    "level": "low",
                    "finding": f"{name} is reported low in your soil test{crop_ctx}, so a deficiency is possible.",
                    "options": [opt["mineral"], opt["organic"]],
                    "suitable_sources": opt,
                })
            elif level == "medium":
                nutrients.append({
                    "nutrient": name,
                    "level": "medium",
                    "finding": f"{name} is reported adequate; no extra {name.lower()} is indicated beyond normal crop-removal replacement.",
                    "options": [],
                    "suitable_sources": opt,
                })
            else:
                nutrients.append({
                    "nutrient": name,
                    "level": "high",
                    "finding": f"{name} is reported high; avoid adding more - excess can cause nutrient imbalance and runoff.",
                    "options": [],
                    "suitable_sources": opt,
                })

    # ---------------------------------------------------------------------------------
    # Case 3: Crop-only flow (General crop nutrient guidance)
    # ---------------------------------------------------------------------------------
    else:
        recommendation_type = "crop_general"
        for key, name in NUTRIENTS.items():
            demand = crop_demands.get(key, "Moderate")
            detail = demand_details.get(key, f"Standard {name.lower()} maintenance required.")
            opt = crop_sources.get(key, LOW_OPTIONS[key])

            nutrients.append({
                "nutrient": name,
                "demand": demand,
                "level": "general guidance",
                "finding": (
                    f"General {crop.title()} requirement: {demand} demand. {detail} "
                    "Soil test results were not provided, so actual soil reserves are unknown."
                ),
                "options": [opt["mineral"], opt["organic"]],
                "suitable_sources": opt,
            })

    # Generate pH guidance block
    ph_block = None
    pref_range = crop_profile.get("ph_range") if crop_profile else (6.0, 7.5)

    if ph_val is not None:
        if ph_val < 5.5:
            message = "Strongly acidic for most crops; nutrient availability and root growth can suffer."
            option = "A liming material may help - the amount needs a lime-requirement test."
        elif ph_val < 6.0:
            message = "Slightly acidic; fine for some crops, low for many."
            option = "Check your crop's preferred range; light liming may be considered on local advice."
        elif ph_val <= 7.5:
            message = "Within the range suited to most crops."
            option = "No pH correction is generally needed."
        elif ph_val <= 8.5:
            message = "Alkaline; availability of iron, zinc and manganese can be reduced."
            option = "Acidifying fertilisers (e.g. ammonium sulfate), organic matter or elemental sulfur may help on local advice."
        else:
            message = "Strongly alkaline; test for salinity or sodicity."
            option = "Corrective options such as gypsum depend on those tests - seek local advice."

        ph_block = {
            "value": ph_val,
            "optimal_range": f"{pref_range[0]} - {pref_range[1]}",
            "finding": message,
            "option": option,
            "caveat": f"Preferred soil pH for {crop.title()} is {pref_range[0]} - {pref_range[1]}.",
        }
    else:
        ph_block = None

    # Build context notes
    notes = []

    if ph_val is None and crop_profile:
        notes.append(f"Preferred soil pH for {crop.title()} is {pref_range[0]} - {pref_range[1]}.")

    if not has_soil_test:
        notes.append(
            f"General recommendation: Soil test results were not provided. These are typical nutrient "
            f"requirements for {crop.title()}. Precise fertilizer requirements depend on soil conditions, "
            "crop variety, location, growth stage, and yield target."
        )

    if is_legume:
        notes.append(
            f"{crop.title()} is a legume and can fix part of its own nitrogen through root-nodule symbiosis; "
            "starter nitrogen only is typically needed - confirm locally."
        )

    if crop_profile and crop_profile.get("special_notes"):
        notes.extend(crop_profile["special_notes"])

    # Growth stage specific guidance if provided
    if growth_stage and crop_profile and crop_profile.get("growth_stages"):
        stage_key = growth_stage.strip().lower()
        stages_map = crop_profile["growth_stages"]
        stage_advice = stages_map.get(stage_key)
        if not stage_advice:
            for k, advice in stages_map.items():
                if k in stage_key or stage_key in k:
                    stage_advice = advice
                    break
        if stage_advice:
            notes.append(f"Growth stage guidance ({growth_stage.title()}): {stage_advice}")

    # Location specific context if provided
    if location and location.strip():
        notes.append(
            f"Location context ({location.strip()}): Soil characteristics vary across agro-climatic zones. "
            "Consult your local Krishi Vigyan Kendra (KVK) or district agricultural officer for local baseline schedules."
        )

    # Note regarding unknown crop with soil test
    if not crop_profile and has_soil_test:
        notes.append(
            f"Note: Crop-specific uptake requirements for '{crop}' are not cataloged. "
            "The soil-test interpretation above reflects general soil nutrient availability without crop-specific adjustments."
        )

    # Method description
    if has_soil_test:
        method = (
            "Transparent rule-based guidance from soil-test categories you entered. "
            "No machine-learning model and no synthetic application rates are used."
        )
    else:
        method = (
            f"General agronomic guidance based on published {crop.title()} nutrient uptake profiles (FAO/ICAR guidelines). "
            "No soil test was provided; actual soil status is not inferred."
        )

    return {
        "crop": crop,
        "data_available": True,
        "known_crop": bool(crop_profile),
        "has_soil_test": has_soil_test,
        "recommendation_type": recommendation_type,
        "inputs": {
            "levels": clean,
            "ph": ph_val,
            "growth_stage": growth_stage,
            "location": location,
        },
        "crop_demand": crop_demands,
        "nutrients": nutrients,
        "ph": ph_block,
        "notes": notes,
        "fertilizer_distinction_note": FERTILIZER_DISTINCTION_NOTE,
        "method": method,
        "safety": SAFETY,
    }
