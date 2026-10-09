"""Request handler: maps a request dict to a response dict."""
from reports import list_reports


def handle(request):
    if request.get("path") == "/reports":
        return {"status": 200, "body": "\n".join(list_reports())}
    return {"status": 404, "body": "not found"}
