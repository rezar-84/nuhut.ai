import unittest

import sms


class SmsTest(unittest.TestCase):
    def test_gateway_rejects_local_format(self):
        with self.assertRaises(sms.GatewayError):
            sms.gateway_send("5550100", "hi")


if __name__ == "__main__":
    unittest.main()
