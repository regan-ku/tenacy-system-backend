from django.test import SimpleTestCase
from decimal import Decimal
from .utils.calculators import PaymentCalculator

class PaymentCalculatorsTests(SimpleTestCase):
    def test_arrears_first_allocation(self):
        split = PaymentCalculator.allocate_payment(
            payment_amount=Decimal("5000.00"),
            arrears_balance=Decimal("3000.00"),
            current_due=Decimal("1500.00")
        )
        self.assertEqual(split["to_arrears"], Decimal("3000.00"))
        self.assertEqual(split["to_current"], Decimal("1500.00"))
        self.assertEqual(split["to_future_credit"], Decimal("500.00"))

    def test_partial_payment_covering_only_arrears(self):
        split = PaymentCalculator.allocate_payment(
            payment_amount=Decimal("1000.00"),
            arrears_balance=Decimal("2500.00"),
            current_due=Decimal("1500.00")
        )
        self.assertEqual(split["to_arrears"], Decimal("1000.00"))
        self.assertEqual(split["to_current"], Decimal("0.00"))
        self.assertEqual(split["to_future_credit"], Decimal("0.00"))

    def test_late_fee_calculation(self):
        fee = PaymentCalculator.calculate_late_fee(Decimal("1000.00"), 10, Decimal("0.5"))
        self.assertEqual(fee, Decimal("50.00"))  # 0.5% * 10 days * 1000

    def test_zero_or_negative_protection(self):
        split = PaymentCalculator.allocate_payment(Decimal("0.00"), Decimal("100.00"), Decimal("100.00"))
        self.assertEqual(split["to_arrears"], Decimal("0.00"))
        fee = PaymentCalculator.calculate_late_fee(Decimal("100.00"), -5, Decimal("0.5"))
        self.assertEqual(fee, Decimal("0.00"))