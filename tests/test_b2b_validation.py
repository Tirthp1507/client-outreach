"""Unit tests for B2B DataValidationEngine and accuracy assurance gate."""

import unittest
from b2b.models import BusinessRecord, BusinessStatus
from b2b.validator import DataValidationEngine, ValidationResult


class TestB2BValidationEngine(unittest.TestCase):

    def setUp(self) -> None:
        self.validator = DataValidationEngine()

    def test_phone_validation_valid_mobile(self) -> None:
        passed, score, _, _ = self.validator._verify_phone_integrity("+91 98250 12345")
        self.assertTrue(passed)
        self.assertGreaterEqual(score, 20.0)

    def test_phone_validation_invalid(self) -> None:
        passed, score, _, _ = self.validator._verify_phone_integrity("123")
        self.assertFalse(passed)
        self.assertLessEqual(score, 5.0)

    def test_email_validation_valid_format(self) -> None:
        passed, score, _, _, _ = self.validator._verify_email_deliverability("test@example.com")
        self.assertTrue(passed)
        self.assertGreaterEqual(score, 15.0)

    def test_email_validation_unlisted(self) -> None:
        passed, score, _, _, _ = self.validator._verify_email_deliverability(None)
        self.assertTrue(passed)
        self.assertGreaterEqual(score, 20.0)

    def test_full_business_record_validation(self) -> None:
        record = BusinessRecord(
            id="biz_test_valid_1",
            name="Sanjivani Clinic",
            category="clinic",
            city="Ahmedabad",
            phone="+91 98252 85799",
            website=None,
            status=BusinessStatus.DISCOVERED,
        )
        res = self.validator.validate(record, no_website_only=True)
        self.assertIsInstance(res, ValidationResult)
        self.assertTrue(record.is_validated)
        self.assertGreaterEqual(record.validation_score, 75.0)
        self.assertIn("business_id", record.validation_details)


if __name__ == "__main__":
    unittest.main()
