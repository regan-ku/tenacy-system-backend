from rest_framework import serializers
from django.utils import timezone

from ..models import Verification, User


class VerificationService:
    """
    Handles identity and business verification workflows.

    This service enforces:
    - Only Landlords and Agencies can submit verification.
    - Already verified users cannot resubmit.
    - Required verification documents exist before saving.
    - Submitted verification moves to pending review.
    """

    @staticmethod
    def submit_verification(user: User, data: dict, files: dict, verification=None) -> Verification:
        """
        Initiates or updates a verification request for Landlords/Agencies.
        """

        data = data or {}
        files = files or {}

        if user.role not in [User.Role.LANDLORD, User.Role.AGENCY]:
            raise serializers.ValidationError(
                "Verification is only required for Landlords and Agencies."
            )

        if verification is None:
            verification, _created = Verification.objects.get_or_create(user=user)

        if verification.status == "verified":
            raise serializers.ValidationError(
                "Your account is already verified. Verification documents cannot be resubmitted."
            )

        # Update KRA PIN if provided.
        if data.get("kra_pin"):
            verification.kra_pin = str(data["kra_pin"]).strip().upper()

        # Update verification files if provided.
        file_fields = [
            "id_document_front",
            "id_document_back",
            "kra_tax_compliance_cert",
            "business_registration",
            "agency_license",
        ]

        for field in file_fields:
            incoming_file = data.get(field) or files.get(field)

            if incoming_file:
                setattr(verification, field, incoming_file)

        # Defense in depth:
        # Validate required verification data again at service level.
        errors = {}

        def has_file(field: str) -> bool:
            incoming_file = data.get(field) or files.get(field)

            if incoming_file:
                return True

            current_file = getattr(verification, field, None)
            return bool(current_file)

        if not verification.kra_pin:
            errors["kra_pin"] = "KRA PIN is required."

        if user.role == User.Role.LANDLORD:
            if not has_file("id_document_front"):
                errors["id_document_front"] = (
                    "National ID / Passport front side is required."
                )

            if not has_file("id_document_back"):
                errors["id_document_back"] = (
                    "National ID / Passport back side is required."
                )

        if user.role == User.Role.AGENCY:
            if not has_file("business_registration"):
                errors["business_registration"] = (
                    "Business Registration Certificate is required."
                )

            if not has_file("agency_license"):
                errors["agency_license"] = (
                    "EARB Agency License is required."
                )

        if not has_file("kra_tax_compliance_cert"):
            errors["kra_tax_compliance_cert"] = (
                "KRA Tax Compliance Certificate is required."
            )

        if errors:
            raise serializers.ValidationError(errors)

        verification.status = "pending"
        verification.submitted_at = timezone.now()
        verification.save()

        return verification

    @staticmethod
    def review_verification(
        verification_id: int,
        reviewer: User,
        status: str,
        reason: str = "",
    ) -> Verification:
        """
        Admin action to approve or reject a verification request.
        """

        if reviewer.role != User.Role.ADMIN:
            raise serializers.ValidationError(
                "Only administrators can review verifications."
            )

        try:
            verification = Verification.objects.get(id=verification_id)
        except Verification.DoesNotExist:
            raise serializers.ValidationError(
                "Verification record not found."
            )

        if status == "verified":
            verification.mark_verified(reviewer)

        elif status in ["rejected", "resubmit"]:
            if not reason:
                raise serializers.ValidationError(
                    "A reason is required for rejection or resubmission."
                )

            verification.mark_rejected(reviewer, reason)

        else:
            raise serializers.ValidationError(
                "Invalid status provided."
            )

        return verification