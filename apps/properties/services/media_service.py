from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Property, Unit, PropertyMedia

class MediaService:
    """
    Manages property and unit media uploads, ensuring the 'cover_photo' 
    field on the Property/Unit models is accurately synchronized.
    """

    @staticmethod
    @transaction.atomic
    def add_media(property: Property, unit: Unit = None, media_type: str = 'image', 
                  file=None, url: str = None, caption: str = None, set_as_cover: bool = False) -> PropertyMedia:
        """
        Adds a new media item to a property or specific unit.
        If set_as_cover is True, it automatically updates the parent model's cover_photo field.
        """
        if not file and not url:
            raise ValidationError("Either a file or an external URL must be provided.")

        media = PropertyMedia.objects.create(
            property=property,
            unit=unit,
            media_type=media_type,
            file=file,
            url=url,
            caption=caption
        )

        if set_as_cover:
            MediaService.set_as_cover(media)

        return media

    @staticmethod
    @transaction.atomic
    def set_as_cover(media_instance: PropertyMedia) -> PropertyMedia:
        """
        Promotes a specific media instance to be the cover photo by updating 
        the actual cover_photo field on the related Property or Unit model.
        """
        cover_source = media_instance.file or media_instance.url
        
        if media_instance.unit:
            media_instance.unit.cover_photo = cover_source
            media_instance.unit.save(update_fields=['cover_photo'])
        else:
            media_instance.property.cover_photo = cover_source
            media_instance.property.save(update_fields=['cover_photo'])
            
        return media_instance

    @staticmethod
    @transaction.atomic
    def delete_media(media_instance: PropertyMedia) -> bool:
        """
        Safely deletes a media instance. If it was the current cover photo, 
        it automatically promotes the next available media to be the new cover.
        """
        property_obj = media_instance.property
        unit_obj = media_instance.unit
        
        # Check if this specific media file is currently set as the cover photo
        cover_source = media_instance.file or media_instance.url
        is_current_cover = False
        
        if unit_obj and str(unit_obj.cover_photo) == str(cover_source):
            is_current_cover = True
        elif not unit_obj and str(property_obj.cover_photo) == str(cover_source):
            is_current_cover = True

        # Delete the instance (Django's FileField will handle physical file deletion if configured)
        media_instance.delete()

        # If it was the cover photo, promote the next available image
        if is_current_cover:
            filter_kwargs = {'property': property_obj}
            if unit_obj:
                filter_kwargs['unit'] = unit_obj
                
            # Get the next media ordered by display_order, then creation date
            next_media = PropertyMedia.objects.filter(**filter_kwargs).order_by('display_order', 'created_at').first()
            
            if next_media:
                MediaService.set_as_cover(next_media)
            else:
                # No media left, clear the cover photo field
                if unit_obj:
                    unit_obj.cover_photo = None
                    unit_obj.save(update_fields=['cover_photo'])
                else:
                    property_obj.cover_photo = None
                    property_obj.save(update_fields=['cover_photo'])
                    
        return True