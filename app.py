import anthropic
import streamlit as st
from PIL import Image

from allergens import ALLERGENS, check_product
from barcode_scan import lookup_product, read_barcode
from photo_scan import scan_photo
from db import load_allergens, make_client, save_allergens, sign_in, sign_out, sign_up

MAX_PHOTO_SCANS = 20

st.set_page_config(page_title="Food Allergen Scanner", page_icon="🔍")
st.title("🔍 Food Allergen Scanner")
st.write("Check a meal photo or a packaged food's barcode for allergens.")
st.info("⚠️ AI and database results can be wrong or incomplete. Always check the package label, and ask staff when eating out.")

# ---------- Database client: one per browser session ----------
if "db" not in st.session_state:
    st.session_state.db = make_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])
    st.session_state.user = None
db = st.session_state.db

# Each allergen checkbox remembers its state under a key like "allergen_Peanuts"
for a in ALLERGENS:
    st.session_state.setdefault(f"allergen_{a}", True)


def set_checkboxes(allergens):
    for a in ALLERGENS:
        st.session_state[f"allergen_{a}"] = a in allergens


def current_selection():
    return [a for a in ALLERGENS if st.session_state[f"allergen_{a}"]]


# ---------- Sidebar: account (optional) ----------
st.sidebar.title("👤 Account")
if st.session_state.user:
    st.sidebar.write(f"Signed in as **{st.session_state.user.email}**")
    if st.sidebar.button("Sign out"):
        sign_out(db)
        st.session_state.user = None
        set_checkboxes(ALLERGENS)
        st.rerun()
else:
    st.sidebar.caption("Optional. Sign in to save your allergen profile. Everything works without an account.")
    with st.sidebar.form("auth_form"):
        email = st.text_input("Email")
        password = st.text_input("Password (6+ characters)", type="password")
        col1, col2 = st.columns(2)
        do_sign_in = col1.form_submit_button("Sign in")
        do_sign_up = col2.form_submit_button("Sign up")
    if do_sign_in or do_sign_up:
        action = "sign in" if do_sign_in else "sign up"
        try:
            res = sign_in(db, email, password) if do_sign_in else sign_up(db, email, password)
            if res.session is None:
                st.sidebar.info("Check your email to confirm your account, then sign in.")
            else:
                st.session_state.user = res.user
                saved = load_allergens(db, res.user.id)
                if saved is None:
                    save_allergens(db, res.user.id, current_selection())
                else:
                    set_checkboxes(saved)
                st.rerun()
        except Exception as e:
            st.sidebar.error(f"Couldn't {action}: {e}")

# ---------- Sidebar: allergen profile ----------
st.sidebar.divider()
st.sidebar.title("🥜 My Allergens")
selected = [a for a in ALLERGENS if st.sidebar.checkbox(a, key=f"allergen_{a}")]
if st.session_state.user and st.sidebar.button("💾 Save my allergens"):
    save_allergens(db, st.session_state.user.id, selected)
    st.sidebar.success("Saved!")

if "scan_count" not in st.session_state:
    st.session_state.scan_count = 0
st.sidebar.divider()
st.sidebar.caption(f"Photo scans used: {st.session_state.scan_count}/{MAX_PHOTO_SCANS}")


def show_product_results(product, selected):
    name = product.get("product_name") or "Unknown product"
    brand = product.get("brands")
    st.subheader(f"{name} ({brand})" if brand else name)

    if not (product.get("ingredients_text") or product.get("allergens_tags")):
        st.warning("This product has no ingredient or allergen data in the database. Check the package label directly.")
        return

    for allergen, status in check_product(product, selected).items():
        if status == "DETECTED":
            st.error(f"🚨 **{allergen}**: listed as an allergen")
        elif status == "MAY CONTAIN":
            st.warning(f"⚠️ **{allergen}**: may contain traces (cross-contamination warning)")
        elif status == "POSSIBLE":
            st.warning(f"⚠️ **{allergen}**: possible, an ingredient name suggests it")
        else:
            st.success(f"✅ **{allergen}**: not listed")

    with st.expander("Full ingredient list"):
        st.write(product.get("ingredients_text") or "Not available")
    st.caption("Data from Open Food Facts, a community-edited database. Recipes change, so always check the package.")


photo_tab, barcode_tab = st.tabs(["📸 Food Photo", "🏷️ Barcode"])

# ---------- Tab 1: food photo (Claude vision) ----------
with photo_tab:
    photo = st.file_uploader("Upload a food photo", type=["jpg", "jpeg", "png", "webp"], key="photo_file")
    if photo:
        st.image(photo, width=400)
        if not selected:
            st.warning("Select at least one allergen in the sidebar.")
        elif st.button("Scan for Allergens", type="primary", key="photo_btn"):
            if st.session_state.scan_count >= MAX_PHOTO_SCANS:
                st.error("Scan limit reached for this session.")
            else:
                try:
                    with st.spinner("Analyzing your food..."):
                        text, flagged = scan_photo(Image.open(photo), selected,
                                                   st.secrets["ANTHROPIC_API_KEY"])
                    st.session_state.scan_count += 1
                    st.subheader("Analysis Results")
                    st.markdown(text)
                except anthropic.APIError:
                    st.error("The AI scan failed. Please try again in a moment.")

# ---------- Tab 2: barcode (Open Food Facts) ----------
with barcode_tab:
    st.write("Upload a clear, close-up photo of the barcode, or type the number printed under it.")
    code_photo = st.file_uploader("Barcode photo", type=["jpg", "jpeg", "png", "webp"], key="barcode_file")
    typed = st.text_input("Or type the barcode number", key="barcode_text").strip()

    barcode = None
    if typed:
        barcode = typed
    elif code_photo:
        barcode = read_barcode(Image.open(code_photo))
        if barcode:
            st.success(f"Barcode found: {barcode}")
        else:
            st.warning("Couldn't read a barcode. Try a closer, sharper photo with good light, or type the number.")

    if barcode:
        if not barcode.isdigit():
            st.error("Barcodes are numbers only. Check what you typed.")
        elif not selected:
            st.warning("Select at least one allergen in the sidebar.")
        elif st.button("Look up product", type="primary", key="barcode_btn"):
            with st.spinner("Looking up product..."):
                product, status = lookup_product(barcode)
            if status == "error":
                st.error("Couldn't reach the product database. Check your connection and try again.")
            elif status == "not_found":
                st.warning("This product isn't in the database yet. Check the package label, or photograph the ingredient list in the Food Photo tab.")
            else:
                show_product_results(product, selected)