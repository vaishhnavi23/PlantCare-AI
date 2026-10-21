
import json
from pathlib import Path

file_path = Path(__file__).parent / "data" / "experts.json"

# Keep the existing expert contacts
experts = json.loads(file_path.read_text(encoding="utf-8-sig"))

districts = [
    "Bagalkote",
    "Ballari",
    "Belagavi",
    "Bengaluru Rural",
    "Bengaluru Urban",
    "Bidar",
    "Chamarajanagar",
    "Chikkaballapura",
    "Chikkamagaluru",
    "Chitradurga",
    "Dakshina Kannada",
    "Davanagere",
    "Dharwad",
    "Gadag",
    "Hassan",
    "Haveri",
    "Kalaburagi",
    "Kodagu",
    "Kolar",
    "Koppal",
    "Mandya",
    "Mysuru",
    "Raichur",
    "Ramanagara",
    "Shivamogga",
    "Tumakuru",
    "Udupi",
    "Uttara Kannada",
    "Vijayapura",
    "Yadgir",
    "Vijayanagara",
]

# Add district entries only when not already represented.
# Unverified contact details are deliberately left blank.
existing_regions = {
    str(entry.get("region", "")).strip().casefold()
    for entry in experts
}

# Also avoid adding a duplicate Davanagere placeholder
existing_regions.add("davanagere")


for district in districts:
    if district.casefold() in existing_regions:
        continue

    experts.append({
        "name": f"{district} agricultural contact — verification needed",
        "organisation": (
            f"Find the official district agriculture office "
            f"or Krishi Vigyan Kendra for {district}"
        ),
        "specialty": "Agricultural extension and crop advisory",
        "region": district,
        "email": "",
        "phone": "",
        "url": "https://raitamitra.karnataka.gov.in/",
    })

file_path.write_text(
    json.dumps(experts, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("Directory updated successfully.")
print("Total contacts/entries:", len(experts))
print("Districts included:", len(districts))
print("File:", file_path)
