from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.html import format_html
from .models import User, Profile, NextOfKin, Verification

# ---------------------------------------------------------
# 0. CUSTOM FORMS FOR EMAIL-BASED AUTH
# ---------------------------------------------------------
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'phone_number', 'role')

class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('email', 'phone_number', 'role')

# ---------------------------------------------------------
# 1. USER ADMIN (Customized for Email-based Auth)
# ---------------------------------------------------------
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Bind custom forms that don't look for the 'username' field
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ('email', 'role', 'is_verified', 'is_active', 'date_joined')
    list_filter = ('role', 'is_verified', 'is_active', 'date_joined')
    search_fields = ('email', 'phone_number')
    ordering = ('-date_joined',)
    
    # Use email instead of username for the core fieldsets
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('phone_number', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Overriding add_fieldsets explicitly so Django's default creation layout doesn't crash on 'username'
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phone_number', 'role', 'password'),
        }),
    )


# ---------------------------------------------------------
# 2. PROFILE INLINE
# ---------------------------------------------------------
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'User Profile'
    readonly_fields = ('profile_complete',)

# Attach the Profile Inline to the User Admin layout dynamically
UserAdmin.inlines = [ProfileInline]


# ---------------------------------------------------------
# 3. NEXT OF KIN ADMIN
# ---------------------------------------------------------
@admin.register(NextOfKin)
class NextOfKinAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'user_email', 'relationship', 'phone_number', 'is_primary')
    list_filter = ('relationship', 'is_primary')
    search_fields = ('full_name', 'user__email', 'phone_number')
    
    @admin.display(description='User Email')
    def user_email(self, obj):
        return obj.user.email


# ---------------------------------------------------------
# 4. VERIFICATION ADMIN (✅ STATUS DROPDOWN UNLOCKED)
# ---------------------------------------------------------
@admin.register(Verification)
class VerificationAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'role', 'status', 'submitted_at', 'reviewed_by_link')
    list_filter = ('status', 'submitted_at')
    search_fields = ('user__email', 'kra_pin')
    
    # ✅ FIX: Removed 'status' from this list! 
    # Now you can use the dropdown to change it from 'Pending' to 'Verified'.
    readonly_fields = ('submitted_at', 'reviewed_at', 'reviewed_by')
    
    actions = ['approve_verifications', 'reject_verifications']

    @admin.display(description='User Email')
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description='User Role')
    def role(self, obj):
        return obj.user.get_role_display()

    @admin.display(description='Reviewed By')
    def reviewed_by_link(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.email
        return format_html('<span style="color: orange;">Pending</span>')

    @admin.action(description="Approve selected verifications")
    def approve_verifications(self, request, queryset):
        count = 0
        for verification in queryset.filter(status__in=['pending', 'resubmit']):
            verification.mark_verified(request.user)
            count += 1
        self.message_user(request, f"Successfully approved {count} verifications.")

    @admin.action(description="Reject selected verifications")
    def reject_verifications(self, request, queryset):
        count = 0
        for verification in queryset.filter(status__in=['pending', 'verified']):
            verification.mark_rejected(request.user, "Rejected via bulk admin action. Please contact support.")
            count += 1
        self.message_user(request, f"Successfully rejected {count} verifications.")