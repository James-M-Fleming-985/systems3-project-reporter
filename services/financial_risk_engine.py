"""
Financial Risk Engine — Auto-generates financial risk entries when variance
exceeds configurable thresholds. Integrates with existing risk scoring
(likelihood × impact) pattern.
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Default variance thresholds (percentage)
DEFAULT_THRESHOLDS = {
    "budget_overrun": 10.0,       # cost actual > budget by this %
    "revenue_shortfall": -10.0,   # revenue actual below target by this %
    "margin_erosion": -5.0,       # margin below target by this %
    "resource_utilisation": 15.0, # resource cost growth rate exceeds this %
}

# Severity mapping based on variance magnitude
SEVERITY_BANDS = [
    (30.0, "critical", "high"),
    (20.0, "high", "high"),
    (10.0, "medium", "medium"),
    (0.0, "low", "low"),
]


class FinancialRiskEngine:
    """Evaluates financial data and auto-generates risks when thresholds breached."""

    def __init__(self, financial_repo, thresholds: Optional[Dict[str, float]] = None):
        self.repo = financial_repo
        self.thresholds = thresholds or dict(DEFAULT_THRESHOLDS)

    def evaluate_risks(self, program_id: Optional[str] = None) -> List[dict]:
        """
        Evaluate all financial data and generate risks for breached thresholds.
        Returns list of newly generated risk dicts.
        """
        generated = []

        if program_id:
            # Evaluate specific program only
            generated.extend(self._evaluate_program(program_id))
        else:
            # Evaluate each program individually
            program_ids = self._get_program_ids(None)
            for pid in program_ids:
                generated.extend(self._evaluate_program(pid))
            # Also evaluate portfolio-level targets (program_id=None in data)
            portfolio_targets = [t for t in self.repo.list_targets() if not t.get("program_id")]
            if portfolio_targets:
                generated.extend(self._evaluate_program(None))

        return generated

    def _get_program_ids(self, program_id: Optional[str] = None) -> set:
        """Get all program IDs that have financial data."""
        if program_id:
            return {program_id}

        ids = set()
        for t in self.repo.list_targets():
            if t.get("program_id"):
                ids.add(t["program_id"])
        for a in self.repo.list_actuals():
            if a.get("program_id"):
                ids.add(a["program_id"])
        return ids

    def _evaluate_program(self, program_id: Optional[str]) -> List[dict]:
        """Evaluate a single program (or portfolio if program_id is None)."""
        risks = []
        targets = self.repo.list_targets(program_id=program_id)
        actuals = self.repo.list_actuals(program_id=program_id)

        if not targets or not actuals:
            return risks

        total_rev_target = sum(t.get("revenue_target", 0) for t in targets)
        total_cost_budget = sum(t.get("cost_budget", 0) for t in targets)
        total_rev_actual = sum(a.get("actual_revenue", 0) for a in actuals)
        total_cost_actual = sum(a.get("actual_cost", 0) for a in actuals)

        # --- Budget Overrun ---
        if total_cost_budget > 0:
            cost_var_pct = ((total_cost_actual - total_cost_budget) / total_cost_budget) * 100
            if cost_var_pct > self.thresholds["budget_overrun"]:
                risk = self._create_risk(
                    risk_type="budget_overrun",
                    description=f"Cost actual exceeds budget by {cost_var_pct:.1f}% "
                                f"(£{total_cost_actual:,.0f} vs £{total_cost_budget:,.0f} budget)",
                    variance_pct=abs(cost_var_pct),
                    trigger_metric="cost",
                    program_id=program_id,
                    mitigation="Review cost drivers and identify reduction opportunities. "
                               "Consider resource reallocation or scope adjustments.",
                )
                risks.append(risk)

        # --- Revenue Shortfall ---
        if total_rev_target > 0:
            rev_var_pct = ((total_rev_actual - total_rev_target) / total_rev_target) * 100
            if rev_var_pct < self.thresholds["revenue_shortfall"]:
                risk = self._create_risk(
                    risk_type="revenue_shortfall",
                    description=f"Revenue trailing target by {abs(rev_var_pct):.1f}% "
                                f"(£{total_rev_actual:,.0f} vs £{total_rev_target:,.0f} target)",
                    variance_pct=abs(rev_var_pct),
                    trigger_metric="revenue",
                    program_id=program_id,
                    mitigation="Accelerate revenue-generating activities. "
                               "Review pipeline health and conversion rates.",
                )
                risks.append(risk)

        # --- Margin Erosion ---
        if total_rev_target > 0 and total_rev_actual > 0:
            target_margin = ((total_rev_target - total_cost_budget) / total_rev_target) * 100
            actual_margin = ((total_rev_actual - total_cost_actual) / total_rev_actual) * 100
            margin_var = actual_margin - target_margin
            if margin_var < self.thresholds["margin_erosion"]:
                risk = self._create_risk(
                    risk_type="margin_erosion",
                    description=f"Margin eroding: {actual_margin:.1f}% actual vs "
                                f"{target_margin:.1f}% target (variance {margin_var:.1f}%)",
                    variance_pct=abs(margin_var),
                    trigger_metric="margin",
                    program_id=program_id,
                    mitigation="Investigate cost increases relative to revenue. "
                               "Consider pricing adjustments or cost optimization.",
                )
                risks.append(risk)

        # --- Resource Utilisation ---
        resource_costs = self.repo.list_resource_costs(program_id=program_id)
        if resource_costs and total_rev_actual > 0:
            total_resource_cost = sum(c.get("cost_amount", 0) for c in resource_costs)
            resource_ratio = (total_resource_cost / total_rev_actual) * 100
            if resource_ratio > self.thresholds["resource_utilisation"]:
                risk = self._create_risk(
                    risk_type="resource_utilisation",
                    description=f"Resource costs consuming {resource_ratio:.1f}% of revenue "
                                f"(£{total_resource_cost:,.0f} resources vs £{total_rev_actual:,.0f} revenue)",
                    variance_pct=resource_ratio,
                    trigger_metric="resource_cost",
                    program_id=program_id,
                    mitigation="Review resource allocation efficiency. "
                               "Identify underutilised resources and optimise deployment.",
                )
                risks.append(risk)

        # Save generated risks and deduplicate against existing
        saved = []
        existing = self.repo.list_financial_risks(program_id=program_id, status="OPEN")
        existing_types = {r.get("risk_type") for r in existing}

        for risk in risks:
            if risk["risk_type"] not in existing_types:
                s = self.repo.save_financial_risk(risk)
                saved.append(s)
            else:
                logger.debug(f"Risk type {risk['risk_type']} already exists for {program_id}, skipping")

        return saved

    def _create_risk(
        self,
        risk_type: str,
        description: str,
        variance_pct: float,
        trigger_metric: str,
        program_id: Optional[str],
        mitigation: str = "",
    ) -> dict:
        """Create a risk dict with severity based on variance magnitude."""
        severity, probability = self._classify_severity(variance_pct)

        return {
            "risk_id": None,  # Will be assigned by repo
            "description": description,
            "risk_type": risk_type,
            "severity": severity,
            "probability": probability,
            "impact": severity,  # Align with existing risk scoring
            "mitigation": mitigation,
            "status": "OPEN",
            "program_id": program_id,
            "trigger_metric": trigger_metric,
            "trigger_variance_pct": round(variance_pct, 2),
        }

    @staticmethod
    def _classify_severity(variance_pct: float) -> tuple:
        """Map variance magnitude to severity and probability labels."""
        abs_var = abs(variance_pct)
        for threshold, severity, probability in SEVERITY_BANDS:
            if abs_var >= threshold:
                return severity, probability
        return "low", "low"
