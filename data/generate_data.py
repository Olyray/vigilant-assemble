import json
import uuid
import random
import copy
from datetime import datetime, timedelta

random.seed(42)

# --- African names pool ---
FIRST_NAMES = [
    "Mary", "Grace", "Esther", "Ruth", "Mercy", "Faith", "Joy",
    "Blessing", "Patience", "Agnes", "Florence", "Rose", "Sarah",
    "Amina", "Fatima", "Aisha", "Ngozi", "Chiamaka", "Wanjiku", "Nia"
]
LAST_NAMES = [
    "Banda", "Moyo", "Phiri", "Mwale", "Tembo", "Nkosi", "Okafor",
    "Adeyemi", "Muthoni", "Ochieng", "Dlamini", "Ndlovu", "Kamau",
    "Mensah", "Asante", "Diallo", "Traore", "Keita", "Balogun", "Eze"
]
FACILITIES = [
    "Kenyatta National Hospital", "Queen Elizabeth Central Hospital",
    "Muhimbili National Hospital", "Lagos University Teaching Hospital",
    "Korle Bu Teaching Hospital"
]

# --- Misspelling helper ---
def misspell(name):
    """Randomly misspell a name to simulate dirty data."""
    if len(name) < 3:
        return name
    ops = ["swap", "drop", "double"]
    op = random.choice(ops)
    i = random.randint(1, len(name) - 2)
    if op == "swap":
        lst = list(name)
        lst[i], lst[i-1] = lst[i-1], lst[i]
        return "".join(lst)
    elif op == "drop":
        return name[:i] + name[i+1:]
    else:
        return name[:i] + name[i] + name[i:]

# --- Clinical notes templates ---
NORMAL_NOTES = [
    "Patient attended ANC visit. All vitals normal. ART adherence confirmed.",
    "Routine follow-up. Patient reports no issues. Pharmacy refill collected on time.",
    "Antenatal visit. Fetal growth normal. Patient compliant with medication.",
]
RISKY_NOTES = [
    "Patient missed pharmacy pick-up on {date}. Reports transport difficulties.",
    "Patient did not attend scheduled ANC visit. Called — reports financial constraints.",
    "Late presentation to antenatal care (first visit at 32 weeks). Adherence counseling provided.",
    "Patient reports missing ART doses for 5 days due to travel. Counseled on adherence.",
    "Pharmacy records show 2 missed pick-ups in the last 3 months. Patient cites transport challenges.",
    "Patient admitted to skipping medication when feeling well. Re-educated on importance of adherence.",
]

def generate_phone():
    return f"+234-{random.randint(700,999)}-{random.randint(1000,9999)}"

def generate_mothers(n=50):
    mothers = []
    for i in range(n):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        dob = datetime(1985 + random.randint(0, 15), random.randint(1,12), random.randint(1,28))
        facility = random.choice(FACILITIES)
        phone = generate_phone()
        art_id = f"ART-{random.randint(1000,9999)}"
        delivery_date = datetime(2026, 3, random.randint(1,31) if random.random() > 0.3 else 4)
        if delivery_date.month == 4:
            delivery_date = datetime(2026, 4, random.randint(1, 7))

        # Decide risk category
        if i < 20:
            # Unsuppressed — obvious risk
            vl_value = random.randint(1500, 80000)
            vl_date = (delivery_date - timedelta(days=random.randint(7, 60))).isoformat()
            notes = [random.choice(NORMAL_NOTES)]
            risk_category = "OBVIOUS_HIGH"
        elif i < 30:
            # Suppressed but adherence issues — HIDDEN risk (the WOW case)
            vl_value = random.randint(20, 180)
            vl_date = (delivery_date - timedelta(days=random.randint(7, 60))).isoformat()
            note_date = (delivery_date - timedelta(days=random.randint(5, 30))).strftime("%Y-%m-%d")
            notes = [
                t.format(date=note_date) if "{date}" in t else t
                for t in random.sample(RISKY_NOTES, k=random.randint(2, 3))
            ]
            risk_category = "HIDDEN_HIGH"
        elif i < 35:
            # Missing VL — Rule 0 triggers HIGH RISK
            vl_value = None
            vl_date = ""
            notes = [random.choice(NORMAL_NOTES)]
            risk_category = "MISSING_VL"
        elif i < 40:
            # Borderline VL (50-1000) — MODERATE risk tier
            vl_value = random.randint(50, 1000)
            vl_date = (delivery_date - timedelta(days=random.randint(7, 60))).isoformat()
            notes = [random.choice(NORMAL_NOTES)]
            risk_category = "MODERATE"
        else:
            # Low risk
            vl_value = random.randint(0, 40)
            vl_date = (delivery_date - timedelta(days=random.randint(7, 30))).isoformat()
            notes = [random.choice(NORMAL_NOTES)]
            risk_category = "LOW"

        mother = {
            "resourceType": "Patient",
            "id": str(uuid.uuid4()),
            "name": [{"family": last, "given": [first]}],
            "gender": "female",
            "birthDate": dob.strftime("%Y-%m-%d"),
            "telecom": [{"system": "phone", "value": phone}],
            "identifier": [
                {"system": "urn:art-program", "value": art_id}
            ],
            "meta": {
                "facility": facility,
                "delivery_date": delivery_date.isoformat(),
                "risk_category": risk_category
            },
            "viral_load": {
                "resourceType": "Observation",
                "code": {"coding": [{"system": "http://loinc.org", "code": "20447-9", "display": "HIV 1 RNA"}]},
                "valueQuantity": {"value": vl_value, "unit": "copies/mL"} if vl_value is not None else {},
                "effectiveDateTime": vl_date
            },
            "clinical_notes": [
                {
                    "resourceType": "DocumentReference",
                    "content": note,
                    "date": (delivery_date - timedelta(days=random.randint(1, 30))).isoformat()
                }
                for note in notes
            ],
            "condition": {
                "resourceType": "Condition",
                "code": {"coding": [{"system": "http://snomed.info", "code": "86406008", "display": "HIV disease"}]},
                "clinicalStatus": "active"
            }
        }
        mothers.append(mother)
    return mothers

