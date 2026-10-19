"""Contact records and phone normalisation."""
import re


def normalize_phone(raw):
    """Canonical form of a phone number: its digits only. Used as the contact key."""
    return re.sub(r"\D", "", raw or "")


def contact(name, phone):
    return {"name": name, "phone": phone, "key": normalize_phone(phone)}
