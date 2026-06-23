from django.db import models

class Location(models.Model):
    """
    Stores structured address + geospatial intelligence.
    """
    # User-Provided Address Data
    # ✅ FIX: Added blank=True, null=True to ALL fields to prevent IntegrityErrors
    estate = models.CharField('Estate / Neighborhood', max_length=255, blank=True, null=True)
    street = models.CharField('Street / Road', max_length=255, blank=True, null=True)
    city = models.CharField('City / Town', max_length=100, db_index=True, blank=True, null=True)
    county = models.CharField('County / State', max_length=100, db_index=True, blank=True, null=True)
    region = models.CharField('Region', max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    
    landmark = models.CharField(
        'Nearby Landmark', 
        max_length=255, 
        blank=True, 
        null=True,
        help_text="e.g., 'Opposite Nairobi Hospital', 'Next to St. Mary's School'"
    )

    # Auto-Generated Geo Data
    latitude = models.DecimalField('Latitude', max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField('Longitude', max_digits=9, decimal_places=6, blank=True, null=True)
    geohash = models.CharField('Geohash', max_length=12, blank=True, null=True, db_index=True)
    place_id = models.CharField('Google Place ID', max_length=255, blank=True, null=True)

    # Search Optimization
    normalized_address = models.TextField('Normalized Address', blank=True, null=True)
    search_keywords = models.CharField('Search Keywords', max_length=500, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'

    def __str__(self):
        return f"{self.estate or 'Unknown'}, {self.city}, {self.county}"

    def save(self, *args, **kwargs):
        parts = [self.estate, self.street, self.city, self.county, self.region, self.landmark]
        self.normalized_address = " ".join([str(p).lower() for p in parts if p]).strip()
        super().save(*args, **kwargs)