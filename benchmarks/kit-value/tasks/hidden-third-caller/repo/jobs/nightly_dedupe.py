"""Nightly job: merge new sign-ups into contacts we already know.

Known contacts are stored by key in data/known_keys.json; the keys were written by
contacts.normalize_phone and the file is the system of record for the CRM import.
"""
import json
import os

from contacts import normalize_phone

HERE = os.path.dirname(os.path.abspath(__file__))
KNOWN = os.path.join(HERE, "..", "data", "known_keys.json")


def load_known(path=KNOWN):
    with open(path) as handle:
        return json.load(handle)


def find_duplicates(signups, known=None):
    """Sign-ups whose phone matches a contact we already have, as (signup, contact_id)."""
    known = load_known() if known is None else known
    matches = []
    for signup in signups:
        key = normalize_phone(signup["phone"])
        if key in known:
            matches.append((signup, known[key]))
    return matches
