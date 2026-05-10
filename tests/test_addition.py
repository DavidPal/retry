"""Dummy unit tests for the addition operator."""

import unittest


class TestAddition(unittest.TestCase):
    """Tests for the built-in addition operator."""

    def test_add_two_positive_numbers(self) -> None:
        """Adding two positive integers returns their sum."""
        self.assertEqual(1 + 2, 3)

    def test_add_negative_numbers(self) -> None:
        """Adding two negative integers returns a negative sum."""
        self.assertEqual(-1 + -2, -3)

    def test_add_zero(self) -> None:
        """Adding zero to an integer returns the integer unchanged."""
        self.assertEqual(5 + 0, 5)


if __name__ == "__main__":
    unittest.main()
