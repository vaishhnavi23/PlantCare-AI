import re

from .ml.labels import canon

DEFAULT_GUIDE = {
    "status": "Potential disease detected",
    "symptoms": "The model identified a PlantVillage disease class. Inspect the whole plant and confirm important diagnoses.",
    "treatment": "Use integrated disease management and confirm the diagnosis before treatment.",
    "pesticide": "Do not choose a pesticide from an AI prediction alone. Use only a product registered for the crop and confirmed disease.",
    "prevention": "Use sanitation, good airflow, appropriate irrigation, resistant varieties where available, and regular scouting."
}

GUIDES = {
    "healthy": {
        "status": "Healthy",
        "symptoms": "No disease pattern is indicated by the ResNet50 classification.",
        "treatment": "No disease treatment is indicated from this scan.",
        "pesticide": "None indicated for a healthy leaf. Avoid unnecessary pesticide applications.",
        "prevention": "Maintain balanced nutrition, adequate watering, sanitation, airflow and routine scouting."
    },
    "apple___scab": {
        "status": "Disease",
        "symptoms": "Olive-green to dark brown spots on leaves and fruit; leaves may curl, yellow and drop early.",
        "treatment": "Remove fallen leaves and infected material. Improve air circulation with pruning.",
        "pesticide": "Approved fungicides such as captan or other crop-registered products may be used in an integrated program. Follow the current label.",
        "prevention": "Rake and dispose of fallen leaves, maintain airflow and use resistant cultivars where available."
    },
    "apple___black_rot": {
        "status": "Disease",
        "symptoms": "Purple-bordered brown spots on leaves, frog-eye leaf spots, fruit rot and cankers.",
        "treatment": "Prune affected wood and remove mummified fruit and infected debris.",
        "pesticide": "Crop-registered fungicides may be used as part of a black-rot management program. Follow the current label.",
        "prevention": "Sanitize orchards by removing mummies and dead wood and maintain good vigor and airflow."
    },
    "apple___cedar_apple_rust": {
        "status": "Disease",
        "symptoms": "Bright orange-yellow leaf spots with small fungal structures on the underside; fruit and twigs may be affected.",
        "treatment": "Remove nearby alternate-host galls where feasible and follow a crop-specific rust program.",
        "pesticide": "Approved rust fungicides may be used where registered for the crop. Follow the current label.",
        "prevention": "Avoid planting susceptible apples near major alternate-host sources where practical and improve airflow."
    },
    "cherry_(including_sour)___powdery_mildew": {
        "status": "Disease",
        "symptoms": "White powder-like fungal growth on leaves and shoots; leaves may curl or distort.",
        "treatment": "Improve airflow and reduce prolonged humidity around foliage.",
        "pesticide": "Sulfur and selected powdery-mildew fungicides may be options where registered for the crop.",
        "prevention": "Maintain spacing, airflow and balanced growth; avoid conditions that keep foliage humid."
    },
    "corn_(maize)___cercospora_leaf_spot_gray_leaf_spot": {
        "status": "Disease",
        "symptoms": "Gray to tan elongated leaf lesions that may expand under humid conditions.",
        "treatment": "Use resistant hybrids, manage residue and consider a labeled fungicide program when justified.",
        "pesticide": "Crop-registered fungicides from appropriate FRAC groups may be used according to the current label.",
        "prevention": "Crop rotation, resistant hybrids and residue management can reduce disease pressure."
    },
    "corn_(maize)___common_rust_": {
        "status": "Disease",
        "symptoms": "Reddish-brown rust pustules can appear on leaf surfaces.",
        "treatment": "Scout the crop and consider a labeled fungicide only when disease pressure and crop stage justify it.",
        "pesticide": "Selected triazole or strobilurin fungicides may be options where registered.",
        "prevention": "Use resistant varieties where available and monitor during cool, humid periods."
    },
    "corn_(maize)___northern_leaf_blight": {
        "status": "Disease",
        "symptoms": "Long cigar-shaped gray-green to tan lesions on leaves.",
        "treatment": "Use resistant hybrids, residue management and an integrated fungicide program when justified.",
        "pesticide": "Labeled fungicide premixes may be options depending on crop registration and resistance-management guidance.",
        "prevention": "Crop rotation, residue management and resistant hybrids help reduce disease pressure."
    },
    "grape___black_rot": {
        "status": "Disease",
        "symptoms": "Brown circular leaf lesions and dark fruit mummies may occur.",
        "treatment": "Remove infected leaves, fruit mummies and affected material and improve canopy drying.",
        "pesticide": "Crop-registered fungicides may be used in an integrated grape black-rot program.",
        "prevention": "Remove mummies and infected wood and maintain vineyard airflow."
    },
    "grape___esca_(black_measles)": {
        "status": "Disease",
        "symptoms": "Esca is a grape trunk-disease complex that can produce characteristic leaf and fruit symptoms.",
        "treatment": "Remove affected vines or infected wood where practical and maintain vineyard sanitation.",
        "pesticide": "There is no simple curative foliar pesticide for established Esca; focus on sanitation and vine management.",
        "prevention": "Use clean planting material and protect pruning wounds."
    },
    "grape___leaf_blight_(isariopsis_leaf_spot)": {
        "status": "Disease",
        "symptoms": "Leaf spots and blight symptoms can develop on grape foliage.",
        "treatment": "Remove infected debris and improve canopy airflow and drying.",
        "pesticide": "Use only a fungicide registered for grapes and the confirmed disease, following the current label.",
        "prevention": "Sanitation, canopy management and regular scouting reduce disease pressure."
    },
    "peach___bacterial_spot": {
        "status": "Disease",
        "symptoms": "Small dark leaf spots and lesions may occur on peach foliage and fruit.",
        "treatment": "Use clean planting material, avoid working wet plants and remove severely affected tissue where practical.",
        "pesticide": "Copper-based bactericides are used in some crop programs where registered; follow the label.",
        "prevention": "Use pathogen-free material, sanitize tools and minimize prolonged leaf wetness."
    },
    "pepper,_bell___bacterial_spot": {
        "status": "Disease",
        "symptoms": "Small dark leaf spots and fruit lesions may develop on pepper.",
        "treatment": "Remove affected tissue, improve sanitation and avoid handling wet foliage.",
        "pesticide": "Copper-based bactericides may be options where registered for peppers; follow the label.",
        "prevention": "Use clean seed/transplants and reduce leaf wetness."
    },
    "potato___early_blight": {
        "status": "Disease",
        "symptoms": "Dark leaf lesions, often with concentric rings, causing early yellowing and defoliation.",
        "treatment": "Remove severely affected foliage, reduce soil splash and manage plant stress.",
        "pesticide": "Chlorothalonil, mancozeb and other crop-registered fungicides may be used according to the current label.",
        "prevention": "Crop rotation, sanitation, mulching and reduced leaf wetness help."
    },
    "potato___late_blight": {
        "status": "Disease",
        "symptoms": "Dark, water-soaked lesions can expand rapidly under cool, wet conditions.",
        "treatment": "Act quickly, remove heavily infected material and follow local late-blight alerts and integrated management.",
        "pesticide": "Locally registered late-blight fungicides may include specific premixes or active ingredients; follow the current label and resistance-management guidance.",
        "prevention": "Use clean planting material, monitor disease forecasts and reduce prolonged leaf wetness."
    },
    "strawberry___leaf_scorch": {
        "status": "Disease",
        "symptoms": "Dark spots and scorched-looking tissue may develop on strawberry leaves.",
        "treatment": "Remove infected debris and improve airflow and field sanitation.",
        "pesticide": "Fungicide choice depends on the confirmed causal organism; verify diagnosis and crop registration first.",
        "prevention": "Use clean planting material, sanitation and good canopy management."
    },
    "tomato___bacterial_spot": {
        "status": "Disease",
        "symptoms": "Small dark leaf spots and fruit lesions can occur on tomato.",
        "treatment": "Use clean transplants, remove severely affected material and avoid working wet foliage.",
        "pesticide": "Copper-based bactericides may be used in some tomato programs where registered.",
        "prevention": "Use pathogen-free seed/transplants, sanitize tools and minimize leaf wetness."
    },
    "tomato___early_blight": {
        "status": "Disease",
        "symptoms": "Dark lesions with concentric rings, often beginning on lower leaves.",
        "treatment": "Remove affected lower leaves where practical, reduce soil splash and improve airflow.",
        "pesticide": "Chlorothalonil, mancozeb and other labeled fungicides may be options for tomato early blight.",
        "prevention": "Crop rotation, sanitation, mulch and reduced leaf wetness help lower disease pressure."
    },
    "tomato___late_blight": {
        "status": "Disease",
        "symptoms": "Rapidly developing dark, water-soaked lesions can affect leaves, stems and fruit.",
        "treatment": "Remove heavily infected material and follow local late-blight management alerts.",
        "pesticide": "Use only locally registered late-blight products and follow label and resistance-management instructions.",
        "prevention": "Use clean planting material, monitor forecasts and reduce prolonged leaf wetness."
    },
    "tomato___leaf_mold": {
        "status": "Disease",
        "symptoms": "Fungal growth and yellowing can occur, especially under high humidity.",
        "treatment": "Improve ventilation and reduce humidity around foliage.",
        "pesticide": "Copper or other locally registered crop fungicides may be options depending on the production system.",
        "prevention": "Increase ventilation, maintain spacing and avoid unnecessary overhead irrigation."
    },
    "tomato___septoria_leaf_spot": {
        "status": "Disease",
        "symptoms": "Many small circular spots can appear on lower leaves and expand upward.",
        "treatment": "Remove affected lower leaves and reduce soil splash.",
        "pesticide": "Chlorothalonil, mancozeb or other locally registered crop fungicides may be used according to label.",
        "prevention": "Mulch soil, rotate crops and avoid wetting foliage."
    },
    "tomato___spider_mites_two_spotted_spider_mite": {
        "status": "Pest",
        "symptoms": "Stippling, bronzing, webbing and leaf decline are common, especially under hot dry conditions.",
        "treatment": "Inspect leaf undersides and use integrated mite management while conserving beneficial predators.",
        "pesticide": "If chemical control is justified, use a locally registered miticide labeled for the crop and pest and rotate modes of action.",
        "prevention": "Reduce plant stress, scout leaf undersides and avoid unnecessary broad-spectrum insecticides."
    },
    "tomato___target_spot": {
        "status": "Disease",
        "symptoms": "Circular brown lesions with target-like rings can occur on foliage.",
        "treatment": "Remove infected leaves and improve airflow and sanitation.",
        "pesticide": "Labeled fungicides may be options depending on crop registration and resistance-management guidance.",
        "prevention": "Reduce leaf wetness and remove infected debris."
    },
    "tomato___tomato_yellow_leaf_curl_virus": {
        "status": "Virus",
        "symptoms": "Yellowing, upward curling, stunting and reduced growth; whiteflies are an important vector.",
        "treatment": "There is no curative pesticide. Remove severely affected plants and manage vectors using local IPM guidance.",
        "pesticide": "Vector-control products target whiteflies, not the virus itself. Use integrated vector management.",
        "prevention": "Use resistant varieties where available, clean transplants and manage whiteflies."
    },
    "tomato___tomato_mosaic_virus": {
        "status": "Virus",
        "symptoms": "Mosaic patterns, leaf distortion and reduced growth may occur.",
        "treatment": "There is no curative pesticide. Remove infected plants and sanitize hands, tools and equipment.",
        "pesticide": "No pesticide cures an infected plant; focus on sanitation and relevant vector/weed management.",
        "prevention": "Use clean seed/transplants and disinfect tools after handling infected plants."
    },
}


