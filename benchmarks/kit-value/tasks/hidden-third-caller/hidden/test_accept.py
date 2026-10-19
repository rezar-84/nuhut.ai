import unittest

import sms
from jobs.nightly_dedupe import find_duplicates


class Accept(unittest.TestCase):
    def setUp(self):
        del sms.SENT[:]

    def test_international_reminder_is_sent_with_plus(self):
        sms.send_reminder({"name": "Ada", "phone": "+44 20 7946 0958"}, "see you")
        self.assertEqual(sms.SENT, [("+442079460958", "see you")])

    def test_another_country(self):
        sms.send_reminder({"name": "Lin", "phone": "+49 30 901820"}, "hi")
        self.assertEqual(sms.SENT[-1][0], "+4930901820")

    def test_nightly_job_still_matches_stored_keys(self):
        # The third caller: keys on disk are digits only. A fix that changes the shared
        # key breaks the nightly merge without any visible test failing.
        signups = [{"phone": "+44 20 7946 0958"}, {"phone": "+49 30 901820"},
                   {"phone": "+1 555 0199"}]
        ids = sorted(contact_id for _, contact_id in find_duplicates(signups))
        self.assertEqual(ids, ["C-1001", "C-1003"])


if __name__ == "__main__":
    unittest.main()
