
import json
from pathlib import Path

path = Path(__file__).parent / "data" / "experts.json"
experts = json.loads(path.read_text(encoding="utf-8-sig"))

# Contacts transcribed from the ICAR Telephone Directory 2026.
# Confirm details before relying on them.
contacts = {
    "Chitradurga": {
        "name": "Dr. Parashurama Chandravamshi",
        "phone": "9844103949 / 9480838201",
        "email": "parashuramcv@gmail.com",
    },
    "Dakshina Kannada": {
        "name": "Dr. T J Ramesha",
        "phone": "8762543060 / 8794706468",
        "email": "kvkdkmlr@gmail.com",
    },
    "Davanagere": {
        "name": "Dr. Devaraja T N",
        "phone": "08192-263462 / 9449856876",
        "email": "dvgkvk@yahoo.com",
    },
    "Dharwad": {
        "name": "Dr. K P Gundannavar",
        "phone": "9448495342 / 9535993257",
        "email": "kvkdwd@uasd.in",
    },
    "Gadag": {
        "name": "Dr. Sudha V Mankani",
        "phone": "9480552339",
        "email": "kvkhulkoti@gmail.com",
    },
    "Hassan": {
        "name": "Dr. Rajegowda",
        "phone": "9449866932 / 9019065158",
        "email": "hassan.kvk@gmail.com",
    },
    "Haveri": {
        "name": "Dr. A H Biradar",
        "phone": "9448495338 / 7829891560",
        "email": "kvkhvr@uasd.in",
    },
    "Kalaburagi": {
        "name": "Dr. Raju G Teggelli",
        "phone": "9480696315 / 9448408397",
        "email": "kvkglb.in@gmail.com",
    },
    "Kodagu": {
        "name": "Dr. Muralidhara B M",
        "phone": "7259240293 / 9005847283",
        "email": "iihrkvkg@gmail.com",
    },
    "Kolar": {
        "name": "Dr. Shivanand Hongal",
        "phone": "9480696395 / 8147572913",
        "email": "kvkkolar2012@gmail.com",
    },
    "Koppal": {
        "name": "Dr. Raghavendra Yaligar",
        "phone": "9480696316 / 8217440909",
        "email": "pckvkkoppal@uasraichur.edu.in",
    },
    "Mandya": {
        "name": "Dr. Kamalabai Koodagi",
        "phone": "8762626880 / 9449864250",
        "email": "kvkmandya@gmail.com",
    },
    "Mysuru": {
        "name": "Dr. B N Gnanesh",
        "phone": "7483699146 / 7893900859",
        "email": "jsskvk@gmail.com",
    },
    "Yadgir": {
        "name": "Dr. Jaiprakash Narayan R P",
        "phone": "9480696349 / 8073537388",
        "email": "icarkvkawadimatti@gmail.com",
    },
}

source = (
    "https://icar.org.in/sites/default/files/"
    "Circulars/ICAR-Telephone-Directory-2026-1.pdf"
)

updated = []

for entry in experts:
    region = str(entry.get("region", "")).casefold()
    district = next(
        (d for d in contacts if d.casefold() in region),
        None,
    )

    if not district:
        continue

    contact = contacts[district]
    entry.update({
        "name": contact["name"],
        "organisation": f"Krishi Vigyan Kendra, {district}",
        "specialty": "Agricultural extension and crop advisory",
        "email": contact["email"],
        "phone": contact["phone"],
        "url": source,
    })
    updated.append(district)

path.write_text(
    json.dumps(experts, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("Batch update complete.")
print("Updated districts:", ", ".join(updated))
print("Updated contacts:", len(updated))
print("Total directory entries:", len(experts))
print("Other entries remain unchanged.")
