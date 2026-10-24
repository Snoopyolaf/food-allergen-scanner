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