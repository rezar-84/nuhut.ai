import unittest

from checkout import checkout_total


class CheckoutTest(unittest.TestCase):
    def test_no_discount(self):
        self.assertEqual(checkout_total([20.0, 30.0]), 50.0)


if __name__ == "__main__":
    unittest.main()
