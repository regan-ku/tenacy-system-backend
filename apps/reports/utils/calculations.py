from decimal import Decimal, ROUND_HALF_UP

class CalculationUtils:
    """
    Standardized mathematical calculations for reporting KPIs.
    Ensures consistent rounding and division-by-zero protection across all dashboards.
    """

    @staticmethod
    def calculate_percentage(numerator: float | Decimal, denominator: float | Decimal, decimals: int = 2) -> float:
        """
        Calculates a percentage safely, returning 0.0 if the denominator is zero.
        """
        if not denominator or float(denominator) == 0.0:
            return 0.0
        
        result = (float(numerator) / float(denominator)) * 100
        return round(result, decimals)

    @staticmethod
    def calculate_occupancy_rate(occupied_units: int, total_units: int) -> float:
        """
        Calculates the occupancy rate as a percentage.
        """
        return CalculationUtils.calculate_percentage(occupied_units, total_units)

    @staticmethod
    def calculate_arrears_rate(outstanding_amount: float | Decimal, total_expected_amount: float | Decimal) -> float:
        """
        Calculates the percentage of revenue that is currently in arrears.
        """
        return CalculationUtils.calculate_percentage(outstanding_amount, total_expected_amount)

    @staticmethod
    def format_currency(amount: float | Decimal, currency: str = "KES") -> str:
        """
        Formats a numeric amount into a standardized currency string.
        """
        return f"{currency} {float(amount):,.2f}"

    @staticmethod
    def calculate_growth_rate(current_value: float | Decimal, previous_value: float | Decimal) -> float:
        """
        Calculates period-over-period growth rate.
        """
        if not previous_value or float(previous_value) == 0.0:
            return 0.0
        
        growth = ((float(current_value) - float(previous_value)) / float(previous_value)) * 100
        return round(growth, 2)