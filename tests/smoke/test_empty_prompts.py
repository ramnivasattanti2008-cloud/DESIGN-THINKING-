"""
Smoke tests for empty, whitespace, and invalid prompt inputs.
Ensures MIRROR never initiates hardware perception or planning on null/malformed goals.
"""

import unittest
from tests.engine.verification_engine import MirrorVerificationEngine

class TestEmptyAndInvalidPrompts(unittest.TestCase):
    def setUp(self):
        self.engine = MirrorVerificationEngine()

    def test_null_prompt_rejected(self):
        is_valid, msg = self.engine.validate_prompt(None)
        self.assertFalse(is_valid)
        self.assertIn("null", msg.lower())

    def test_empty_string_rejected(self):
        is_valid, msg = self.engine.validate_prompt("")
        self.assertFalse(is_valid)
        self.assertIn("empty", msg.lower())

    def test_whitespace_only_rejected(self):
        is_valid, msg = self.engine.validate_prompt("   \t  \n  ")
        self.assertFalse(is_valid)
        self.assertIn("whitespace", msg.lower())

    def test_single_word_rejected_as_insufficient(self):
        is_valid, msg = self.engine.validate_prompt("fix")
        self.assertFalse(is_valid)
        self.assertIn("brief", msg.lower())

    def test_non_actionable_greetings_rejected(self):
        for phrase in ["hi", "hello", "asdf", "test"]:
            is_valid, msg = self.engine.validate_prompt(phrase)
            self.assertFalse(is_valid, f"Phrase '{phrase}' should have been rejected")

    def test_valid_actionable_prompt_accepted(self):
        is_valid, msg = self.engine.validate_prompt("Inspect the wall power socket for loose wiring")
        self.assertTrue(is_valid)
        self.assertIn("valid", msg.lower())

if __name__ == "__main__":
    unittest.main()
