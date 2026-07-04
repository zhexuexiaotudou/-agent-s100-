import unittest

from tools.token_budget.privacy_redactor import PrivacyRedactor, find_private_leaks


class PrivacyRedactorTest(unittest.TestCase):
    def test_redacts_path_filename_and_contact(self):
        text = (
            "Read /mnt/nas/openclaw/Personal/家庭/身份证扫描件.pdf "
            "and email zhangsan@example.com or call 13812345678."
        )
        result = PrivacyRedactor().redact(text)
        self.assertIn("<PRIVATE_PATH_HASH:", result.redacted_text)
        self.assertIn("<PRIVATE_EMAIL_HASH:", result.redacted_text)
        self.assertIn("<PRIVATE_PHONE_HASH:", result.redacted_text)
        self.assertEqual(find_private_leaks(result.redacted_text, ["/mnt/nas/openclaw/Personal/家庭/身份证扫描件.pdf"]), [])

    def test_redacts_secret_and_id(self):
        text = "password=SYNTHETIC_VALUE_1234567890 身份证号 110101199001011234"
        result = PrivacyRedactor().redact(text)
        self.assertIn("<PRIVATE_SECRET_HASH:", result.redacted_text)
        self.assertIn("<PRIVATE_ID_HASH:", result.redacted_text)
        self.assertNotIn("110101199001011234", result.redacted_text)


if __name__ == "__main__":
    unittest.main()
