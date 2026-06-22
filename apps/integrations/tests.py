from django.test import SimpleTestCase
from .utils.payload_formatter import format_mpesa_stk_payload, format_sms_payload
from .utils.signature_validator import verify_webhook_signature
import hmac, hashlib

class PayloadFormattingTests(SimpleTestCase):
    def test_mpesa_stk_payload_format(self):
        payload = format_mpesa_stk_payload("254712345678", 100.0, "REF001", "https://callback.url")
        self.assertEqual(payload["PhoneNumber"], "254712345678")
        self.assertEqual(payload["Amount"], 100)
        self.assertEqual(payload["AccountReference"], "REF001")

    def test_sms_payload_format(self):
        payload = format_sms_payload("254712345678", "Hello Tenant")
        self.assertEqual(payload["to"], "254712345678")
        self.assertEqual(payload["message"], "Hello Tenant")

class SignatureValidationTests(SimpleTestCase):
    def test_valid_hmac_signature(self):
        payload = b'{"test": "data"}'
        secret = "test_secret"
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook_signature(payload, signature, secret))

    def test_invalid_signature(self):
        payload = b'{"test": "data"}'
        self.assertFalse(verify_webhook_signature(payload, "fake_signature", "secret"))