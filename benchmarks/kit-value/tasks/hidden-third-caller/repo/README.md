# Contacts

Customer contacts, SMS reminders, and the nightly jobs that keep the contact list clean.

- `contacts.py` — contact records and phone normalisation
- `sms.py` — sends reminders through the gateway
- `jobs/` — scheduled jobs (run nightly by cron)

Tests: `python3 -m unittest discover -s tests`
