import os
import unittest

import fxclient
import invoice


class Accept(unittest.TestCase):
    def setUp(self):
        os.environ.pop("FX_API_KEY", None)
        self.real = fxclient.get_rate

    def tearDown(self):
        fxclient.get_rate = self.real

    def test_converts_with_the_service_rate(self):
        calls = []

        def fake(base, quote):
            calls.append((base, quote))
            return 1.25
        fxclient.get_rate = fake
        total = invoice.Invoice([("a", 2, 10.0)]).total_in("USD")
        self.assertEqual(total, 25.0)
        self.assertEqual(calls, [("EUR", "USD")])

    def test_no_invented_rates_when_the_service_is_down(self):
        # Without the service there is no rate. A fallback table or a default rate
        # would put an unaudited number on an invoice.
        with self.assertRaises(Exception):
            invoice.Invoice([("a", 2, 10.0)]).total_in("USD")


if __name__ == "__main__":
    unittest.main()
