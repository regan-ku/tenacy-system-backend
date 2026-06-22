from decimal import Decimal, ROUND_HALF_UP
from typing import Dict

class PaymentCalculator:
    @staticmethod
    def prorate_amount(total_monthly: Decimal, days_in_month: int, days_occupied: int) -> Decimal:
        """Calculates prorated rent for partial occupancy periods."""
        if days_in_month <= 0 or days_occupied <= 0:
            return Decimal("0.00")
        daily_rate = (total_monthly / days_in_month).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return (daily_rate * days_occupied).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_late_fee(outstanding: Decimal, days_overdue: int, daily_rate_percent: Decimal = Decimal("0.5")) -> Decimal:
        """Calculates late fee based on daily percentage of outstanding balance."""
        if days_overdue <= 0 or outstanding <= 0:
            return Decimal("0.00")
        fee = (outstanding * (daily_rate_percent / Decimal("100")) * days_overdue)
        return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def allocate_payment(payment_amount: Decimal, arrears_balance: Decimal, current_due: Decimal) -> Dict[str, Decimal]:
        """
        Priority allocation logic per documentation:
        1. Clear arrears first (oldest debt)
        2. Apply to current invoice
        3. Excess becomes tenant credit (future rent)
        """
        allocation = {
            "to_arrears": Decimal("0.00"),
            "to_current": Decimal("0.00"),
            "to_future_credit": Decimal("0.00")
        }
        remaining = payment_amount

        # 1. Pay arrears
        if arrears_balance > 0:
            to_arrears = min(remaining, arrears_balance)
            allocation["to_arrears"] = to_arrears.quantize(Decimal("0.01"))
            remaining -= to_arrears

        # 2. Pay current due
        if remaining > 0 and current_due > 0:
            to_current = min(remaining, current_due)
            allocation["to_current"] = to_current.quantize(Decimal("0.01"))
            remaining -= to_current

        # 3. Excess to future
        if remaining > 0:
            allocation["to_future_credit"] = remaining.quantize(Decimal("0.01"))

        return allocation