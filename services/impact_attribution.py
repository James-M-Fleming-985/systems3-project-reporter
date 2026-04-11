"""
Impact Attribution Service — Manages attribution percentages for indirect-revenue
programs, tracks history, and provides data-backed confidence scoring by
correlating indirect program activity with financial outcomes.
"""
import logging
import math
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ImpactAttributionService:
    """Manages impact attribution for indirect-revenue programs."""

    def __init__(self, financial_repo):
        self.repo = financial_repo

    def set_attribution(
        self,
        program_id: str,
        attribution_pct: float,
        notes: Optional[str] = None,
        set_by: str = "manual",
    ) -> dict:
        """
        Set attribution percentage for an indirect program.
        Validates against total allocation across all programs.
        """
        if not (0 <= attribution_pct <= 100):
            raise ValueError("attribution_pct must be between 0 and 100")

        # Check total allocation doesn't exceed 100
        current_total = self._total_attribution_excluding(program_id)
        if current_total + attribution_pct > 100:
            raise ValueError(
                f"Total attribution would be {current_total + attribution_pct:.1f}% "
                f"(max 100%). Current allocation across other programs: {current_total:.1f}%"
            )

        attribution = {
            "program_id": program_id,
            "attribution_pct": attribution_pct,
            "set_by": set_by,
            "notes": notes,
            "confidence_score": self._calculate_confidence(program_id),
        }

        saved = self.repo.save_attribution(attribution)
        return saved

    def get_current(self, program_id: str) -> Optional[dict]:
        """Get current attribution for a program."""
        data = self.repo.get_attribution(program_id)
        if not data or not data.get("entries"):
            return None
        latest = data["entries"][-1]
        latest["history_count"] = len(data["entries"])
        return latest

    def get_history(self, program_id: str) -> List[dict]:
        """Get full attribution history for a program."""
        data = self.repo.get_attribution(program_id)
        if not data:
            return []
        return data.get("entries", [])

    def get_all_current(self) -> List[dict]:
        """Get current attribution for all indirect programs."""
        attributions = self.repo.list_attributions()
        result = []
        for attr in attributions:
            entries = attr.get("entries", [])
            if entries:
                latest = entries[-1]
                latest["history_count"] = len(entries)
                result.append(latest)
        return result

    def _total_attribution_excluding(self, exclude_program_id: str) -> float:
        """Sum of all current attribution percentages excluding the given program."""
        total = 0.0
        for attr in self.repo.list_attributions():
            entries = attr.get("entries", [])
            if entries:
                latest = entries[-1]
                if latest.get("program_id") != exclude_program_id:
                    total += latest.get("attribution_pct", 0)
        return total

    def _calculate_confidence(self, program_id: str) -> float:
        """
        Calculate data-backed confidence score (0-1) for an attribution.
        Based on:
        - Amount of historical actuals data
        - Consistency of attribution changes
        - Correlation between program activity periods and revenue changes
        """
        actuals = self.repo.list_actuals(program_id=program_id)
        history = self.repo.get_attribution(program_id)

        # Base confidence from data availability
        data_points = len(actuals)
        if data_points == 0:
            return 0.2  # Low confidence with no data
        elif data_points < 3:
            data_score = 0.3
        elif data_points < 6:
            data_score = 0.5
        elif data_points < 12:
            data_score = 0.7
        else:
            data_score = 0.85

        # Consistency bonus: fewer attribution changes = more stable = higher confidence
        consistency_score = 1.0
        if history and history.get("entries"):
            changes = len(history["entries"])
            if changes > 5:
                consistency_score = 0.6
            elif changes > 3:
                consistency_score = 0.8

        # Correlation factor: check if program's actuals correlate with portfolio revenue
        correlation_score = self._estimate_correlation(program_id)

        # Weighted combination
        confidence = (data_score * 0.4 + consistency_score * 0.3 + correlation_score * 0.3)
        return round(min(confidence, 1.0), 2)

    def _estimate_correlation(self, program_id: str) -> float:
        """
        Estimate correlation between this program's costs and portfolio revenue.
        Higher correlation suggests the program's impact attribution is valid.
        """
        program_actuals = self.repo.list_actuals(program_id=program_id)
        portfolio_actuals = self.repo.list_actuals(program_id=None)

        if len(program_actuals) < 3 or len(portfolio_actuals) < 3:
            return 0.5  # Neutral when insufficient data

        # Build time-aligned series
        program_by_period = {}
        for a in program_actuals:
            key = a.get("period_start", "")
            program_by_period[key] = a.get("actual_cost", 0) or 0

        portfolio_by_period = {}
        for a in portfolio_actuals:
            key = a.get("period_start", "")
            portfolio_by_period[key] = portfolio_by_period.get(key, 0) + (a.get("actual_revenue", 0) or 0)

        # Find common periods
        common = sorted(set(program_by_period.keys()) & set(portfolio_by_period.keys()))
        if len(common) < 3:
            return 0.5

        x = [program_by_period[k] for k in common]
        y = [portfolio_by_period[k] for k in common]

        # Pearson correlation
        r = self._pearson_r(x, y)

        # Map correlation to 0-1 score (negative correlation = low score)
        return round(max(0, (r + 1) / 2), 2)

    @staticmethod
    def _pearson_r(x: List[float], y: List[float]) -> float:
        """Compute Pearson correlation coefficient."""
        n = len(x)
        if n < 2:
            return 0.0

        mx = sum(x) / n
        my = sum(y) / n

        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        dx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        dy = math.sqrt(sum((yi - my) ** 2 for yi in y))

        if dx == 0 or dy == 0:
            return 0.0

        return num / (dx * dy)
