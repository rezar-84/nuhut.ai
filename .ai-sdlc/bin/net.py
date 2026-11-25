"""The one place the runtime fetches or posts to a URL (ADR 0003 decision 6).

- https only; a redirect that changes the scheme or the host is refused;
- `post_json` (webhooks, NUHT-034) also takes plain http, but only to 127.0.0.1 or
  localhost and only while NUHUT_ALLOW_HTTP=1, for a local receiver or a test;
- a 5 second timeout and a 1 MB cap on the body;
- an error names only the scheme and host, never the path or query, which may carry a
  token.

Zero third-party dependencies (Python 3.8+ stdlib).
NOTE: Must never contain two literal opening curly braces in a row.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request as urllib_request

TIMEOUT = 5
MAX_BYTES = 1024 * 1024


def origin(url):
    """"scheme://host" of <url>, for messages."""
    try:
        parts = urllib.parse.urlsplit(str(url))
    except ValueError:
        return "(unparseable URL)"
    return "%s://%s" % (parts.scheme or "?", parts.hostname or "?")


LOOPBACK = ("127.0.0.1", "localhost")


def _check(url, loopback_http=False):
    try:
        parts = urllib.parse.urlsplit(str(url))
        host = parts.hostname
    except ValueError:
        raise ValueError("not a URL")
    if parts.scheme == "http" and loopback_http and host in LOOPBACK \
            and os.environ.get("NUHUT_ALLOW_HTTP") == "1":
        return parts
    if parts.scheme != "https" or not host:
        raise ValueError("only https:// URLs are %s, not %s"
                         % ("posted to" if loopback_http else "fetched", origin(url)))
    return parts


class SafeRedirect(urllib_request.HTTPRedirectHandler):
    """Follows a redirect only to the same scheme and host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if new.scheme != old.scheme or (new.hostname or "") != (old.hostname or ""):
            raise ValueError("refused a redirect from %s to %s"
                             % (origin(req.full_url), origin(new.geturl())))
        return urllib_request.HTTPRedirectHandler.redirect_request(
            self, req, fp, code, msg, headers, new.geturl())


def fetch(url, timeout=TIMEOUT, limit=MAX_BYTES):
    """The body of https <url> as bytes. Raises ValueError with a message that names
    only the scheme and host."""
    _check(url)
    opener = urllib_request.build_opener(SafeRedirect())
    request = urllib_request.Request(url, headers={"User-Agent": "nuhut-runtime"})
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(limit + 1)
    except ValueError:
        raise
    except urllib.error.HTTPError as exc:
        raise ValueError("%s answered HTTP %s" % (origin(url), exc.code))
    except Exception as exc:
        raise ValueError("could not fetch from %s (%s)" % (origin(url), exc.__class__.__name__))
    if len(body) > limit:
        raise ValueError("%s sent more than %d bytes" % (origin(url), limit))
    return body


def post_json(url, payload, timeout=TIMEOUT):
    """POST <payload> as JSON to https <url> (or loopback http under NUHUT_ALLOW_HTTP=1)
    and ignore the response body. Raises ValueError with a message that names only the
    scheme and host."""
    _check(url, loopback_http=True)
    opener = urllib_request.build_opener(SafeRedirect())
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = urllib_request.Request(url, data=data, method="POST", headers={
        "User-Agent": "nuhut-runtime", "Content-Type": "application/json"})
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status if hasattr(response, "status") else response.getcode()
    except ValueError as exc:
        # urllib raises ValueError for some malformed URLs with the URL in the text.
        raise ValueError(str(exc) if "refused a redirect" in str(exc)
                         else "could not post to %s (bad URL)" % origin(url))
    except urllib.error.HTTPError as exc:
        raise ValueError("%s answered HTTP %s" % (origin(url), exc.code))
    except Exception as exc:
        raise ValueError("could not post to %s (%s)" % (origin(url), exc.__class__.__name__))
