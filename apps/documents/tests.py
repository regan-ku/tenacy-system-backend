from django.test import SimpleTestCase
from .utils.formatter import DocFormatter
from .utils.pdf_utils import PdfUtils
import datetime

class DocFormatterTests(SimpleTestCase):
    def test_currency_formatting(self):
        self.assertEqual(DocFormatter.format_currency(15000.50), "KES 15,000.50")

    def test_date_formatting(self):
        date_obj = datetime.datetime(2024, 1, 15)
        self.assertEqual(DocFormatter.format_date(date_obj), "15 January 2024")

    def test_safe_filename_generation(self):
        self.assertEqual(DocFormatter.generate_safe_filename("Lease Agreement - Unit 4B"), "lease_agreement_unit_4b.pdf")

    def test_context_sanitization(self):
        context = {"name": "<script>alert('xss')</script>", "amount": None, "date": "2024-01-01"}
        sanitized = DocFormatter.sanitize_context(context)
        self.assertEqual(sanitized["name"], "alert('xss')")
        self.assertNotIn("amount", sanitized)
        self.assertEqual(sanitized["date"], "2024-01-01")

class PdfUtilsTests(SimpleTestCase):
    def test_variable_injection(self):
        template = "Hello {tenant_name}, your rent is {rent_amount}."
        context = {"tenant_name": "John", "rent_amount": "KES 15,000"}
        result = PdfUtils.inject_variables(template, context)
        self.assertEqual(result, "Hello John, your rent is KES 15,000.")

    def test_secure_url_generation(self):
        url = PdfUtils.generate_secure_download_url("lease.pdf", expires_hours=24)
        self.assertIn("token=", url)
        self.assertIn("expires=", url)