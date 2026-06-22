from django.core.exceptions import ValidationError
from ..models import Application, ApplicationDecision, ApplicationNote
from .tenancy_condition_service import TenancyConditionService
from ..utils.scoring_engine import ScoringEngine
from ..utils.risk_analyzer import RiskAnalyzer
from .screening_service import ScreeningService

class DecisionEngine:
    """
    Evaluates application conditions and automatically routes the decision workflow.
    Enforces the rule: Agents can ONLY approve if ALL conditions are met. Otherwise, escalate.
    """

    @staticmethod
    def evaluate_and_route(application: Application, reviewer) -> str:
        """
        Evaluates the application and returns the required action: 'approve', 'escalate', or 'reject'.
        """
        if application.application_type == Application.ApplicationType.RENTAL:
            conditions = TenancyConditionService.validate_rental_conditions(
                application.unit, application.applicant
            )
        elif application.application_type == Application.ApplicationType.TRANSFER:
            transfer_details = application.transfer_details
            conditions = TenancyConditionService.validate_transfer_conditions(
                transfer_details.from_unit, transfer_details.to_unit, application.applicant
            )
        else:
            # Eviction notices follow a different workflow (manager approval for handover)
            return 'escalate' 

        # CORE BUSINESS RULE:
        # If ANY condition fails or there are blocking flags, an Agent CANNOT approve.
        # It MUST be escalated to a Manager.
        if not conditions["all_conditions_met"] or conditions["has_blocking_flags"]:
            return 'escalate'
            
        # If all conditions are perfectly met, the Agent is authorized to approve.
        return 'approve'

    @staticmethod
    def record_decision(application: Application, decision: str, reviewer, reason: str = "") -> ApplicationDecision:
        """
        Records the final decision, updates the application status, and logs the action.
        """
        valid_decisions = ['approved', 'rejected', 'escalated']
        if decision not in valid_decisions:
            raise ValidationError(f"Invalid decision. Must be one of: {valid_decisions}")

        # 1. Enforce Agent Escalation Rule
        if reviewer.role == 'agent' and decision == 'approved':
            required_action = DecisionEngine.evaluate_and_route(application, reviewer)
            if required_action == 'escalate':
                raise ValidationError(
                    "Agent approval denied: Not all tenancy conditions are met. This application must be escalated to a Manager."
                )

        # 2. Update Application Status
        status_map = {
            'approved': Application.Status.APPROVED,
            'rejected': Application.Status.REJECTED,
            'escalated': Application.Status.ESCALATED
        }
        application.status = status_map[decision]
        application.save(update_fields=['status'])

        # 3. Create Immutable Decision Record
        decision_record = ApplicationDecision.objects.create(
            application=application,
            decision=decision,
            approver=reviewer,
            approver_role=reviewer.role,
            reason=reason
        )

        # 4. Auto-generate a system note for audit trail
        note_type = ApplicationNote.NoteType.ESCALATION_REASON if decision == 'escalated' else ApplicationNote.NoteType.MANAGER_REMARK
        ApplicationNote.objects.create(
            application=application,
            note_type=note_type,
            content=f"Application {decision} by {reviewer.role}. Reason: {reason or 'No reason provided'}",
            created_by=reviewer
        )

        # 5. If approved, trigger tenancy creation/transfer (handled by integration service)
        if decision == 'approved':
            from .tennacy_intergration_service import TenancyIntegrationService
            TenancyIntegrationService.execute_approved_application(application)

        return decision_record

    @staticmethod
    def get_reviewer_context(application: Application, reviewer) -> dict:
        """
        Provides the reviewer with all necessary context (screening profile, risk analysis, conditions) 
        before they make a decision.
        """
        screening_profile = ScreeningService.get_tenant_screening_profile(application.applicant, reviewer)
        
        if application.application_type == Application.ApplicationType.RENTAL:
            conditions = TenancyConditionService.validate_rental_conditions(application.unit, application.applicant)
        elif application.application_type == Application.ApplicationType.TRANSFER:
            transfer_details = application.transfer_details
            conditions = TenancyConditionService.validate_transfer_conditions(
                transfer_details.from_unit, transfer_details.to_unit, application.applicant
            )
        else:
            conditions = {}

        risk_analysis = RiskAnalyzer.assess_risk(screening_profile, conditions)
        score_analysis = ScoringEngine.calculate_score(screening_profile, application)

        return {
            "screening_profile": screening_profile,
            "tenancy_conditions": conditions,
            "risk_analysis": risk_analysis,
            "score_analysis": score_analysis,
            "recommended_action": DecisionEngine.evaluate_and_route(application, reviewer)
        }