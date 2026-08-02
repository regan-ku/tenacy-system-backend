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
        unit_group=None, # Added support for unit_group based on your schema
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
            # Check if a file with the exact same original name already exists in this context
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
        Uses select_for_update() to prevent race conditions (crashing) 
        if multiple requests try to update the cover simultaneously.
        """
        cover_source = media_instance.file or media_instance.url
        if not cover_source:
            raise ValidationError("Cannot set an empty file/URL as cover.")

        # ==========================================
        # 🛡️ 4. CONCURRENCY PROTECTION (Prevents Crashes)
        # ==========================================
        if media_instance.unit:
            # Lock the Unit row in the DB until this transaction finishes
            unit = Unit.objects.select_for_update().get(pk=media_instance.unit.pk)
            
            old_cover = unit.cover_photo
            unit.cover_photo = cover_source
            unit.save(update_fields=['cover_photo'])
            
            # Clean up old orphaned file if it's no longer used
            MediaService._cleanup_orphaned_file(media_instance.property, old_cover)
            
        elif media_instance.unit_group:
            # If your UnitGroup model has a cover_photo field, handle it here.
            # For now, we fallback to property if unit_group doesn't have its own cover.
            pass 
        else:
            # Lock the Property row in the DB
            prop = Property.objects.select_for_update().get(pk=media_instance.property.pk)
            
            old_cover = prop.cover_photo
            prop.cover_photo = cover_source
            prop.save(update_fields=['cover_photo'])
            
            # Clean up old orphaned file if it's no longer used
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
        
        # Check if this specific media file is currently set as the cover photo
        cover_source = media_instance.file or media_instance.url
        is_current_cover = False
        
        if unit_obj and unit_obj.cover_photo and str(unit_obj.cover_photo) == str(cover_source):
            is_current_cover = True
        elif not unit_obj and property_obj.cover_photo and str(property_obj.cover_photo) == str(cover_source):
            is_current_cover = True

        # ==========================================
        # 🛡️ 5. PHYSICAL FILE CLEANUP
        # ==========================================
        # Before deleting the DB record, check if we need to delete the physical file.
        # We only delete the physical file if NO OTHER media record is using it.
        file_to_delete = media_instance.file
        media_instance.delete() # Delete DB record first
        
        if file_to_delete:
            # Check if any other media instance is still using this exact file path
            is_still_used = PropertyMedia.objects.filter(file=file_to_delete).exists()
            if not is_still_used:
                try:
                    file_to_delete.delete(save=False) # Delete physical file from storage
                except Exception:
                    pass # Fail silently on file deletion; DB is the source of truth

        # ==========================================
        # 🛡️ 6. COVER PHOTO PROMOTION
        # ==========================================
        if is_current_cover:
            filter_kwargs = {'property': property_obj}
            if unit_obj:
                filter_kwargs['unit'] = unit_obj
                
            # Get the next media ordered by display_order, then creation date
            next_media = PropertyMedia.objects.filter(**filter_kwargs).order_by('display_order', 'created_at').first()
            
            if next_media:
                MediaService.set_as_cover(next_media)
            else:
                # No media left, clear the cover photo field safely
                if unit_obj:
                    unit_obj.cover_photo = None
                    unit_obj.save(update_fields=['cover_photo'])
                else:
                    property_obj.cover_photo = None
                    property_obj.save(update_fields=['cover_photo'])
                    
        return True

    @staticmethod
    def _cleanup_orphaned_file(property_obj: Property, old_file_field):
        """
        Helper to delete a physical file from storage if it is no longer 
        referenced by ANY PropertyMedia record. Prevents storage bloat.
        """
        if not old_file_field:
            return
            
        # Check if any media record still points to this old file
        is_still_used = PropertyMedia.objects.filter(
            property=property_obj, 
            file=old_file_field
        ).exists()
        
        if not is_still_used:
            try:
                old_file_field.delete(save=False)
            except Exception:
                pass # Fail silently, storage cleanup is secondary to DB integrity