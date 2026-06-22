
class ScoringEngine:
    """
    Calculates an objective numerical score for an applicant (0-100).
    Used by reviewers and the Decision Engine to quantify applicant reliability.
    """

    @staticmethod
    def calculate_score(screening_profile: dict, application) -> dict:
        """
        Returns: {"score": int, "rating": str, "factors": list}
        """
        score = 50  # Base starting score
        factors = []

        # 1. Employment Status Factor
        if hasattr(application, 'rental_details'):
            status = application.rental_details.employment_status
            if status in ['employed', 'self_employed']:
                score += 10
                factors.append("Stable employment confirmed")
            elif status == 'unemployed':
                score -= 15
                factors.append("Unemployed status")

        # 2. Historical Tenancy Performance
        history = screening_profile.get('history_records', [])
        successful_completions = sum(
            1 for h in history 
            if h['final_status'] in ['terminated', 'expired'] and 'breach' not in h.get('termination_reason', '').lower()
        )
        score += min(successful_completions * 5, 20)
        if successful_completions > 0:
            factors.append(f"{successful_completions} successful past tenancies")

        # 3. Negative History Deductions
        breaches_or_evictions = sum(
            1 for h in history 
            if 'breach' in h.get('termination_reason', '').lower() or h['final_status'] == 'terminated'
        )
        score -= min(breaches_or_evictions * 15, 30)
        if breaches_or_evictions > 0:
            factors.append(f"{breaches_or_evictions} past breach/termination record(s)")

        # 4. System Blocking Flags
        if screening_profile.get('tenant_has_blocking_flags', False):
            score -= 20
            factors.append("System blocking flags detected")

        # 5. Cap & Rating Assignment
        score = max(0, min(100, score))
        
        if score >= 80:
            rating = "Excellent"
        elif score >= 60:
            rating = "Good"
        elif score >= 40:
            rating = "Fair"
        else:
            rating = "Poor"

        return {
            "score": score,
            "rating": rating,
            "factors": factors
        }