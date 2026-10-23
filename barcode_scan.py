"""Read a barcode from a photo and look the product up in Open Food Facts."""
import numpy as np
import requests
import zxingcpp

OFF_URL = "https://world.openfoodfacts.org/api/v2/product/{}.json"
FIELDS = "product_name,brands,ingredients_text,allergens_tags,traces_tags"
# Open Food Facts asks every app to identify itself
HEADERS = {"User-Agent": "FoodAllergenScanner/1.0 (github.com/Snoopyolaf/food-allergen-scanner)"}


def read_barcode(image):
    """Return the barcode number found in a PIL image, or None."""
    gray = np.array(image.convert("L"))
    for result in zxingcpp.read_barcodes(gray):
        if result.text.isdigit():
            return result.text
    return None


def lookup_product(barcode):
    """Return (product, status). status is 'ok', 'not_found', or 'error'."""
    try:
        response = requests.get(
            OFF_URL.format(barcode),
            params={"fields": FIELDS},
            headers=HEADERS,
            timeout=10,
        )
        if response.status_code == 404:
            return None, "not_found"
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None, "error"

    if data.get("status") != 1 or "product" not in data:
        return None, "not_found"
    return data["product"], "ok"