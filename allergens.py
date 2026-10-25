"""Allergen definitions and the product allergen check."""

ALLERGENS = [
    "Peanuts", "Tree Nuts", "Dairy", "Eggs", "Wheat/Gluten",
    "Soy", "Shellfish", "Fish", "Sesame",
]


OFF_TAGS = {
    "Peanuts": ["en:peanuts"],
    "Tree Nuts": ["en:nuts"],
    "Dairy": ["en:milk"],
    "Eggs": ["en:eggs"],
    "Wheat/Gluten": ["en:gluten"],
    "Soy": ["en:soybeans"],
    "Shellfish": ["en:crustaceans", "en:molluscs"],
    "Fish": ["en:fish"],
    "Sesame": ["en:sesame-seeds"],
}


KEYWORDS = {
    "Peanuts": ["peanut", "groundnut"],
    "Tree Nuts": ["almond", "cashew", "walnut", "pecan", "hazelnut", "pistachio",
                  "macadamia", "brazil nut", "pine nut", "praline", "marzipan"],
    "Dairy": ["milk", "whey", "casein", "butter", "cheese", "cream",
              "lactose", "yogurt", "ghee"],
    "Eggs": ["egg", "albumin", "mayonnaise"],
    "Wheat/Gluten": ["wheat", "gluten", "barley", "rye", "malt", "semolina", "spelt"],
    "Soy": ["soy", "soya", "edamame", "tofu"],
    "Shellfish": ["shrimp", "crab", "lobster", "prawn", "crayfish", "clam",
                  "oyster", "mussel", "scallop", "squid"],
    "Fish": ["fish", "anchovy", "salmon", "tuna", "cod", "sardine", "tilapia"],
    "Sesame": ["sesame", "tahini"],
}


def check_product(product, selected):
    """Return {allergen: status} for each allergen the user selected."""
    allergen_tags = product.get("allergens_tags") or []
    trace_tags = product.get("traces_tags") or []
    ingredients = (product.get("ingredients_text") or "").lower()

    results = {}
    for allergen in selected:
        tags = OFF_TAGS[allergen]
        if any(tag in allergen_tags for tag in tags):
            results[allergen] = "DETECTED"
        elif any(tag in trace_tags for tag in tags):
            results[allergen] = "MAY CONTAIN"
        elif any(word in ingredients for word in KEYWORDS[allergen]):
            results[allergen] = "POSSIBLE"
        else:
            results[allergen] = "NOT LISTED"
    return results

STATUS_TEXT = {
    "DETECTED": "🔴 **{}**: listed as an allergen",
    "MAY CONTAIN": "🟠 **{}**: may contain traces (cross-contamination warning)",
    "POSSIBLE": "🟡 **{}**: possible, an ingredient name suggests it",
    "NOT LISTED": "🟢 **{}**: not listed",
}


def flagged_from(results):
    """Allergens that got any warning."""
    return [a for a, status in results.items() if status != "NOT LISTED"]


def summary_text(results):
    """One line per allergen, for saving to history."""
    return "\n\n".join(STATUS_TEXT[status].format(a) for a, status in results.items())