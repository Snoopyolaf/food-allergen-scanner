"""Send a food photo to Claude and get an allergen analysis back."""
import base64
import io

import anthropic

MODEL = "claude-sonnet-4-6"
MAX_SIDE = 1568  


def _encode(image):
    image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")


def _build_prompt(selected):
    return f"""You are a food allergen detection assistant. Analyze this food photo carefully.

The user is checking for these allergens: {", ".join(selected)}

Provide:
1. **What I See** - Identify the food and its visible components
2. **Allergen Analysis** - For each allergen above, state:
   - 🟢 NOT VISIBLE - no sign of it
   - 🟡 POSSIBLE - may be present based on typical recipes for this dish
   - 🔴 LIKELY - likely present
3. **Safety Recommendation** - One or two sentences

When in doubt, flag it. Hidden ingredients like sauces, oils and shared cookware cannot be seen in a photo, so never call a food safe.

End your response with exactly one final line in this format:
FLAGGED: <comma-separated allergens you marked POSSIBLE or LIKELY, or NONE>"""


def _split_flagged(text, selected):
    """Pull the FLAGGED line off the end and turn it into a list."""
    lines = text.strip().splitlines()
    flagged = []
    last = lines[-1].strip("* ") if lines else ""
    if last.upper().startswith("FLAGGED"):
        names = last.split(":", 1)[-1]
        wanted = {name.strip(" *.").lower() for name in names.split(",")}
        flagged = [a for a in selected
                   if a.lower() in wanted or a.split("/")[0].lower() in wanted]
        text = "\n".join(lines[:-1])
    return text, flagged


def scan_photo(image, selected, api_key):
    """Return (analysis_text, flagged_allergens)."""
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg", "data": _encode(image)}},
                {"type": "text", "text": _build_prompt(selected)},
            ],
        }],
    )
    return _split_flagged(message.content[0].text, selected)