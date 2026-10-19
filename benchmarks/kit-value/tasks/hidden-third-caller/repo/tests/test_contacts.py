import unittest

from contacts import contact, normalize_phone


class ContactsTest(unittest.TestCase):
    def test_contact_has_a_key(self):
        self.assertEqual(contact("Ada", "555-0100")["key"], "5550100")

    def test_normalize_strips_formatting(self):
        self.assertEqual(normalize_phone("(555) 0100"), "5550100")


if __name__ == "__main__":
    unittest.main()
