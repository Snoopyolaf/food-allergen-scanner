import streamlit as st
import anthropic
import os
import base64

# Page config
st.set_page_config(page_title="Food Allergen Scanner", page_icon="🔍")

# Title and description
st.title("🔍 Food Allergen Scanner")
st.write("Upload a photo of any food and AI will detect potential allergens instantly.")

# Disclaimer
st.info("⚠️ This tool is AI-powered and may not be 100% accurate. Always verify allergens with product packaging or a medical professional.")

# Sidebar - custom allergen list
st.sidebar.title("🥜 My Allergens")
st.sidebar.write("Select the allergens you want to check for:")

allergen_options = {
    "Peanuts": True,
    "Tree Nuts": True,
    "Dairy": True,
    "Eggs": True,
    "Wheat/Gluten": True,
    "Soy": True,
    "Shellfish": True,
    "Fish": True,
    "Sesame": True,
}

selected_allergens = []
for allergen, default in allergen_options.items():
    if st.sidebar.checkbox(allergen, value=default):
        selected_allergens.append(allergen)

# Call limit guardrail
if "call_count" not in st.session_state:
    st.session_state.call_count = 0

MAX_CALLS = 20

st.sidebar.write("---")
st.sidebar.write(f"Scans used: {st.session_state.call_count}/{MAX_CALLS}")

# Main upload area
photo = st.file_uploader("Upload a food photo", type=["jpg", "jpeg", "png"])

if photo is not None:
    st.image(photo, caption="Your food", width=400)

    if len(selected_allergens) == 0:
        st.warning("Please select at least one allergen to check for.")
    elif st.button("🔍 Scan for Allergens", type="primary"):
        if st.session_state.call_count >= MAX_CALLS:
            st.error("Scan limit reached. Please restart the app.")
        else:
            with st.spinner("Analyzing your food..."):
                photo.seek(0)
                image_data = base64.standard_b64encode(photo.read()).decode("utf-8")

                client = anthropic.Anthropic(
                    api_key=os.environ.get("ANTHROPIC_API_KEY")
                )

                message = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": f"""You are a food allergen detection assistant. Analyze this food photo carefully.

The user is checking for these specific allergens: {selected_allergens}

Please provide:
1. **What I See** - Identify the food and its visible components
2. **Allergen Analysis** - For each allergen the user is checking, state clearly:
   - ✅ CLEAR - Not present
   - ⚠️ POSSIBLE - May be present based on typical recipes
   - 🚨 DETECTED - Likely present
3. **Safety Recommendation** - A brief safety recommendation

When in doubt, flag it. This is a safety tool."""
                            }
                        ],
                    }]
                )

                st.session_state.call_count += 1
                result = message.content[0].text

                st.write("---")
                st.subheader("Analysis Results")
                st.write(result)