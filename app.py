from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic
import streamlit as st
from PIL import Image

from allergens import ALLERGENS, STATUS_TEXT, check_product, flagged_from, summary_text
from barcode_scan import lookup_product, read_barcode
from db import (delete_scan, load_allergens, load_scans, make_client,
                save_allergens, save_scan, sign_in, sign_out, sign_up)
from photo_scan import scan_photo

MAX_PHOTO_SCANS = 20
LOCAL_TZ = ZoneInfo("America/Los_Angeles")

st.set_page_config(page_title="Trace Check")
st.title("Trace Check")
st.write("Check a meal photo or a packaged food's barcode for allergens.")
st.info("⚠️ AI and database results can be wrong or incomplete. Always check the package label, and ask staff when eating out.")


if "db" not in st.session_state:
    st.session_state.db = make_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])
    st.session_state.user = None
db = st.session_state.db

if "scan_count" not in st.session_state:
    st.session_state.scan_count = 0

for a in ALLERGENS:
    st.session_state.setdefault(f"allergen_{a}", True)


def set_checkboxes(allergens):
    for a in ALLERGENS:
        st.session_state[f"allergen_{a}"] = a in allergens


def current_selection():
    return [a for a in ALLERGENS if st.session_state[f"allergen_{a}"]]


def save_to_history(**scan):
    """Save a scan if signed in. A failed save never breaks the scan itself."""
    if not st.session_state.user:
        st.caption("Sign in to save scans to your history.")
        return
    try:
        save_scan(db, **scan)
        st.caption("✓ Saved to your history.")
    except Exception:
        st.caption("⚠️ Couldn't save this scan to your history.")


def show_product_results(product, selected):
    """Show a barcode product's allergen check. Returns the results, or None if there's no data."""
    name = product.get("product_name") or "Unknown product"
    brand = product.get("brands")
    st.subheader(f"{name} ({brand})" if brand else name)

    if not (product.get("ingredients_text") or product.get("allergens_tags")):
        st.warning("This product has no ingredient or allergen data in the database. Check the package label directly.")
        return None

    results = check_product(product, selected)
    for allergen, status in results.items():
        message = STATUS_TEXT[status].format(allergen)
        if status == "DETECTED":
            st.error(message)
        elif status == "NOT LISTED":
            st.success(message)
        else:
            st.warning(message)

    with st.expander("Full ingredient list"):
        st.write(product.get("ingredients_text") or "Not available")
    st.caption("Data from Open Food Facts, a community-edited database. Recipes change, so always check the package.")
    return results



st.sidebar.title("👤 Account")
if st.session_state.user:
    st.sidebar.write(f"Signed in as **{st.session_state.user.email}**")
    if st.sidebar.button("Sign out"):
        sign_out(db)
        st.session_state.user = None
        set_checkboxes(ALLERGENS)
        st.rerun()
else:
    st.sidebar.caption("Optional. Sign in to save your allergen profile and scan history. Everything else works without an account.")
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


st.sidebar.divider()
st.sidebar.title("My Allergens")
selected = [a for a in ALLERGENS if st.sidebar.checkbox(a, key=f"allergen_{a}")]
if st.session_state.user and st.sidebar.button("Save my allergens"):
    save_allergens(db, st.session_state.user.id, selected)
    st.sidebar.success("Saved!")
st.sidebar.divider()
st.sidebar.caption(f"Photo scans used: {st.session_state.scan_count}/{MAX_PHOTO_SCANS}")

photo_tab, barcode_tab, history_tab = st.tabs(["Food Photo", "Barcode", "History"])


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
                    save_to_history(scan_type="photo", result=text, flagged=flagged)
                except anthropic.APIError:
                    st.error("The AI scan failed. Please try again in a moment.")


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
                results = show_product_results(product, selected)
                if results:
                    save_to_history(
                        scan_type="barcode",
                        product_name=product.get("product_name"),
                        barcode=barcode,
                        flagged=flagged_from(results),
                        result=summary_text(results),
                    )


with history_tab:
    if not st.session_state.user:
        st.info("Sign in from the sidebar to save and view your scan history.")
    else:
        try:
            scans = load_scans(db)
        except Exception:
            scans = None
            st.error("Couldn't load your history. Try again in a moment.")

        if scans == []:
            st.write("No scans yet. Your photo and barcode scans will show up here.")

        for scan in scans or []:
            when = datetime.fromisoformat(scan["created_at"]).astimezone(LOCAL_TZ).strftime("%b %d, %I:%M %p")
            if scan["scan_type"] == "photo":
                icon, title = "📸", "Food photo"
            else:
                icon, title = "🏷️", scan["product_name"] or f"Barcode {scan['barcode']}"
            flags = ", ".join(scan["flagged_allergens"]) or "No allergens flagged"
            with st.expander(f"{icon} {title} · {when} · {flags}"):
                st.markdown(scan["result"])
                if st.button("Delete", key=f"del_{scan['id']}"):
                    delete_scan(db, scan["id"])
                    st.rerun()