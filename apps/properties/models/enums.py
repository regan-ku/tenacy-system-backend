from django.db import models

class PropertyCategory(models.TextChoices):
    RESIDENTIAL = 'residential', 'Residential'
    COMMERCIAL = 'commercial', 'Commercial'
    HOSPITALITY = 'hospitality', 'Hospitality (Short Stay/Hotels)'
    INDUSTRIAL = 'industrial', 'Industrial'
    LAND = 'land', 'Land & Plots'
    MIXED_USE = 'mixed_use', 'Mixed Use'

class PropertySubType(models.TextChoices):
    # Residential
    APARTMENT = 'apartment', 'Apartment'
    FLAT = 'flat', 'Flat'
    BUNGALOW = 'bungalow', 'Bungalow'
    MANSION = 'mansion', 'Mansion'
    VILLA = 'villa', 'Villa'
    TOWNHOUSE = 'townhouse', 'Townhouse'
    MAISONETTE = 'maisonette', 'Maisonette'
    BEDSITTER = 'bedsitter', 'Bedsitter'
    STUDIO = 'studio', 'Studio Apartment'
    SINGLE_ROOM = 'single_room', 'Single Room'
    HOSTEL = 'hostel', 'Student Hostel'
    
    # Commercial
    OFFICE_SPACE = 'office_space', 'Office Space'
    RETAIL_SHOP = 'retail_shop', 'Retail Shop'
    WAREHOUSE = 'warehouse', 'Warehouse'
    
    # Hospitality
    AIRBNB = 'airbnb', 'Airbnb / Vacation Rental'
    HOTEL = 'hotel', 'Hotel'
    GUEST_HOUSE = 'guest_house', 'Guest House'
    SERVICED_APARTMENT = 'serviced_apartment', 'Serviced Apartment'
    
    # Land
    RESIDENTIAL_PLOT = 'residential_plot', 'Residential Plot'
    COMMERCIAL_LAND = 'commercial_land', 'Commercial Land'
    AGRICULTURAL_LAND = 'agricultural_land', 'Agricultural Land'

class ConstructionType(models.TextChoices):
    CONCRETE = 'concrete', 'Concrete'
    STONE = 'stone', 'Stone'
    STEEL_FRAME = 'steel_frame', 'Steel Frame'
    TIMBER = 'timber', 'Timber'
    BRICK = 'brick', 'Brick'
    MIXED = 'mixed', 'Mixed Materials'

class UnitType(models.TextChoices):
    SINGLE_ROOM = 'single_room', 'Single Room'
    BEDSITTER = 'bedsitter', 'Bedsitter'
    STUDIO = 'studio', 'Studio'
    ONE_BEDROOM = 'one_bedroom', '1 Bedroom'
    TWO_BEDROOM = 'two_bedroom', '2 Bedrooms'
    THREE_BEDROOM = 'three_bedroom', '3 Bedrooms'
    FOUR_PLUS_BEDROOM = 'four_plus_bedroom', '4+ Bedrooms'
    PENTHOUSE = 'penthouse', 'Penthouse'
    COMMERCIAL_SPACE = 'commercial_space', 'Commercial Space'
    LAND_PLOT = 'land_plot', 'Land Plot'
    PARKING_BAY = 'parking_bay', 'Parking Bay'

class UnitStatus(models.TextChoices):
    AVAILABLE = 'available', 'Available'
    OCCUPIED = 'occupied', 'Occupied'
    RESERVED = 'reserved', 'Reserved'
    MAINTENANCE = 'maintenance', 'Under Maintenance'
    OUT_OF_SERVICE = 'out_of_service', 'Out of Service'

class BillingCycle(models.TextChoices):
    DAILY = 'daily', 'Daily (Short Stay)'
    WEEKLY = 'weekly', 'Weekly'
    MONTHLY = 'monthly', 'Monthly'
    QUARTERLY = 'quarterly', 'Quarterly'
    YEARLY = 'yearly', 'Yearly'

class OwnershipStatus(models.TextChoices):
    OWNED = 'owned', 'Owned & Self-Managed'
    DELEGATED = 'delegated', 'Delegated to Agency'
    RELINQUISHED = 'relinquished', 'Relinquished (Agency Full Control)'

class ListingType(models.TextChoices):
    RENTAL = 'rental', 'Rental'
    SALE = 'sale', 'Sale'
    SHORT_STAY = 'short_stay', 'Short Stay'