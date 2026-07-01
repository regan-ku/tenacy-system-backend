import json
import secrets
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from ..models import User, Profile, NextOfKin, Verification

class UserService:
    """
    Core business logic for user lifecycle management, state resolution, and role upgrades.
    """

    @staticmethod
    def lookup_applicant(email=None, phone=None):
        """
        SMART LOOKUP ENGINE: Finds a user by email or phone and determines their 
        readiness to be added as a tenant. Powers the dynamic 'Add Tenant' Modal.
        """
        user = None
        if email:
            user = User.objects.filter(email__iexact=email.strip()).first()
        elif phone:
            user = User.objects.filter(phone_number=phone).first()
            
        if not user:
            return {
                "status": "new_user",
                "user": None,
                "role": None,
                "missing_fields": []
            }
            
        if user.role == User.Role.AGENCY:
            return {
                "status": "existing_agency",
                "user": user,
                "role": user.role,
                "missing_fields": [] 
            }
            
        profile = getattr(user, 'profile', None)
        
        has_dob = bool(profile and profile.date_of_birth)
        has_nok = NextOfKin.objects.filter(user=user, is_primary=True).exists()
        has_nationality = bool(profile and profile.nationality)
        has_address = bool(profile and profile.address)
        
        is_legally_complete = has_dob and has_nok and has_nationality and has_address
        
        if not is_legally_complete:
            missing_fields = []
            if not has_nationality: missing_fields.append('nationality')
            if not has_address: missing_fields.append('address')
            if not has_dob: missing_fields.append('date_of_birth')
            if not has_nok: missing_fields.append('next_of_kin')
                
            return {
                "status": "existing_incomplete",
                "user": user,
                "role": user.role,
                "missing_fields": missing_fields
            }
            
        return {
            "status": "existing_complete",
            "user": user,
            "role": user.role,
            "missing_fields": []
        }

    @staticmethod
    @transaction.atomic
    def create_or_update_tenant_for_manager(manager_user: User, payload: dict) -> dict:
        """
        UNIVERSAL TENANT CREATOR: Handles both creating a brand new tenant AND 
        updating an existing incomplete tenant (like a staff member) to complete 
        their legal profile. Prevents duplicate accounts.
        """
        tenant_data = payload.get('tenant_data', {})
        profile_data = payload.get('profile_data', {})
        nok_data = payload.get('next_of_kin_data', {})

        email = tenant_data.get('email', '').strip().lower()
        phone = tenant_data.get('phone_number') or tenant_data.get('phone')

        if not email:
            raise ValidationError("Email is required.")

        existing_user = User.objects.filter(email=email).first()
        if not existing_user and phone:
            existing_user = User.objects.filter(phone_number=phone).first()

        temp_password = None

        if existing_user:
            user = existing_user
            profile, _ = Profile.objects.get_or_create(user=user)
            if profile_data.get('full_name'): profile.full_name = profile_data['full_name']
            if profile_data.get('national_id'): profile.national_id = profile_data['national_id']
            if profile_data.get('nationality'): profile.nationality = profile_data['nationality']
            if profile_data.get('address'): profile.address = profile_data['address']
            if profile_data.get('date_of_birth'): profile.date_of_birth = profile_data['date_of_birth']
            
            Profile.objects.filter(pk=profile.pk).update(profile_complete=True)
        else:
            temp_password = f"Temp{secrets.token_urlsafe(8)}!"
            user = User.objects.create_user(
                email=email,
                password=temp_password,
                phone_number=phone,
                role=User.Role.TENANT,
                is_verified=False,
                requires_password_change=True
            )
            
            Profile.objects.create(
                user=user,
                full_name=profile_data.get('full_name', ''),
                national_id=profile_data.get('national_id') or profile_data.get('id_number'),
                nationality=profile_data.get('nationality', ''),
                address=profile_data.get('address', ''),
                date_of_birth=profile_data.get('date_of_birth'),
                profile_complete=True
            )

        if nok_data.get('full_name'):
            NextOfKin.objects.update_or_create(
                user=user, is_primary=True,
                defaults={
                    'full_name': nok_data['full_name'],
                    'relationship': nok_data.get('relationship', 'other'),
                    'phone_number': nok_data.get('phone_number') or nok_data.get('phone', ''),
                    'city': nok_data.get('city', ''),
                }
            )

        return {
            "user": user,
            "temp_password": temp_password,
            "is_new": temp_password is not None
        }

    @staticmethod
    @transaction.atomic
    def create_staff_for_manager(manager_user: User, payload: dict) -> dict:
        """
        Creates a Staff member (Agent/Caretaker/Property Manager) with a Ghost Profile.
        They can log in immediately, but profile_complete=False triggers 
        the Tenant Profile Interceptor if they try to rent a unit.
        """
        email = payload.get('email', '').strip().lower()
        phone = payload.get('phone_number') or payload.get('phone')
        full_name = payload.get('full_name')
        role = payload.get('role', 'agent') # Default to string 'agent' to avoid enum issues early on

        if not email:
            raise ValidationError("Email is required.")
        if User.objects.filter(email=email).exists():
            raise ValidationError(f"A user with the email {email} already exists.")
        if phone and User.objects.filter(phone_number=phone).exists():
            raise ValidationError(f"A user with the phone number {phone} already exists.")

        temp_password = f"Temp{secrets.token_urlsafe(8)}!"

        # ✅ CRITICAL FIX: Map frontend roles to valid User.Role choices
        # Property Managers are stored as 'agent' in the User model, 
        # but get the 'property_manager' role in the AgencyStaff model.
        user_role_map = {
            'agent': User.Role.AGENT,
            'caretaker': User.Role.CARETAKER,
            'property_manager': User.Role.AGENT, 
        }
        user_role = user_role_map.get(role, User.Role.AGENT)

        user = User.objects.create_user(
            email=email,
            password=temp_password,
            phone_number=phone,
            role=user_role, # Use the mapped User role
            is_verified=False,
            requires_password_change=True
        )

        Profile.objects.create(
            user=user,
            full_name=full_name,
            profile_complete=False 
        )

        # ✅ FIXED: Robust AgencyStaff creation without silent failures
        from apps.agencies.models.agency import Agency
        from apps.agencies.models.agency_staff import AgencyStaff
        
        agency = Agency.objects.filter(
            Q(created_by=manager_user) | 
            Q(directors__user=manager_user) |
            Q(contact_email=manager_user.email)
        ).first()
        
        if agency:
            # ✅ Map to AgencyStaff.StaffRole (which DOES have PROPERTY_MANAGER)
            staff_role_map = {
                'agent': AgencyStaff.StaffRole.AGENT,
                'caretaker': AgencyStaff.StaffRole.CARETAKER,
                'property_manager': AgencyStaff.StaffRole.PROPERTY_MANAGER,
            }
            agency_staff_role = staff_role_map.get(role)
            
            if agency_staff_role:
                AgencyStaff.objects.create(
                    agency=agency,
                    user=user,
                    role=agency_staff_role,
                    status=AgencyStaff.Status.ACTIVE,
                    contact_email=email,
                    contact_phone=phone,
                )

        return {
            "user": user,
            "temp_password": temp_password
        }

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

        # ✅ Define staff roles dynamically to include PROPERTY_MANAGER if it exists
        staff_roles = [User.Role.AGENT, User.Role.CARETAKER]
        if hasattr(User.Role, 'PROPERTY_MANAGER'):
            staff_roles.append(User.Role.PROPERTY_MANAGER)

        # 1. PROFILE CHECK
        if not profile or not profile.profile_complete:
            if is_acting_as_tenant:
                return {
                    "profile_complete": False,
                    "role": user.role,
                    "next_route": "/onboarding",
                    "message": "Please complete your profile to proceed with your tenancy."
                }
            elif user.role in staff_roles:
                has_basic_profile = profile and profile.full_name and user.phone_number
                if not has_basic_profile:
                    return {
                        "profile_complete": False,
                        "role": user.role,
                        "next_route": "/onboarding",
                        "message": "Please complete your basic profile to access your dashboard."
                    }
                
                if profile and not profile.profile_complete:
                    profile.profile_complete = True
                    profile.save(update_fields=['profile_complete'])
                elif not profile:
                    Profile.objects.create(user=user, full_name=user.email.split('@')[0], profile_complete=True)
                
                has_dob = bool(profile and profile.date_of_birth)
                has_nok = NextOfKin.objects.filter(user=user, is_primary=True).exists()
                is_tenant_ready = has_dob and has_nok
                
                return {
                    "profile_complete": True,
                    "tenant_profile_complete": is_tenant_ready,
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

        tenant_profile_complete = True
        if user.role in staff_roles:
            has_dob = bool(profile and profile.date_of_birth)
            has_nok = NextOfKin.objects.filter(user=user, is_primary=True).exists()
            tenant_profile_complete = has_dob and has_nok

        # 2. TENANT LOGIC
        if is_acting_as_tenant:
            has_active_tenancy = Tenancy.objects.filter(tenant=user, status='active').exists()
            if has_active_tenancy:
                return {
                    "profile_complete": True,
                    "tenant_profile_complete": tenant_profile_complete,
                    "role": user.role,
                    "next_route": "/dashboard/tenant",
                    "message": "Welcome back to your tenant dashboard."
                }

            has_approved_application = Application.objects.filter(applicant=user, status='approved').exists()
            if has_approved_application:
                return {
                    "profile_complete": True,
                    "tenant_profile_complete": tenant_profile_complete,
                    "role": user.role,
                    "next_route": "/dashboard/tenant",
                    "message": "You have an approved application. Proceed to your dashboard to finalize your tenancy."
                }

            has_pending_application = Application.objects.filter(applicant=user, status__in=['pending', 'under_review']).exists()
            if has_pending_application:
                return {
                    "profile_complete": True,
                    "tenant_profile_complete": tenant_profile_complete,
                    "role": user.role,
                    "next_route": "/applications/pending",
                    "message": "Your application is currently under review by the property manager."
                }

            incomplete_app = Application.objects.filter(applicant=user, status='incomplete').first()
            if incomplete_app:
                return {
                    "profile_complete": True,
                    "tenant_profile_complete": tenant_profile_complete,
                    "role": user.role,
                    "next_route": "/marketplace", 
                    "message": "Resume your incomplete rental application."
                }
                
            return {
                "profile_complete": True,
                "tenant_profile_complete": tenant_profile_complete,
                "role": user.role,
                "next_route": "/marketplace",
                "message": "You have no active tenancies. Browse available properties."
            }

        # 3. LANDLORD & AGENCY LOGIC
        if user.role in [User.Role.LANDLORD, User.Role.AGENCY]:
            is_verified = False
            
            if user.role == User.Role.LANDLORD:
                verification = getattr(user, 'verification_record', None)
                if verification and verification.status == 'verified':
                    is_verified = True
                    
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

            if user.role == User.Role.LANDLORD:
                has_dob = bool(profile and profile.date_of_birth)
                has_nok = NextOfKin.objects.filter(user=user, is_primary=True).exists()
                tenant_profile_complete = has_dob and has_nok
            else:
                tenant_profile_complete = False

            if not is_verified:
                return {
                    "profile_complete": True,
                    "tenant_profile_complete": tenant_profile_complete,
                    "role": user.role,
                    "next_route": "/pending-verification",
                    "message": "Your identity and compliance documents are currently under review."
                }
            
            Property = apps.get_model('properties', 'Property')
            
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
                                "tenant_profile_complete": tenant_profile_complete,
                                "role": user.role,
                                "next_route": "/dashboard/agency",
                                "message": "Welcome! You have pending property delegations."
                            }
                except Exception:
                    pass 

            user_properties = Property.objects.filter(created_by=user).annotate(
                groups_count=Count('unit_groups'),
                media_count=Count('media')
            ).order_by('-created_at')
            
            has_completed = any(p.groups_count > 0 or p.media_count > 0 for p in user_properties)
            
            if has_completed:
                return {
                    "profile_complete": True,
                    "tenant_profile_complete": tenant_profile_complete,
                    "role": user.role,
                    "next_route": f"/dashboard/{user.role}",
                    "message": "Welcome back to your management dashboard."
                }
                
            if user_properties.exists():
                draft_property = user_properties.first()
                return {
                    "profile_complete": True,
                    "tenant_profile_complete": tenant_profile_complete,
                    "role": user.role,
                    "next_route": f"/properties/wizard?property_id={draft_property.id}",
                    "message": "Resume your incomplete property setup."
                }
                
            return {
                "profile_complete": True,
                "tenant_profile_complete": tenant_profile_complete,
                "role": user.role,
                "next_route": "/properties/wizard",
                "message": "Your account is verified! Get started by creating your first property."
            }

        # 4. STAFF FALLBACK
        return {
            "profile_complete": True,
            "tenant_profile_complete": tenant_profile_complete,
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
        
        profile.full_name = data.get('full_name', profile.full_name)
        profile.nationality = data.get('nationality', profile.nationality)
        profile.address = data.get('address', profile.address)
        
        dob = data.get('date_of_birth')
        if dob:
            profile.date_of_birth = dob
            
        id_number = data.get('id_number')
        if id_number:
            profile.national_id = id_number
            
        profile.save()
        Profile.objects.filter(pk=profile.pk).update(profile_complete=True)
        
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