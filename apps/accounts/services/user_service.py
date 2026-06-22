import json
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count  # ✅ ADDED: For Smart Draft Detection
from ..models import User, Profile, NextOfKin, Verification

class UserService:
    """
    Core business logic for user lifecycle management, state resolution, and role upgrades.
    """

    @staticmethod
    def get_user_state(user: User) -> dict:
        """
        POST-LOGIN USER STATE RESOLUTION ENGINE
        Determines the exact next_route based on profile, records, and verification.
        """
        profile = getattr(user, 'profile', None)
        
        Application = apps.get_model('applications', 'Application')
        Tenancy = apps.get_model('tenancy', 'Tenancy')
        
        is_acting_as_tenant = (
            user.role == User.Role.TENANT or
            Application.objects.filter(applicant=user).exists() or
            Tenancy.objects.filter(tenant=user, status='active').exists()
        )

        # 1. PROFILE CHECK
        if not profile or not profile.profile_complete:
            if is_acting_as_tenant:
                return {
                    "profile_complete": False,
                    "role": user.role,
                    "next_route": "/onboarding",
                    "message": "Please complete your profile to proceed with your tenancy."
                }
            elif user.role in [User.Role.AGENT, User.Role.CARETAKER]:
                if profile:
                    profile.profile_complete = True
                    profile.save(update_fields=['profile_complete'])
                else:
                    Profile.objects.create(user=user, profile_complete=True)
                return {
                    "profile_complete": True,
                    "role": user.role,
                    "next_route": f"/dashboard/{user.role}",
                    "message": "Welcome to your operational dashboard."
                }
            else:
                return {
                    "profile_complete": False,
                    "role": user.role,
                    "next_route": "/onboarding",
                    "message": "Please complete your profile to continue."
                }

        # 2. TENANT LOGIC (Record-based)
        if is_acting_as_tenant:
            incomplete_app = Application.objects.filter(applicant=user, status='incomplete').first()
            if incomplete_app:
                return {
                    "profile_complete": True,
                    "role": user.role,
                    "next_route": f"/applications/wizard/{incomplete_app.id}",
                    "message": "Resume your incomplete rental application."
                }
            
            has_active_tenancy = Tenancy.objects.filter(tenant=user, status='active').exists()
            if not has_active_tenancy:
                return {
                    "profile_complete": True,
                    "role": user.role,
                    "next_route": "/marketplace",
                    "message": "You have no active tenancies. Browse available properties."
                }
                
            return {
                "profile_complete": True,
                "role": user.role,
                "next_route": "/dashboard/tenant",
                "message": "Welcome back to your tenant dashboard."
            }

        # 3. LANDLORD & AGENCY LOGIC (✅ FIXED: Smart Draft Detection)
        if user.role in [User.Role.LANDLORD, User.Role.AGENCY]:
            is_verified = False
            
            # A. Check Landlord Verification (accounts.Verification model)
            if user.role == User.Role.LANDLORD:
                verification = getattr(user, 'verification_record', None)
                if verification and verification.status == 'verified':
                    is_verified = True
                    
            # B. Check Agency Verification (agencies.Agency OR agencies.AgencyVerification models)
            elif user.role == User.Role.AGENCY:
                try:
                    Agency = apps.get_model('agencies', 'Agency')
                    agency = Agency.objects.filter(created_by=user).first()
                    if not agency:
                        agency = Agency.objects.filter(contact_email=user.email).first()
                        
                    if agency:
                        if agency.status in [Agency.Status.VERIFIED, Agency.Status.ACTIVE]:
                            is_verified = True
                        else:
                            AgencyVerification = apps.get_model('agencies', 'AgencyVerification')
                            agency_ver = AgencyVerification.objects.filter(agency=agency).first()
                            if agency_ver and agency_ver.status == 'verified':
                                is_verified = True
                except Exception:
                    pass
                
                if not is_verified:
                    verification = getattr(user, 'verification_record', None)
                    if verification and verification.status == 'verified':
                        is_verified = True

            # If neither verification model shows 'verified', keep them in the waiting room
            if not is_verified:
                return {
                    "profile_complete": True,
                    "role": user.role,
                    "next_route": "/pending-verification",
                    "message": "Your identity and compliance documents are currently under review by our admin team. You will be redirected to your dashboard once your account is fully verified."
                }
            
            Property = apps.get_model('properties', 'Property')
            
            # AGENCY SPECIFIC: Check for pending delegated properties
            if user.role == User.Role.AGENCY:
                try:
                    Agency = apps.get_model('agencies', 'Agency')
                    DelegatedProperty = apps.get_model('agencies', 'DelegatedProperty')
                    
                    agency = Agency.objects.filter(created_by=user).first()
                    if not agency:
                        agency = Agency.objects.filter(contact_email=user.email).first()
                        
                    if agency:
                        pending_delegations = DelegatedProperty.objects.filter(
                            agency=agency, 
                            status__in=['pending', 'pending_acceptance']
                        ).exists()
                        
                        if pending_delegations:
                            return {
                                "profile_complete": True,
                                "role": user.role,
                                "next_route": "/dashboard/agency",
                                "message": "Welcome! You have pending property delegations from landlords waiting for your acceptance."
                            }
                except Exception:
                    pass 

            # ✅🚨 CRITICAL FIX: Smart Draft Detection
            # A property is ONLY considered "complete" if it has Unit Groups or Media.
            # If it has neither, it's just a Step 3 draft and the user abandoned the wizard.
            user_properties = Property.objects.filter(created_by=user).annotate(
                groups_count=Count('unit_groups'),
                media_count=Count('media')
            ).order_by('-created_at')
            
            # Check if any property is "completed" (has groups or media)
            has_completed = any(p.groups_count > 0 or p.media_count > 0 for p in user_properties)
            
            if has_completed:
                return {
                    "profile_complete": True,
                    "role": user.role,
                    "next_route": f"/dashboard/{user.role}",
                    "message": "Welcome back to your management dashboard."
                }
                
            # If no completed properties, but they have at least one draft
            if user_properties.exists():
                draft_property = user_properties.first()
                return {
                    "profile_complete": True,
                    "role": user.role,
                    "next_route": f"/properties/wizard?property_id={draft_property.id}",
                    "message": "Resume your incomplete property setup."
                }
                
            # If no properties at all, send them to start the wizard
            return {
                "profile_complete": True,
                "role": user.role,
                "next_route": "/properties/wizard",
                "message": "Your account is verified! Get started by creating your first property."
            }

        # 4. AGENT & CARETAKER LOGIC
        return {
            "profile_complete": True,
            "role": user.role,
            "next_route": f"/dashboard/{user.role}",
            "message": "Welcome to your operational dashboard."
        }

    @staticmethod
    @transaction.atomic
    def complete_onboarding(user: User, data: dict, files: dict) -> Profile:
        """
        Handles the final onboarding submission.
        Smart router: Saves data to the correct models based on User Role.
        """
        profile, created = Profile.objects.get_or_create(user=user)
        
        # 1. Update Profile fields (Basic contact info for the INDIVIDUAL human)
        profile.full_name = data.get('full_name', profile.full_name)
        profile.nationality = data.get('nationality', profile.nationality)
        profile.address = data.get('address', profile.address)
        
        dob = data.get('date_of_birth')
        if dob:
            profile.date_of_birth = dob
            
        id_number = data.get('id_number')
        if id_number:
            profile.national_id = id_number
            
        # Save the basic text fields first
        profile.save()
        
        # ✅🚨 CRITICAL FIX: Force update the database directly to bypass the 
        # Profile model's save() method completely. This guarantees profile_complete 
        # stays True, even if the frontend sent empty strings for some fields.
        Profile.objects.filter(pk=profile.pk).update(profile_complete=True)
        
        # 2. Handle Next of Kin (for Tenants/Landlords ONLY)
        if user.role != User.Role.AGENCY:
            nok_name = data.get('next_of_kin_name')
            if nok_name:
                NextOfKin.objects.update_or_create(
                    user=user, is_primary=True,
                    defaults={
                        'full_name': nok_name,
                        'relationship': data.get('next_of_kin_relationship', ''),
                        'phone_number': data.get('next_of_kin_phone', ''),
                        'city': data.get('next_of_kin_city', ''),
                    }
                )
        
        # 3. Handle Agency Specific Data (The BUSINESS entity)
        if user.role == User.Role.AGENCY:
            Agency = apps.get_model('agencies', 'Agency')
            AgencyProfile = apps.get_model('agencies', 'AgencyProfile')
            AgencyDirector = apps.get_model('agencies', 'AgencyDirector')
            
            agency, agency_created = Agency.objects.get_or_create(
                registration_number=data.get('registration_number'),
                defaults={
                    'created_by': user,
                    'name': data.get('business_name'),
                    'contact_email': data.get('business_email'),
                    'phone_number': data.get('phone_number'),
                    'physical_address': data.get('address'),
                    'status': 'pending_verification',
                    'is_active': False,
                }
            )
            
            AgencyProfile.objects.update_or_create(
                agency=agency,
                defaults={
                    'business_name': data.get('business_name'),
                    'registration_number': data.get('registration_number'),
                    'kra_pin': data.get('kra_pin', ''),
                    'physical_address': data.get('address'),
                    'city': data.get('city', 'Nairobi'),
                    'county': data.get('county', 'Nairobi'),
                    'contact_person_name': profile.full_name or user.email,
                    'contact_person_phone': data.get('phone_number'),
                    'contact_person_email': data.get('business_email'),
                }
            )
            
            directors_data = data.get('directors', [])
            
            if isinstance(directors_data, str):
                try:
                    directors_data = json.loads(directors_data)
                except json.JSONDecodeError:
                    directors_data = []

            if directors_data:
                AgencyDirector.objects.filter(agency=agency).delete()
                
                for index, d in enumerate(directors_data):
                    AgencyDirector.objects.create(
                        agency=agency,
                        user=user if index == 0 else None,
                        full_name=d.get('full_name'),
                        national_id=d.get('id_number'),
                        email=d.get('email'),
                        phone_number=d.get('phone_number'),
                        nationality=data.get('nationality', 'Kenyan'),
                        address=data.get('address', ''),
                        ownership_percentage=d.get('ownership_percentage', 0),
                        is_primary_director=(index == 0),
                        verification_status='pending'
                    )
                    
            verification, v_created = Verification.objects.get_or_create(user=user)
            
            kra_pin = data.get('kra_pin')
            if kra_pin:
                verification.kra_pin = kra_pin

            file_fields = ['kra_tax_compliance_cert', 'business_registration', 'agency_license']
            for field in file_fields:
                if field in files:
                    setattr(verification, field, files[field])
                    
            if verification.status != 'verified':
                verification.status = 'pending' 
            verification.save()
            
        # 4. Handle Landlord Verification Documents
        elif user.role == User.Role.LANDLORD:
            verification, v_created = Verification.objects.get_or_create(user=user)
            
            kra_pin = data.get('kra_pin')
            if kra_pin:
                verification.kra_pin = kra_pin

            file_fields = ['id_document_front', 'id_document_back', 'kra_tax_compliance_cert']
            for field in file_fields:
                if field in files:
                    setattr(verification, field, files[field])
                    
            if verification.status != 'verified':
                verification.status = 'pending' 
            verification.save()
            
        return profile

    @staticmethod
    @transaction.atomic
    def request_role_upgrade(user: User, target_role: str) -> dict:
        if target_role not in [User.Role.LANDLORD, User.Role.AGENCY]:
            raise ValidationError("Upgrades are only supported for Landlord or Agency roles.")
        
        if getattr(user, 'verification_record', None) and user.verification_record.status == 'verified':
            user.role = target_role
            user.save(update_fields=['role'])
            return {"status": "upgraded", "next_route": f"/dashboard/{target_role}"}
        
        verification, created = Verification.objects.get_or_create(user=user)
        if verification.status == 'verified':
            verification.status = 'pending' 
            verification.save(update_fields=['status'])
            
        return {
            "status": "verification_required",
            "next_route": "/onboarding/verification",
            "message": f"To operate as a {target_role}, you must complete identity and tax verification."
        }

    @staticmethod
    def update_profile(user: User, profile_data: dict) -> Profile:
        profile = user.profile
        for key, value in profile_data.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        profile.save() 
        return profile

    @staticmethod
    def add_next_of_kin(user: User, kin_data: dict) -> NextOfKin:
        if user.next_of_kin_contacts.count() >= 3:
            raise ValidationError("Maximum of 3 next of kin contacts allowed.")
        return NextOfKin.objects.create(user=user, **kin_data)