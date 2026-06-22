from django.utils.text import slugify

class MarketplaceHelpers:
    """
    Reusable helper functions for marketplace data formatting and generation.
    """

    @staticmethod
    def generate_listing_title(property, unit_group=None):
        """
        Generates a clean, SEO-friendly listing title.
        Example: "2 Bedroom Apartment in Kilimani, Nairobi"
        """
        unit_type_display = ""
        if unit_group:
            # Get the display name of the unit type (e.g., "2 Bedrooms")
            unit_type_display = unit_group.get_unit_type_display() + " "
            
        location = property.location
        location_str = f"in {location.estate}, {location.city}" if location.estate else f"in {location.city}"
        
        return f"{unit_type_display}{property.get_property_sub_type_display()} {location_str}".strip()

    @staticmethod
    def format_price_range(unit_group):
        """
        Formats the price and period for display (e.g., "KES 15,000 / month").
        """
        period_map = {
            'daily': 'per night',
            'weekly': 'per week',
            'monthly': 'per month',
            'quarterly': 'per quarter',
            'yearly': 'per year'
        }
        period = period_map.get(unit_group.billing_cycle, 'per month')
        return f"KES {unit_group.base_rent_amount:,.2f} {period}"

    @staticmethod
    def get_availability_badge(availability_record):
        """
        Returns a dictionary with status and color for frontend UI badges.
        """
        if not availability_record or availability_record.available_units == 0:
            return {"text": "Fully Occupied", "color": "red"}
        elif availability_record.available_units == 1:
            return {"text": "1 Unit Remaining", "color": "orange"}
        else:
            return {"text": f"{availability_record.available_units} Units Remaining", "color": "green"}