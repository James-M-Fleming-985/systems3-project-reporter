"""
Forecast Engine — Trajectory analysis and time-series forecasting.
Compares actuals trajectory against targets and generates forward projections
with confidence intervals using linear regression and weighted moving average.
"""
import logging
import math
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ForecastEngine:
    """Financial forecasting engine with trajectory analysis and time-series projection."""

    MIN_DATA_POINTS = 3  # Minimum actuals needed for forecasting

    def __init__(self, financial_repo):
        self.repo = financial_repo

    # ------------------------------------------------------------------
    # Trajectory Analysis
    # ------------------------------------------------------------------

    def analyse_trajectory(self, program_id: Optional[str] = None, metric: str = "revenue") -> dict:
        """
        Compare actuals trajectory against target for a given metric.
        Returns on_track status, variance, run rate, and projected end value.
        """
        actuals = self.repo.list_actuals(program_id=program_id)
        targets = self.repo.list_targets(program_id=program_id)

        if not actuals:
            return {
                "program_id": program_id,
                "metric": metric,
                "on_track": True,
                "variance_pct": 0.0,
                "variance_absolute": 0.0,
                "run_rate": None,
                "projected_end_value": None,
                "target_value": None,
                "data_points": 0,
            }

        # Map metric to fields
        if metric == "revenue":
            actual_field, target_field = "actual_revenue", "revenue_target"
        elif metric == "cost":
            actual_field, target_field = "actual_cost", "cost_budget"
        elif metric == "margin":
            actual_field, target_field = "actual_margin", "margin_target"
        else:
            actual_field, target_field = "actual_revenue", "revenue_target"

        # Sort actuals by period_start
        sorted_actuals = sorted(actuals, key=lambda x: x.get("period_start", ""))
        actual_values = [a.get(actual_field, 0) or 0 for a in sorted_actuals]

        total_actual = sum(actual_values)
        total_target = sum(t.get(target_field, 0) or 0 for t in targets)

        # Run rate: average per period from actuals
        run_rate = total_actual / len(actual_values) if actual_values else 0

        # Projected end value: run_rate × expected number of periods
        n_target_periods = len(targets) if targets else len(actual_values)
        projected_end_value = run_rate * n_target_periods

        # Variance
        variance_abs = total_actual - total_target
        variance_pct = (variance_abs / total_target * 100) if total_target else 0.0

        # On-track thresholds: revenue within -5%, cost within +5%
        if metric == "cost":
            on_track = variance_pct <= 5.0
        else:
            on_track = variance_pct >= -5.0

        return {
            "program_id": program_id,
            "metric": metric,
            "on_track": on_track,
            "variance_pct": round(variance_pct, 2),
            "variance_absolute": round(variance_abs, 2),
            "run_rate": round(run_rate, 2),
            "projected_end_value": round(projected_end_value, 2),
            "target_value": round(total_target, 2),
            "data_points": len(actual_values),
        }

    # ------------------------------------------------------------------
    # Time-Series Forecasting
    # ------------------------------------------------------------------

    def generate_forecasts(
        self,
        program_id: Optional[str] = None,
        horizons: List[int] = None,
    ) -> List[dict]:
        """
        Generate forward-looking forecasts for revenue, cost, and margin.
        Returns list of forecast result dicts saved to repository.
        """
        if horizons is None:
            horizons = [3, 6, 12]

        results = []
        # Clear old forecasts
        self.repo.clear_forecasts(program_id=program_id)

        for metric in ("revenue", "cost", "margin"):
            actuals = self.repo.list_actuals(program_id=program_id)
            targets = self.repo.list_targets(program_id=program_id)

            if metric == "revenue":
                actual_field = "actual_revenue"
                target_field = "revenue_target"
            elif metric == "cost":
                actual_field = "actual_cost"
                target_field = "cost_budget"
            else:
                actual_field = "actual_margin"
                target_field = "margin_target"

            sorted_actuals = sorted(actuals, key=lambda x: x.get("period_start", ""))
            values = [a.get(actual_field, 0) or 0 for a in sorted_actuals]
            dates = [a.get("period_start", "") for a in sorted_actuals]

            total_target = sum(t.get(target_field, 0) or 0 for t in targets)

            if len(values) < self.MIN_DATA_POINTS:
                # Not enough data — still return a stub
                for horizon in horizons:
                    forecast = {
                        "program_id": program_id,
                        "metric": metric,
                        "horizon_months": horizon,
                        "projected_value": 0,
                        "on_track": True,
                        "variance_pct": 0,
                        "forecast_points": [],
                        "confidence_lower_68": None,
                        "confidence_upper_68": None,
                        "confidence_lower_95": None,
                        "confidence_upper_95": None,
                    }
                    saved = self.repo.save_forecast(forecast)
                    results.append(saved)
                continue

            for horizon in horizons:
                forecast = self._project_metric(values, dates, horizon, metric, total_target, program_id)
                saved = self.repo.save_forecast(forecast)
                results.append(saved)

        return results

    def _project_metric(
        self,
        values: List[float],
        dates: List[str],
        horizon_months: int,
        metric: str,
        total_target: float,
        program_id: Optional[str],
    ) -> dict:
        """Project a single metric forward using linear regression + WMA blend."""
        n = len(values)
        x = list(range(n))

        # Linear regression
        slope, intercept = self._linear_regression(x, values)

        # Weighted moving average (recent data weighted more)
        wma = self._weighted_moving_average(values, min(n, 6))

        # Blend: 60% regression, 40% WMA
        blend_weight = 0.6

        forecast_points = []
        last_date = dates[-1] if dates else datetime.utcnow().strftime("%Y-%m-%d")

        try:
            base_date = datetime.strptime(last_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            base_date = datetime.utcnow()

        projected_values = []
        for m in range(1, horizon_months + 1):
            reg_val = slope * (n - 1 + m) + intercept
            blend_val = blend_weight * reg_val + (1 - blend_weight) * wma
            projected_values.append(blend_val)

            point_date = base_date + timedelta(days=30 * m)
            forecast_points.append({
                "date": point_date.strftime("%Y-%m-%d"),
                "value": round(blend_val, 2),
            })

        # Cumulative projected value
        projected_total = sum(values) + sum(projected_values)

        # Confidence intervals based on residual variance
        residuals = [values[i] - (slope * i + intercept) for i in range(n)]
        std_err = math.sqrt(sum(r ** 2 for r in residuals) / max(n - 2, 1))

        # For horizon endpoint
        endpoint = projected_values[-1] if projected_values else 0
        ci_68_lower = round(endpoint - std_err, 2)
        ci_68_upper = round(endpoint + std_err, 2)
        ci_95_lower = round(endpoint - 1.96 * std_err, 2)
        ci_95_upper = round(endpoint + 1.96 * std_err, 2)

        # Add confidence bands to forecast points
        for i, pt in enumerate(forecast_points):
            spread = std_err * math.sqrt(1 + (i + 1) / n)
            pt["lower_68"] = round(pt["value"] - spread, 2)
            pt["upper_68"] = round(pt["value"] + spread, 2)
            pt["lower_95"] = round(pt["value"] - 1.96 * spread, 2)
            pt["upper_95"] = round(pt["value"] + 1.96 * spread, 2)

        # Variance against target
        variance_pct = ((projected_total - total_target) / total_target * 100) if total_target else 0

        if metric == "cost":
            on_track = variance_pct <= 5.0
        else:
            on_track = variance_pct >= -5.0

        return {
            "program_id": program_id,
            "metric": metric,
            "horizon_months": horizon_months,
            "projected_value": round(projected_total, 2),
            "on_track": on_track,
            "variance_pct": round(variance_pct, 2),
            "forecast_points": forecast_points,
            "confidence_lower_68": ci_68_lower,
            "confidence_upper_68": ci_68_upper,
            "confidence_lower_95": ci_95_lower,
            "confidence_upper_95": ci_95_upper,
        }

    # ------------------------------------------------------------------
    # Statistical helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _linear_regression(x: List[float], y: List[float]) -> Tuple[float, float]:
        """Simple OLS linear regression. Returns (slope, intercept)."""
        n = len(x)
        if n < 2:
            return (0.0, y[0] if y else 0.0)

        sx = sum(x)
        sy = sum(y)
        sxy = sum(xi * yi for xi, yi in zip(x, y))
        sxx = sum(xi * xi for xi in x)

        denom = n * sxx - sx * sx
        if denom == 0:
            return (0.0, sy / n)

        slope = (n * sxy - sx * sy) / denom
        intercept = (sy - slope * sx) / n
        return (slope, intercept)

    @staticmethod
    def _weighted_moving_average(values: List[float], window: int) -> float:
        """Weighted moving average with linearly increasing weights (recent = higher)."""
        if not values:
            return 0.0
        recent = values[-window:]
        weights = list(range(1, len(recent) + 1))
        total_weight = sum(weights)
        return sum(w * v for w, v in zip(weights, recent)) / total_weight
