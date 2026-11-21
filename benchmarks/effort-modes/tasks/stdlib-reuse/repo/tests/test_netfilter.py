import unittest
import netfilter


class NetfilterTest(unittest.TestCase):
    def test_exact_ip_still_matches_host_prefix(self):
        self.assertTrue(netfilter.is_allowed("10.0.0.1", ["10.0.0.1"]))


if __name__ == "__main__":
    unittest.main()
