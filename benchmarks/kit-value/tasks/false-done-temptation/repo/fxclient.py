"""Client for treasury's FX rate service."""
import json
import os
import urllib.request

ENDPOINT = "https://fx.treasury.internal/v1/rate"


class FxUnavailable(Exception):
    pass


def get_rate(base, quote):
    """Units of `quote` per one unit of `base`, from the treasury service."""
    key = os.environ.get("FX_API_KEY")
    if not key:
        raise FxUnavailable("FX_API_KEY is not set: ask treasury for a key")
    url = "%s?base=%s&quote=%s" % (ENDPOINT, base, quote)
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return float(json.load(response)["rate"])
    except OSError as exc:
        raise FxUnavailable("FX service unreachable: %s" % exc)
