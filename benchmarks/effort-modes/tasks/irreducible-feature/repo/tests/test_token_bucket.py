import unittest
import token_bucket


class TokenBucketTest(unittest.TestCase):
    def test_module_imports(self):
        self.assertTrue(hasattr(token_bucket, "RateLimiter"))


if __name__ == "__main__":
    unittest.main()
