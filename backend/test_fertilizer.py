from app.services.fertilizer import recommend, FertInputError

tests = ["usha", "pavan", "tomato", "rice"]

for crop in tests:
    try:
        recommend(crop, {"N": "medium", "P": None, "K": None}, None)
        print(crop, "ACCEPTED")
    except FertInputError as error:
        print(crop, "REJECTED:", error)