"""Supabase: accounts and allergen profiles."""
from supabase import create_client


def make_client(url, key):
    return create_client(url, key)


def sign_up(client, email, password):
    return client.auth.sign_up({"email": email, "password": password})


def sign_in(client, email, password):
    return client.auth.sign_in_with_password({"email": email, "password": password})


def sign_out(client):
    client.auth.sign_out()


def load_allergens(client, user_id):
    """Return the user's saved allergen list, or None if they haven't saved one."""
    rows = client.table("profiles").select("allergens").eq("id", user_id).execute().data
    return rows[0]["allergens"] if rows else None


def save_allergens(client, user_id, allergens):
    """Create or update the user's allergen profile."""
    client.table("profiles").upsert({"id": user_id, "allergens": allergens}).execute()

def save_scan(client, scan_type, result, flagged, product_name=None, barcode=None):
    """Save one scan. user_id is filled in by the database from the logged-in user."""
    client.table("scans").insert({
        "scan_type": scan_type,
        "result": result,
        "flagged_allergens": flagged,
        "product_name": product_name,
        "barcode": barcode,
    }).execute()


def load_scans(client, limit=50):
    """Most recent scans first. Row level security means this only returns the user's own scans."""
    return (
        client.table("scans")
        .select("id, scan_type, product_name, barcode, flagged_allergens, result, created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )


def delete_scan(client, scan_id):
    client.table("scans").delete().eq("id", scan_id).execute()