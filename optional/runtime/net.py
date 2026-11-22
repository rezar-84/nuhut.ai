"""The one place the runtime fetches a URL (ADR 0003 decision 6).

- https only; a redirect that changes the scheme or the host is refused;
- a 5 second timeout and a 1 MB cap on the body;
- an error names only the scheme and host, never the path or query, which may carry a
  token.

Zero third-party dependencies (Python 3.8+ stdlib).
NOTE: Must never contain two literal opening curly braces in a row.
"""

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


def _check(url):
    try:
        parts = urllib.parse.urlsplit(str(url))
    except ValueError:
        raise ValueError("not a URL")
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("only https:// URLs are fetched, not %s" % origin(url))
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
