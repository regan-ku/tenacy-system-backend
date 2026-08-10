import os
from django.db import transaction, models
from django.db.models import Max
from django.core.exceptions import ValidationError
from ..models import Property, Unit, PropertyMedia

class MediaService:
    """
    Bulletproof Media Service.
    Manages property, unit, and unit-group media uploads with strict 
    concurrency control, duplicate prevention, and orphaned file cleanup.
    """

    @staticmethod
    @transaction.atomic
    def add_media(
        property: Property, 
        unit: Unit = None, 
        unit_group=None,
        media_type: str = 'image', 
        file=None, 
        url: str = None, 
        caption: str = None, 
        set_as_cover: bool = False
    ) -> PropertyMedia:
        """
        Adds a new media item with strict validation against duplicates and state errors.
        """
        if not property:
            raise ValidationError("A valid property is required to attach media.")
            
        if not file and not url:
            raise ValidationError("Either a file or an external URL must be provided.")

        # ==========================================
        # 🛡️ 1. DUPLICATE PREVENTION
        # ==========================================
        qs = PropertyMedia.objects.filter(property=property)
        if unit:
            qs = qs.filter(unit=unit)
        elif unit_group:
            qs = qs.filter(unit_group=unit_group)
            
        if file and hasattr(file, 'name'):
            if qs.filter(file__endswith=os.path.basename(file.name)).exists():
                raise ValidationError(f"A media file named '{file.name}' already exists for this property.")
        
        if url:
            if qs.filter(url=url).exists():
                raise ValidationError("This external URL has already been added to this property.")

        # ==========================================
        # 🛡️ 2. AUTO-SEQUENCING (Display Order)
        # ==========================================
        max_order = qs.aggregate(Max('display_order'))['display_order__max'] or 0
        
        # ==========================================
        # 🛡️ 3. CREATE MEDIA INSTANCE
        # ==========================================
        media = PropertyMedia.objects.create(
            property=property,
            unit=unit,
            unit_group=unit_group,
            media_type=media_type,
            file=file,
            url=url,
            caption=caption,
            display_order=max_order + 1
        )

        if set_as_cover:
            MediaService.set_as_cover(media)

        return media

    @staticmethod
    @transaction.atomic
    def set_as_cover(media_instance: PropertyMedia) -> PropertyMedia:
        """
        Promotes a specific media instance to be the cover photo.
        Uses select_for_update() to prevent race conditions.
        """
        cover_source = media_instance.file or media_instance.url
        if not cover_source:
            raise ValidationError("Cannot set an empty file/URL as cover.")

        # ==========================================
        # 🛡️ 4. CONCURRENCY PROTECTION
        # ==========================================
        if media_instance.unit:
            unit = Unit.objects.select_for_update().get(pk=media_instance.unit.pk)
            
            old_cover = unit.cover_photo
            unit.cover_photo = cover_source
            unit.save(update_fields=['cover_photo'])
            
            MediaService._cleanup_orphaned_file(media_instance.property, old_cover)
            
        elif media_instance.unit_group:
            # For single-unit properties, unit_group cover falls back to property cover
            prop = Property.objects.select_for_update().get(pk=media_instance.property.pk)
            
            old_cover = prop.cover_photo
            prop.cover_photo = cover_source
            prop.save(update_fields=['cover_photo'])
            
            MediaService._cleanup_orphaned_file(prop, old_cover)
        else:
            prop = Property.objects.select_for_update().get(pk=media_instance.property.pk)
            
            old_cover = prop.cover_photo
            prop.cover_photo = cover_source
            prop.save(update_fields=['cover_photo'])
            
            MediaService._cleanup_orphaned_file(prop, old_cover)
            
        return media_instance

    @staticmethod
    @transaction.atomic
    def delete_media(media_instance: PropertyMedia) -> bool:
        """
        Safely deletes a media instance. 
        Handles cover photo promotion and physical file cleanup.
        """
        property_obj = media_instance.property
        unit_obj = media_instance.unit
        
        cover_source = media_instance.file or media_instance.url
        is_current_cover = False
        
        if unit_obj and unit_obj.cover_photo and str(unit_obj.cover_photo) == str(cover_source):
            is_current_cover = True
        elif not unit_obj and property_obj.cover_photo and str(property_obj.cover_photo) == str(cover_source):
            is_current_cover = True

        # ==========================================
        # 🛡️ 5. PHYSICAL FILE CLEANUP
        # ==========================================
        file_to_delete = media_instance.file
        media_instance.delete()
        
        if file_to_delete:
            is_still_used = PropertyMedia.objects.filter(file=file_to_delete).exists()
            if not is_still_used:
                try:
                    file_to_delete.delete(save=False)
                except Exception:
                    pass

        # ==========================================
        # 🛡️ 6. COVER PHOTO PROMOTION
        # ==========================================
        if is_current_cover:
            filter_kwargs = {'property': property_obj}
            if unit_obj:
                filter_kwargs['unit'] = unit_obj
                
            next_media = PropertyMedia.objects.filter(**filter_kwargs).order_by('display_order', 'created_at').first()
            
            if next_media:
                MediaService.set_as_cover(next_media)
            else:
                if unit_obj:
                    unit_obj.cover_photo = None
                    unit_obj.save(update_fields=['cover_photo'])
                else:
                    property_obj.cover_photo = None
                    property_obj.save(update_fields=['cover_photo'])
                    
        return True

    @staticmethod
    def get_effective_unit_media(unit: Unit) -> list:
        """
        ✅ NEW: Returns the effective media for a unit.
        
        For single-unit properties, returns property-level media as the unit's media
        since the property IS the unit. For multi-unit properties, returns only
        unit-specific media.
        
        This is the method the marketplace and tenant dashboards should call
        when displaying unit media.
        """
        if not unit or not unit.property_ref:
            return []
            
        property_obj = unit.property_ref
        
        # ✅ SINGLE-UNIT PROPERTY: Return property-level media as unit media
        if property_obj.is_single_unit_property:
            return list(
                PropertyMedia.objects.filter(
                    property=property_obj,
                    unit__isnull=True,
                    unit_group__isnull=True,
                    media_type__in=['image', 'video']
                ).order_by('display_order', 'created_at')
            )
        
        # MULTI-UNIT PROPERTY: Return only unit-specific media
        return list(
            PropertyMedia.objects.filter(
                unit=unit,
                media_type__in=['image', 'video']
            ).order_by('display_order', 'created_at')
        )

    @staticmethod
    def get_effective_unit_cover(unit: Unit):
        """
        ✅ NEW: Returns the effective cover photo for a unit.
        
        For single-unit properties, returns the property cover photo.
        For multi-unit properties, returns the unit's own cover photo.
        """
        if not unit or not unit.property_ref:
            return None
            
        property_obj = unit.property_ref
        
        if property_obj.is_single_unit_property:
            return property_obj.cover_photo
        
        return unit.cover_photo

    @staticmethod
    def _cleanup_orphaned_file(property_obj: Property, old_file_field):
        """
        Helper to delete a physical file from storage if it is no longer 
        referenced by ANY PropertyMedia record.
        """
        if not old_file_field:
            return
            
        is_still_used = PropertyMedia.objects.filter(
            property=property_obj, 
            file=old_file_field
        ).exists()
        
        if not is_still_used:
            try:
                old_file_field.delete(save=False)
            except Exception:
                pass