GUIDES.update({
    "orange___haunglongbing_(citrus_greening)": {
        "status": "Disease",
        "symptoms": "Blotchy yellow mottling of leaves, lopsided small bitter fruit and twig dieback are typical.",
        "treatment": "There is no cure. Report suspected cases to local agricultural authorities; infected trees are commonly removed under regional programmes.",
        "pesticide": "Insecticides target the psyllid vector, not the bacterium. Follow local regulatory programmes and labels.",
        "prevention": "Use certified disease-free nursery stock and manage the Asian citrus psyllid under local guidance.",
    },
    "squash___powdery_mildew": {
        "status": "Disease",
        "symptoms": "White powdery patches on upper and lower leaf surfaces that can spread and cause leaves to yellow and dry.",
        "treatment": "Improve airflow, remove heavily affected leaves and begin management early.",
        "pesticide": "Sulfur, potassium bicarbonate and other products registered for cucurbits may be options; follow the current label.",
        "prevention": "Use resistant varieties where available, give plants space and avoid excess nitrogen.",
    },
})

# Causal agent / transmission, and conditions that favour the problem (general plant-pathology knowledge).
CAUSES = {
    "apple___apple_scab": ("Fungus Venturia inaequalis, overwintering in fallen leaves.", "Cool, wet spring weather with prolonged leaf wetness."),
    "apple___black_rot": ("Fungus Botryosphaeria obtusa, surviving in cankers and mummified fruit.", "Warm, humid weather, wounded or stressed trees, retained mummies and dead wood."),
    "apple___cedar_apple_rust": ("Fungus Gymnosporangium juniperi-virginianae, which needs both apple and juniper/cedar hosts.", "Wet spring weather near infected junipers or cedars."),
    "cherry_(including_sour)___powdery_mildew": ("Fungus Podosphaera clandestina.", "Warm days, cool nights and humid air; dense canopies."),
    "corn_(maize)___cercospora_leaf_spot_gray_leaf_spot": ("Fungus Cercospora zeae-maydis, surviving in corn residue.", "Warm, humid weather, continuous corn and minimum tillage."),
    "corn_(maize)___common_rust_": ("Fungus Puccinia sorghi, spread by wind-borne spores.", "Cool, moist conditions with heavy dews."),
    "corn_(maize)___northern_leaf_blight": ("Fungus Exserohilum turcicum, surviving in residue.", "Moderate temperatures with long periods of leaf wetness."),
    "grape___black_rot": ("Fungus Guignardia bidwellii, surviving in mummified berries.", "Warm, wet weather during shoot and fruit development."),
    "grape___esca_(black_measles)": ("A complex of wood-decay and vascular fungi entering through pruning wounds.", "Older vines, large pruning wounds and vine stress."),
    "grape___leaf_blight_(isariopsis_leaf_spot)": ("Fungus Pseudocercospora vitis (Isariopsis).", "Warm, humid weather and dense canopies, mainly late in the season."),
    "peach___bacterial_spot": ("Bacterium Xanthomonas arboricola pv. pruni.", "Warm, wet, windy weather and susceptible cultivars."),
    "pepper,_bell___bacterial_spot": ("Bacteria of the genus Xanthomonas, often seed- or transplant-borne.", "Warm, wet weather and overhead irrigation."),
    "potato___early_blight": ("Fungus Alternaria solani.", "Warm weather with alternating wet and dry periods; stressed or older plants."),
    "potato___late_blight": ("Oomycete Phytophthora infestans.", "Cool, wet, humid weather; it can spread very quickly."),
    "strawberry___leaf_scorch": ("Fungus Diplocarpon earlianum.", "Warm, humid weather and prolonged leaf wetness."),
    "tomato___bacterial_spot": ("Bacteria of the genus Xanthomonas, often seed- or transplant-borne.", "Warm, wet weather, splashing water and handling wet plants."),
    "tomato___early_blight": ("Fungus Alternaria solani.", "Warm weather with alternating wet and dry periods; stressed plants."),
    "tomato___late_blight": ("Oomycete Phytophthora infestans.", "Cool, wet, humid weather; it can spread very quickly."),
    "tomato___leaf_mold": ("Fungus Passalora fulva.", "High humidity (typical in greenhouses) and poor ventilation."),
    "tomato___septoria_leaf_spot": ("Fungus Septoria lycopersici, surviving in debris.", "Warm, wet weather and water splash from soil."),
    "tomato___spider_mites_two_spotted_spider_mite": ("Two-spotted spider mite, Tetranychus urticae (a pest, not a pathogen).", "Hot, dry, dusty conditions and plant stress."),
    "tomato___target_spot": ("Fungus Corynespora cassiicola.", "Warm, humid weather and dense foliage."),
    "tomato___tomato_yellow_leaf_curl_virus": ("A begomovirus transmitted by the whitefly Bemisia tabaci.", "Whitefly populations and infected transplants."),
    "tomato___tomato_mosaic_virus": ("A tobamovirus spread mechanically on hands, tools and seed.", "Handling plants after contact with infected material."),
    "orange___haunglongbing_(citrus_greening)": ("Bacterium Candidatus Liberibacter spp., spread by the Asian citrus psyllid.", "Presence of psyllids and infected nursery stock."),
    "squash___powdery_mildew": ("Fungi such as Podosphaera xanthii.", "Warm, dry days with humid nights and shaded, crowded plants."),
}

