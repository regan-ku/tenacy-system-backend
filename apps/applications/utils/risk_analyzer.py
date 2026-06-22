from django.db.models import Q
from django.utils import timezone
from apps.tenancy.models import Tenancy, TenancyNote


class RiskAnalyzer:
    """
    Analyzes an applicant's historical data to generate a risk score and 
    flag potential concerns for Agents/Managers during application review.
    """

    # Scoring weights (deductions from a base score of 100)
    DEDUCTION_PROFILE_INCOMPLETE = 20
    DEDUCTION_BREACH_TERMINATION = 40
    DEDUCTION_NEGATIVE_PAYMENT_NOTE = 15
    DEDUCTION_NEGATIVE_BEHAVIOR_NOTE = 10
    DEDUCTION_UNRESOLVED_MAINTENANCE = 5

    @staticmethod
    def analyze_applicant(applicant) -> dict:
        """
        Evaluates the applicant's historical records and returns a risk assessment.
        """
        base_score = 100
        flags = []
        
        # 1. Profile Completeness Check
        profile = getattr(applicant, 'profile', None)
        if not profile or not getattr(profile, 'profile_complete', False):
            base_score -= RiskAnalyzer.DEDUCTION_PROFILE_INCOMPLETE
            flags.append("Profile is incomplete or unverified.")

        # 2. Fetch Historical Tenancies
        past_tenancies = Tenancy.objects.filter(
            tenant=applicant
        ).select_related('property', 'unit').order_by('-start_date')

        # 3. Fetch All Historical Notes for this Tenant
        # We look for internal notes that might be visible during application review
        historical_notes = TenancyNote.objects.filter(
            tenant=applicant,
            visibility='application_view' # As per documentation rules
        ).order_by('-created_at')

        # 4. Analyze Tenancy History & Notes
        breach_count = 0
        negative_payment_count = 0
        negative_behavior_count = 0

        for tenancy in past_tenancies:
            # Check for past breaches/evictions
            if tenancy.status == 'terminated':
                # In a full implementation, you'd check a specific termination_reason field
                # For now, we check notes or assume a flag exists
                pass 

        for note in historical_notes:
            if note.note_type == 'payment' and 'late' in note.note_content.lower():
                negative_payment_count += 1
                base_score -= RiskAnalyzer.DEDUCTION_NEGATIVE_PAYMENT_NOTE
                flags.append(f"Past payment issue noted on {note.created_at.strftime('%Y-%m-%d')}.")
            
            elif note.note_type == 'behavior':
                negative_behavior_count += 1
                base_score -= RiskAnalyzer.DEDUCTION_NEGATIVE_BEHAVIOR_NOTE
                flags.append(f"Past behavioral concern noted on {note.created_at.strftime('%Y-%m-%d')}.")
            
            elif note.note_type == 'maintenance' and 'damage' in note.note_content.lower():
                base_score -= RiskAnalyzer.DEDUCTION_UNRESOLVED_MAINTENANCE
                flags.append("Past note indicates potential property damage.")

        # 5. Check for Active Arrears (if they are an existing tenant applying for a transfer)
        # This requires integration with the payments app, simplified here as a placeholder
        # active_arrears = PaymentService.get_tenant_arrears(applicant)
        # if active_arrears > 0:
        #     base_score -= 30
        #     flags.append(f"Applicant has outstanding arrears of {active_arrears}.")

        # 6. Cap the score at 0 minimum
        final_score = max(0, base_score)

        # 7. Determine Risk Level
        if final_score >= 80:
            risk_level = 'LOW'
        elif final_score >= 50:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'HIGH'

        return {
            "risk_score": final_score,
            "risk_level": risk_level,
            "flags": flags,
            "total_past_tenancies": past_tenancies.count(),
            "negative_notes_count": negative_payment_count + negative_behavior_count,
            "requires_manager_review": risk_level == 'HIGH' or len(flags) >= 2
        }

    @staticmethod
    def get_tenant_summary_for_application(applicant) -> dict:
        """
        Provides a quick, readable summary of the tenant for the Agent/Manager 
        viewing the application, powered by the risk analyzer.
        """
        risk_data = RiskAnalyzer.analyze_applicant(applicant)
        
        return {
            "applicant_name": applicant.get_full_name(),
            "risk_assessment": risk_data,
            "profile_complete": getattr(applicant.profile, 'profile_complete', False) if hasattr(applicant, 'profile') else False,
            "verification_status": getattr(applicant, 'is_verified', False)
        }