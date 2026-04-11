"""
Financial Repository — YAML-based CRUD for financial data.
Follows the existing repository pattern (project_repository.py, risk_repository.py).
Stores data in users/{user_id}/financial/ with encryption for sensitive fields.
"""
import os
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import yaml

from services.encryption_service import EncryptionService
from models.financial_models import ENCRYPTED_FIELDS

logger = logging.getLogger(__name__)


class FinancialRepository:
    """Repository for managing financial data (targets, actuals, resource costs, profiles)."""

    SUBDIRS = ("targets", "actuals", "resource_costs", "profiles", "attribution", "forecasts", "risks")

    def __init__(self, storage_dir: Optional[str] = None, encryption_service: Optional[EncryptionService] = None):
        if storage_dir is None:
            base = os.getenv("DATA_STORAGE_PATH")
            if base is None:
                base = str(Path(__file__).resolve().parent.parent / "data")
            storage_dir = os.path.join(base, "financial")

        self.storage_dir = storage_dir
        self.encryption = encryption_service or EncryptionService()

        # Ensure sub-directories exist
        for sub in self.SUBDIRS:
            os.makedirs(os.path.join(self.storage_dir, sub), exist_ok=True)

        logger.info(f"FinancialRepository initialised: {self.storage_dir}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path(self, subdir: str, filename: str) -> str:
        return os.path.join(self.storage_dir, subdir, filename)

    def _save_yaml(self, subdir: str, filename: str, data: Any) -> str:
        path = self._path(subdir, filename)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return path

    def _load_yaml(self, subdir: str, filename: str) -> Optional[Any]:
        path = self._path(subdir, filename)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def _list_files(self, subdir: str, suffix: str = ".yaml") -> List[str]:
        d = os.path.join(self.storage_dir, subdir)
        if not os.path.isdir(d):
            return []
        return [f for f in os.listdir(d) if f.endswith(suffix)]

    def _encrypt_record(self, record: dict) -> dict:
        return self.encryption.encrypt_dict_fields(record, ENCRYPTED_FIELDS)

    def _decrypt_record(self, record: dict) -> dict:
        return self.encryption.decrypt_dict_fields(record, ENCRYPTED_FIELDS)

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    # ------------------------------------------------------------------
    # Financial Targets
    # ------------------------------------------------------------------

    def save_target(self, target: dict) -> dict:
        if not target.get("id"):
            target["id"] = str(uuid.uuid4())
        target["updated_at"] = self._now()
        if not target.get("created_at"):
            target["created_at"] = target["updated_at"]

        encrypted = self._encrypt_record(target)
        self._save_yaml("targets", f"{target['id']}.yaml", encrypted)
        return target

    def get_target(self, target_id: str) -> Optional[dict]:
        data = self._load_yaml("targets", f"{target_id}.yaml")
        if data is None:
            return None
        return self._decrypt_record(data)

    def delete_target(self, target_id: str) -> bool:
        path = self._path("targets", f"{target_id}.yaml")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def list_targets(self, program_id: Optional[str] = None,
                     period: Optional[str] = None) -> List[dict]:
        results = []
        for fname in self._list_files("targets"):
            data = self._load_yaml("targets", fname)
            if data is None:
                continue
            data = self._decrypt_record(data)
            if program_id is not None and data.get("program_id") != program_id:
                continue
            if period is not None and data.get("period") != period:
                continue
            results.append(data)
        # Sort by period_start descending
        results.sort(key=lambda x: x.get("period_start", ""), reverse=True)
        return results

    # ------------------------------------------------------------------
    # Financial Actuals
    # ------------------------------------------------------------------

    def save_actual(self, actual: dict) -> dict:
        if not actual.get("id"):
            actual["id"] = str(uuid.uuid4())
        actual["updated_at"] = self._now()
        if not actual.get("created_at"):
            actual["created_at"] = actual["updated_at"]
        if not actual.get("recorded_date"):
            actual["recorded_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        # Auto-calculate margin if not provided
        if actual.get("actual_margin") is None and actual.get("actual_revenue"):
            rev = actual["actual_revenue"]
            cost = actual.get("actual_cost", 0)
            actual["actual_margin"] = round(((rev - cost) / rev) * 100, 2) if rev != 0 else 0.0

        encrypted = self._encrypt_record(actual)
        self._save_yaml("actuals", f"{actual['id']}.yaml", encrypted)
        return actual

    def get_actual(self, actual_id: str) -> Optional[dict]:
        data = self._load_yaml("actuals", f"{actual_id}.yaml")
        if data is None:
            return None
        return self._decrypt_record(data)

    def list_actuals(self, program_id: Optional[str] = None,
                     period: Optional[str] = None) -> List[dict]:
        results = []
        for fname in self._list_files("actuals"):
            data = self._load_yaml("actuals", fname)
            if data is None:
                continue
            data = self._decrypt_record(data)
            if program_id is not None and data.get("program_id") != program_id:
                continue
            if period is not None and data.get("period") != period:
                continue
            results.append(data)
        results.sort(key=lambda x: x.get("period_start", ""))
        return results

    # ------------------------------------------------------------------
    # Resource Costs
    # ------------------------------------------------------------------

    def save_resource_cost(self, cost: dict) -> dict:
        if not cost.get("id"):
            cost["id"] = str(uuid.uuid4())
        cost["updated_at"] = self._now()
        if not cost.get("created_at"):
            cost["created_at"] = cost["updated_at"]

        encrypted = self._encrypt_record(cost)
        self._save_yaml("resource_costs", f"{cost['id']}.yaml", encrypted)
        return cost

    def list_resource_costs(self, program_id: Optional[str] = None,
                            period: Optional[str] = None,
                            cost_type: Optional[str] = None) -> List[dict]:
        results = []
        for fname in self._list_files("resource_costs"):
            data = self._load_yaml("resource_costs", fname)
            if data is None:
                continue
            data = self._decrypt_record(data)
            if program_id is not None and data.get("program_id") != program_id:
                continue
            if period is not None and data.get("period") != period:
                continue
            if cost_type is not None and data.get("cost_type") != cost_type:
                continue
            results.append(data)
        results.sort(key=lambda x: x.get("period_start", ""), reverse=True)
        return results

    def get_resource_cost_summary(self, program_id: Optional[str] = None) -> List[dict]:
        """Aggregate resource costs per program."""
        costs = self.list_resource_costs(program_id=program_id)
        summary: Dict[str, Dict[str, float]] = {}
        for c in costs:
            pid = c.get("program_id", "portfolio")
            if pid not in summary:
                summary[pid] = {"program_id": pid, "total": 0.0,
                                "labour": 0.0, "tools": 0.0,
                                "infrastructure": 0.0, "external": 0.0,
                                "total_hours": 0.0}
            summary[pid]["total"] += c.get("cost_amount", 0)
            ct = c.get("cost_type", "external")
            if ct in summary[pid]:
                summary[pid][ct] += c.get("cost_amount", 0)
            summary[pid]["total_hours"] += c.get("billable_hours", 0) or 0
        return list(summary.values())

    # ------------------------------------------------------------------
    # Program Financial Profiles
    # ------------------------------------------------------------------

    def save_profile(self, profile: dict) -> dict:
        profile["updated_at"] = self._now()
        if not profile.get("created_at"):
            profile["created_at"] = profile["updated_at"]
        pid = profile["program_id"]
        safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in pid)
        self._save_yaml("profiles", f"{safe}.yaml", profile)
        return profile

    def get_profile(self, program_id: str) -> Optional[dict]:
        safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in program_id)
        return self._load_yaml("profiles", f"{safe}.yaml")

    def list_profiles(self) -> List[dict]:
        results = []
        for fname in self._list_files("profiles"):
            data = self._load_yaml("profiles", fname)
            if data:
                results.append(data)
        return results

    # ------------------------------------------------------------------
    # Impact Attribution
    # ------------------------------------------------------------------

    def save_attribution(self, attribution: dict) -> dict:
        pid = attribution["program_id"]
        safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in pid)
        fname = f"{safe}.yaml"

        # Load existing history
        existing = self._load_yaml("attribution", fname) or {"program_id": pid, "entries": []}

        attribution["effective_date"] = attribution.get("effective_date") or self._now()
        existing["entries"].append(attribution)
        self._save_yaml("attribution", fname, existing)
        return attribution

    def get_attribution(self, program_id: str) -> Optional[dict]:
        safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in program_id)
        return self._load_yaml("attribution", f"{safe}.yaml")

    def list_attributions(self) -> List[dict]:
        results = []
        for fname in self._list_files("attribution"):
            data = self._load_yaml("attribution", fname)
            if data:
                results.append(data)
        return results

    def get_current_attribution_pct(self, program_id: str) -> Optional[float]:
        data = self.get_attribution(program_id)
        if not data or not data.get("entries"):
            return None
        return data["entries"][-1].get("attribution_pct")

    # ------------------------------------------------------------------
    # Forecasts (generated, cached)
    # ------------------------------------------------------------------

    def save_forecast(self, forecast: dict) -> dict:
        if not forecast.get("id"):
            forecast["id"] = str(uuid.uuid4())
        forecast["generated_at"] = self._now()
        self._save_yaml("forecasts", f"{forecast['id']}.yaml", forecast)
        return forecast

    def list_forecasts(self, program_id: Optional[str] = None) -> List[dict]:
        results = []
        for fname in self._list_files("forecasts"):
            data = self._load_yaml("forecasts", fname)
            if data is None:
                continue
            if program_id is not None and data.get("program_id") != program_id:
                continue
            results.append(data)
        results.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
        return results

    def clear_forecasts(self, program_id: Optional[str] = None):
        """Delete forecasts, optionally filtered by program."""
        for fname in self._list_files("forecasts"):
            if program_id:
                data = self._load_yaml("forecasts", fname)
                if data and data.get("program_id") != program_id:
                    continue
            path = self._path("forecasts", fname)
            os.remove(path)

    # ------------------------------------------------------------------
    # Financial Risks
    # ------------------------------------------------------------------

    def save_financial_risk(self, risk: dict) -> dict:
        if not risk.get("risk_id"):
            risk["risk_id"] = f"FGSI-{str(uuid.uuid4())[:8].upper()}"
        risk["updated_at"] = self._now()
        if not risk.get("created_at"):
            risk["created_at"] = risk["updated_at"]
        self._save_yaml("risks", f"{risk['risk_id']}.yaml", risk)
        return risk

    def list_financial_risks(self, program_id: Optional[str] = None,
                             status: Optional[str] = None) -> List[dict]:
        results = []
        for fname in self._list_files("risks"):
            data = self._load_yaml("risks", fname)
            if data is None:
                continue
            if program_id is not None and data.get("program_id") != program_id:
                continue
            if status is not None and data.get("status") != status:
                continue
            results.append(data)
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    # ------------------------------------------------------------------
    # Financial Summary (aggregation)
    # ------------------------------------------------------------------

    def get_financial_summary(self, program_id: Optional[str] = None) -> dict:
        """Build aggregated financial summary for dashboard KPIs."""
        targets = self.list_targets(program_id=program_id)
        actuals = self.list_actuals(program_id=program_id)

        total_rev_target = sum(t.get("revenue_target", 0) for t in targets)
        total_cost_budget = sum(t.get("cost_budget", 0) for t in targets)
        total_rev_actual = sum(a.get("actual_revenue", 0) for a in actuals)
        total_cost_actual = sum(a.get("actual_cost", 0) for a in actuals)

        rev_var = ((total_rev_actual - total_rev_target) / total_rev_target * 100) if total_rev_target else 0
        cost_var = ((total_cost_actual - total_cost_budget) / total_cost_budget * 100) if total_cost_budget else 0

        target_margin = None
        actual_margin = None
        if total_rev_target > 0:
            target_margin = round((total_rev_target - total_cost_budget) / total_rev_target * 100, 2)
        if total_rev_actual > 0:
            actual_margin = round((total_rev_actual - total_cost_actual) / total_rev_actual * 100, 2)

        risks = self.list_financial_risks(program_id=program_id, status="OPEN")
        risk_score = len(risks) * 10  # simple score: 10 pts per open risk

        # Per-program breakdown
        program_ids = set()
        for t in targets:
            if t.get("program_id"):
                program_ids.add(t["program_id"])
        for a in actuals:
            if a.get("program_id"):
                program_ids.add(a["program_id"])

        program_summaries = []
        for pid in program_ids:
            pt = [t for t in targets if t.get("program_id") == pid]
            pa = [a for a in actuals if a.get("program_id") == pid]
            profile = self.get_profile(pid)
            prog_rev_target = sum(t.get("revenue_target", 0) for t in pt)
            prog_rev_actual = sum(a.get("actual_revenue", 0) for a in pa)
            prog_cost_budget = sum(t.get("cost_budget", 0) for t in pt)
            prog_cost_actual = sum(a.get("actual_cost", 0) for a in pa)
            program_summaries.append({
                "program_id": pid,
                "contribution_type": (profile or {}).get("contribution_type", "direct_revenue"),
                "revenue_target": prog_rev_target,
                "revenue_actual": prog_rev_actual,
                "cost_budget": prog_cost_budget,
                "cost_actual": prog_cost_actual,
                "variance_pct": round(((prog_rev_actual - prog_rev_target) / prog_rev_target * 100), 2) if prog_rev_target else 0,
            })

        return {
            "total_revenue_target": total_rev_target,
            "total_revenue_actual": total_rev_actual,
            "total_cost_budget": total_cost_budget,
            "total_cost_actual": total_cost_actual,
            "target_margin": target_margin,
            "actual_margin": actual_margin,
            "revenue_variance_pct": round(rev_var, 2),
            "cost_variance_pct": round(cost_var, 2),
            "net_profit": round(total_rev_actual - total_cost_actual, 2),
            "net_profit_target": round(total_rev_target - total_cost_budget, 2),
            "profit_margin": actual_margin,
            "profit_variance_pct": round(
                ((total_rev_actual - total_cost_actual) - (total_rev_target - total_cost_budget))
                / (total_rev_target - total_cost_budget) * 100, 2
            ) if (total_rev_target - total_cost_budget) != 0 else 0,
            "financial_risk_score": risk_score,
            "on_track": rev_var >= -5 and cost_var <= 5,
            "program_count": len(program_ids),
            "program_summaries": program_summaries,
        }
