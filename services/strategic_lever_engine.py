"""
Strategic Lever Recommendation Engine — AI-driven suggestions for corrective
actions based on variance and trajectory analysis. Generates ranked
recommendations: cost reduction, revenue acceleration, resource reallocation,
risk mitigation.
"""
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class StrategicLeverEngine:
    """Generates ranked strategic lever recommendations based on financial analysis."""

    def __init__(self, financial_repo):
        self.repo = financial_repo

    def generate_levers(self, program_id: Optional[str] = None,
                        period_start: Optional[str] = None,
                        period_end: Optional[str] = None) -> List[dict]:
        """
        Analyse current financial state and generate strategic lever recommendations.
        Returns list of lever dicts ranked by estimated_impact descending.
        """
        levers = []

        summary = self.repo.get_financial_summary(
            program_id=program_id,
            period_start=period_start,
            period_end=period_end,
        )
        if not summary:
            return levers

        rev_var = summary.get("revenue_variance_pct", 0)
        cost_var = summary.get("cost_variance_pct", 0)
        actual_margin = summary.get("actual_margin")
        target_margin = summary.get("target_margin")
        program_summaries = summary.get("program_summaries", [])

        total_rev_actual = summary.get("total_revenue_actual", 0)
        total_cost_actual = summary.get("total_cost_actual", 0)
        total_rev_target = summary.get("total_revenue_target", 0)
        total_cost_budget = summary.get("total_cost_budget", 0)

        # --- Revenue shortfall levers ---
        if rev_var < -5:
            shortfall = total_rev_target - total_rev_actual
            levers.append({
                "id": str(uuid.uuid4()),
                "title": "Accelerate Revenue Pipeline",
                "description": f"Revenue is {abs(rev_var):.1f}% below target (£{shortfall:,.0f} gap). "
                               "Prioritise high-probability pipeline opportunities and shorten sales cycles.",
                "lever_type": "revenue_acceleration",
                "estimated_impact": round(shortfall * 0.3, 2),
                "confidence": 0.6,
                "effort_level": "medium",
                "affected_programs": self._underperforming_programs(program_summaries, "revenue"),
                "recommended_timeline": "1-3 months",
                "status": "proposed",
                "generated_at": datetime.utcnow().isoformat(),
            })

        if rev_var < -15:
            levers.append({
                "id": str(uuid.uuid4()),
                "title": "Launch Quick-Win Revenue Initiatives",
                "description": f"Significant revenue gap of {abs(rev_var):.1f}%. "
                               "Identify and fast-track quick-win opportunities: upsells, "
                               "cross-sells, or accelerated delivery milestones.",
                "lever_type": "revenue_acceleration",
                "estimated_impact": round((total_rev_target - total_rev_actual) * 0.15, 2),
                "confidence": 0.45,
                "effort_level": "low",
                "affected_programs": self._underperforming_programs(program_summaries, "revenue"),
                "recommended_timeline": "1-2 months",
                "status": "proposed",
                "generated_at": datetime.utcnow().isoformat(),
            })

        # --- Cost overrun levers ---
        if cost_var > 5:
            overrun = total_cost_actual - total_cost_budget
            levers.append({
                "id": str(uuid.uuid4()),
                "title": "Implement Cost Reduction Programme",
                "description": f"Costs are {cost_var:.1f}% above budget (£{overrun:,.0f} overrun). "
                               "Review non-essential spend categories and renegotiate vendor contracts.",
                "lever_type": "cost_reduction",
                "estimated_impact": round(overrun * 0.4, 2),
                "confidence": 0.65,
                "effort_level": "medium",
                "affected_programs": self._over_budget_programs(program_summaries),
                "recommended_timeline": "1-3 months",
                "status": "proposed",
                "generated_at": datetime.utcnow().isoformat(),
            })

        if cost_var > 15:
            levers.append({
                "id": str(uuid.uuid4()),
                "title": "Emergency Spend Freeze on Non-Critical Items",
                "description": f"Cost overrun of {cost_var:.1f}% requires immediate action. "
                               "Freeze discretionary spend and defer non-essential procurement.",
                "lever_type": "cost_reduction",
                "estimated_impact": round((total_cost_actual - total_cost_budget) * 0.25, 2),
                "confidence": 0.75,
                "effort_level": "low",
                "affected_programs": self._over_budget_programs(program_summaries),
                "recommended_timeline": "Immediate",
                "status": "proposed",
                "generated_at": datetime.utcnow().isoformat(),
            })

        # --- Resource reallocation levers ---
        resource_summary = self.repo.get_resource_cost_summary(program_id=program_id)
        if resource_summary and program_summaries:
            high_cost_programs = [r for r in resource_summary if r.get("total", 0) > 0]
            if high_cost_programs and len(program_summaries) > 1:
                levers.append({
                    "id": str(uuid.uuid4()),
                    "title": "Optimise Resource Allocation Across Programs",
                    "description": "Redistribute resources from over-staffed programs "
                                   "to those with higher revenue potential or delivery risk.",
                    "lever_type": "resource_reallocation",
                    "estimated_impact": round(total_cost_actual * 0.05, 2),
                    "confidence": 0.5,
                    "effort_level": "high",
                    "affected_programs": [r.get("program_id") for r in high_cost_programs],
                    "recommended_timeline": "2-4 months",
                    "status": "proposed",
                    "generated_at": datetime.utcnow().isoformat(),
                })

        # --- Margin improvement levers ---
        if actual_margin is not None and target_margin is not None:
            margin_gap = target_margin - actual_margin
            if margin_gap > 3:
                levers.append({
                    "id": str(uuid.uuid4()),
                    "title": "Margin Recovery Plan",
                    "description": f"Margin is {margin_gap:.1f}pp below target "
                                   f"({actual_margin:.1f}% vs {target_margin:.1f}%). "
                                   "Combine cost reduction and revenue acceleration to close gap.",
                    "lever_type": "risk_mitigation",
                    "estimated_impact": round(total_rev_actual * margin_gap / 100, 2),
                    "confidence": 0.55,
                    "effort_level": "high",
                    "affected_programs": [],
                    "recommended_timeline": "3-6 months",
                    "status": "proposed",
                    "generated_at": datetime.utcnow().isoformat(),
                })

        # --- Risk mitigation levers ---
        open_risks = self.repo.list_financial_risks(program_id=program_id, status="OPEN")
        critical_risks = [r for r in open_risks if r.get("severity") in ("critical", "high")]
        if critical_risks:
            levers.append({
                "id": str(uuid.uuid4()),
                "title": "Address Critical Financial Risks",
                "description": f"{len(critical_risks)} high/critical financial risk(s) require "
                               "immediate attention. Implement mitigation actions to prevent "
                               "further financial deterioration.",
                "lever_type": "risk_mitigation",
                "estimated_impact": round(total_rev_target * 0.02 * len(critical_risks), 2),
                "confidence": 0.7,
                "effort_level": "medium",
                "affected_programs": list({r.get("program_id") for r in critical_risks if r.get("program_id")}),
                "recommended_timeline": "Immediate",
                "status": "proposed",
                "generated_at": datetime.utcnow().isoformat(),
            })

        # Sort by estimated_impact descending
        levers.sort(key=lambda l: l.get("estimated_impact", 0), reverse=True)

        # Sanity cap: limit impacts to annualised revenue target to prevent
        # decade-scale sums producing unrealistic recommendations.
        annual_cap = total_rev_target if total_rev_target > 0 else total_cost_budget
        if annual_cap > 0:
            for lever in levers:
                if lever["estimated_impact"] > annual_cap:
                    lever["estimated_impact"] = round(annual_cap, 2)

        # Data maturity: if no actuals recorded, reduce confidence and flag
        if total_rev_actual == 0 and total_cost_actual == 0:
            for lever in levers:
                lever["confidence"] = round(lever["confidence"] * 0.5, 2)
                lever["description"] = "[Limited data] " + lever["description"]

        return levers

    @staticmethod
    def _underperforming_programs(summaries: List[dict], metric: str = "revenue") -> List[str]:
        """Find programs underperforming on a given metric."""
        result = []
        for p in summaries:
            if metric == "revenue" and p.get("variance_pct", 0) < -5:
                result.append(p.get("program_id", ""))
        return result

    @staticmethod
    def _over_budget_programs(summaries: List[dict]) -> List[str]:
        """Find programs over budget."""
        result = []
        for p in summaries:
            cost_actual = p.get("cost_actual", 0)
            cost_budget = p.get("cost_budget", 0)
            if cost_budget > 0 and ((cost_actual - cost_budget) / cost_budget * 100) > 5:
                result.append(p.get("program_id", ""))
        return result