def generate_newborns(mothers):
    newborns = []
    for i, mom in enumerate(mothers):
        first_name = mom["name"][0]["given"][0]
        last_name = mom["name"][0]["family"]
        facility = mom["meta"]["facility"]
        delivery = mom["meta"]["delivery_date"]
        phone = mom["telecom"][0]["value"]

        # --- Create "dirty" infant name ---
        naming_style = random.choice(["baby_of", "baby_of_misspell", "unnamed", "first_name_only"])
        if naming_style == "baby_of":
            infant_name = {"family": last_name, "given": [f"Baby of {first_name}"]}
        elif naming_style == "baby_of_misspell":
            infant_name = {"family": misspell(last_name), "given": [f"Baby of {first_name}"]}
        elif naming_style == "unnamed":
            infant_name = {"family": "", "given": [random.choice(["Unnamed Male", "Unnamed Female", "Baby Boy", "Baby Girl"])]}
        else:
            infant_name = {"family": last_name, "given": [first_name]}

        # Shared Phone Penalty test: some mothers share a phone number
        # First 5 mothers share a common phone to test the penalty logic
        if i < 5:
            phone = "+234-800-SHARED"
            mom["telecom"] = [{"system": "phone", "value": phone}]

        # Some newborns share mother's phone, some don't
        infant_phone = phone if random.random() > 0.3 else ""

        newborn = {
            "resourceType": "Patient",
            "id": str(uuid.uuid4()),
            "name": [infant_name],
            "gender": random.choice(["male", "female"]),
            "birthDate": delivery[:10],
            "telecom": [{"system": "phone", "value": infant_phone}] if infant_phone else [],
            "meta": {
                "facility": facility if random.random() > 0.1 else random.choice(FACILITIES),
                "mother_id": mom["id"]  # ground truth — NOT visible to agents
            }
        }
        newborns.append(newborn)
    return newborns

if __name__ == "__main__":
    mothers = generate_mothers(50)
    newborns = generate_newborns(mothers)

    with open("data/mothers.json", "w") as f:
        json.dump(mothers, f, indent=2, default=str)
    with open("data/newborns.json", "w") as f:
        json.dump(newborns, f, indent=2, default=str)

    print(f"Generated {len(mothers)} mothers and {len(newborns)} newborns")
    print(f"  Obvious high risk: {sum(1 for m in mothers if m['meta']['risk_category']=='OBVIOUS_HIGH')}")
    print(f"  Hidden high risk:  {sum(1 for m in mothers if m['meta']['risk_category']=='HIDDEN_HIGH')}")
    print(f"  Missing VL (Rule 0): {sum(1 for m in mothers if m['meta']['risk_category']=='MISSING_VL')}")
    print(f"  Moderate risk:     {sum(1 for m in mothers if m['meta']['risk_category']=='MODERATE')}")
    print(f"  Low risk:          {sum(1 for m in mothers if m['meta']['risk_category']=='LOW')}")
    print(f"  Shared phone infants: {sum(1 for n in newborns if any(t.get('value') == '+234-800-SHARED' for t in n.get('telecom', [])))}")
