"""SMS reminders through the gateway."""
from contacts import normalize_phone

SENT = []  # the gateway client in production; a list here


class GatewayError(Exception):
    pass


def gateway_send(to, text):
    if not to.startswith("+"):
        raise GatewayError("gateway rejects %r: not in international format" % to)
    SENT.append((to, text))


def send_reminder(contact, text):
    gateway_send(normalize_phone(contact["phone"]), text)
