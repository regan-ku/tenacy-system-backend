from django.core.exceptions import ValidationError
from ..models import Application, ApplicationDecision, ApplicationNote
from .tenancy_condition_service import TenancyConditionService
from ..utils.scoring_engine import ScoringEngine
from ..utils.risk_analyzer import RiskAnalyzer
from .screening_service import ScreeningService

class DecisionEngine:
    """
    Evaluates application conditions and automatically routes the decision workflow.
    """

    @staticmethod
    def evaluate_and_route(application: Application, reviewer) -> str:
        if application.application_type == Application.ApplicationType.RENTAL:
            conditions = TenancyConditionService.validate_rental_conditions(
                application.unit, application.applicant
            )
        elif application.application_type == Application.ApplicationType.TRANSFER:
            transfer_details = getattr(application, 'transfer_details', None) or getattr(application, 'transfer_application', None)
            if not transfer_details:
                return 'escalate'
                
            conditions = TenancyConditionService.validate_transfer_conditions(
                transfer_details.from_unit, transfer_details.to_unit, application.applicant
            )
        else:
            return 'escalate' 

        if not conditions.get("all_conditions_met", False) or conditions.get("has_blocking_flags", True):
            return 'escalate'
            
        return 'approve'

    @staticmethod
    def record_decision(application: Application, decision: str, reviewer, reason: str = "") -> ApplicationDecision:
        valid_decisions = ['approved', 'rejected', 'escalated']
        if decision not in valid_decisions:
            raise ValidationError(f"Invalid decision. Must be one of: {valid_decisions}")

        if reviewer.role == 'agent' and decision == 'approved':
            required_action = DecisionEngine.evaluate_and_route(application, reviewer)
            if required_action == 'escalate':
                raise ValidationError(
                    "Agent approval denied: Not all tenancy conditions are met. This application must be escalated to a Manager."
                )

        # ✅ FIX: Safely handle status mapping
        status_map = {
            'approved': getattr(Application.Status, 'APPROVED', 'approved'),
            'rejected': getattr(Application.Status, 'REJECTED', 'rejected'),
            'escalated': getattr(Application.Status, 'ESCALATED', 'escalated')
        }
        application.status = status_map[decision]
        application.save(update_fields=['status'])

        decision_record = ApplicationDecision.objects.create(
            application=application,
            decision=decision,
            approver=reviewer,
            approver_role=reviewer.role,
            reason=reason
        )

        # ✅ FIX: Safely get NoteType enum
        note_type_enum = getattr(ApplicationNote.NoteType, 'ESCALATION_REASON', 'escalation_reason') if decision == 'escalated' else getattr(ApplicationNote.NoteType, 'MANAGER_REMARK', 'manager_remark')
        
        ApplicationNote.objects.create(
            application=application,
            note_type=note_type_enum,
            content=f"Application {decision} by {reviewer.role}. Reason: {reason or 'No reason provided'}",
            created_by=reviewer
        )

        if decision == 'approved':
            # ✅ CRITICAL FIX: Corrected the spelling of the import
            from .tennacy_intergration_service import TenancyIntegrationService
            try:
                TenancyIntegrationService.execute_approved_application(application)
            except Exception as e:
                print(f"⚠️ Error executing approved application integration: {e}")

        return decision_record

    @staticmethod
    def get_reviewer_context(application: Application, reviewer) -> dict:
        screening_profile = ScreeningService.get_tenant_screening_profile(application.applicant, reviewer)
        
        if application.application_type == Application.ApplicationType.RENTAL:
            conditions = TenancyConditionService.validate_rental_conditions(application.unit, application.applicant)
        elif application.application_type == Application.ApplicationType.TRANSFER:
            transfer_details = getattr(application, 'transfer_details', None) or getattr(application, 'transfer_application', None)
            if transfer_details:
                conditions = TenancyConditionService.validate_transfer_conditions(
                    transfer_details.from_unit, transfer_details.to_unit, application.applicant
                )
            else:
                conditions = {}
        else:
            conditions = {}

        try:
            risk_analysis = RiskAnalyzer.assess_risk(screening_profile, conditions)
        except (AttributeError, TypeError):
            risk_analysis = {"risk_level": "unknown", "message": "Risk analyzer not yet configured."}

        try:
            score_analysis = ScoringEngine.calculate_score(screening_profile, application)
        except (AttributeError, TypeError):
            score_analysis = {"score": 0, "message": "Scoring engine not yet configured."}

        return {
            "screening_profile": screening_profile,
            "tenancy_conditions": conditions,
            "risk_analysis": risk_analysis,
            "score_analysis": score_analysis,
            "recommended_action": DecisionEngine.evaluate_and_route(application, reviewer)
        }