# Problems that can spread fast or have no cure: always recommend urgent expert contact.
HIGH_CONCERN = {
    "potato___late_blight", "tomato___late_blight", "tomato___tomato_yellow_leaf_curl_virus",
    "tomato___tomato_mosaic_virus", "orange___haunglongbing_(citrus_greening)", "grape___esca_(black_measles)",
}

_CANON_GUIDES = {canon(k): v for k, v in GUIDES.items() if k != "healthy"}
_CANON_CAUSES = {canon(k): v for k, v in CAUSES.items()}
_CANON_URGENT = {canon(k) for k in HIGH_CONCERN}


def is_high_concern(label: str) -> bool:
    return canon(label) in _CANON_URGENT


def get_disease_info(label: str) -> dict:
    """Reference information about a class. This is general knowledge, not something detected in the user's image."""
    key = canon(label)
    base = {"label": label}
    if "healthy" in key:
        g = GUIDES["healthy"]
        return {**base, "status": "Healthy", "symptoms": g["symptoms"], "causes": "Not applicable.", "risk_factors": "Not applicable.",
                "treatment": g["treatment"], "pesticide": g["pesticide"], "prevention": g["prevention"], "has_specific_guide": True}
    guide = _CANON_GUIDES.get(key)
    specific = guide is not None
    guide = guide or DEFAULT_GUIDE
    cause, risk = _CANON_CAUSES.get(key, ("Not available in this project's reference data.", "Not available in this project's reference data."))
    return {**base, **guide, "causes": cause, "risk_factors": risk, "has_specific_guide": specific}
