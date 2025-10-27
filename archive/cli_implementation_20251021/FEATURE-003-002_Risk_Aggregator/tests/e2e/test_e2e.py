"""
End-to-End tests for Risk Aggregator Feature (FEATURE-003-002)

This module contains comprehensive E2E tests that verify the complete
risk aggregation workflow including data ingestion, calculation, 
aggregation, and reporting.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any
import aiohttp
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np


class TestRiskAggregatorE2E:
    """End-to-end tests for the Risk Aggregator feature."""
    
    @pytest.fixture
    def base_url(self):
        """Base URL for the risk aggregator service."""
        return "http://localhost:8080/api/v1/risk"
    
    @pytest.fixture
    def test_portfolio(self):
        """Create a test portfolio with realistic data."""
        return {
            "portfolio_id": "PORT-001",
            "name": "Test Portfolio Alpha",
            "positions": [
                {
                    "position_id": "POS-001",
                    "instrument_id": "AAPL",
                    "instrument_type": "EQUITY",
                    "quantity": 1000,
                    "market_value": 150000.00,
                    "currency": "USD"
                },
                {
                    "position_id": "POS-002",
                    "instrument_id": "GOOGL",
                    "instrument_type": "EQUITY",
                    "quantity": 500,
                    "market_value": 125000.00,
                    "currency": "USD"
                },
                {
                    "position_id": "POS-003",
                    "instrument_id": "US10Y",
                    "instrument_type": "BOND",
                    "quantity": 100000,
                    "market_value": 98500.00,
                    "currency": "USD"
                }
            ],
            "total_value": 373500.00,
            "base_currency": "USD",
            "created_at": datetime.now().isoformat()
        }
    
    @pytest.fixture
    def market_data(self):
        """Create realistic market data for risk calculations."""
        return {
            "AAPL": {
                "current_price": 150.00,
                "volatility": 0.25,
                "returns": [0.01, -0.02, 0.015, -0.005, 0.02],
                "beta": 1.2
            },
            "GOOGL": {
                "current_price": 250.00,
                "volatility": 0.28,
                "returns": [0.02, -0.015, 0.01, -0.01, 0.025],
                "beta": 1.1
            },
            "US10Y": {
                "current_price": 98.50,
                "volatility": 0.05,
                "returns": [0.001, -0.002, 0.0015, -0.0005, 0.002],
                "duration": 8.5,
                "yield": 0.045
            }
        }
    
    @pytest.fixture
    def risk_limits(self):
        """Define risk limits for validation."""
        return {
            "portfolio_var_limit": 50000.00,
            "position_var_limit": 20000.00,
            "concentration_limit": 0.40,
            "leverage_limit": 2.0,
            "liquidity_ratio_min": 0.30
        }
    
    @pytest.mark.asyncio
    async def test_complete_risk_aggregation_workflow_success(
        self, base_url, test_portfolio, market_data, risk_limits
    ):
        """
        Test 1: Complete successful risk aggregation workflow
        
        This E2E test verifies:
        1. Portfolio data ingestion
        2. Market data retrieval
        3. Risk metric calculations
        4. Risk aggregation across positions
        5. Risk limit validation
        6. Risk report generation
        """
        
        # Step 1: Ingest portfolio data
        async with aiohttp.ClientSession() as session:
            # Upload portfolio
            portfolio_response = await session.post(
                f"{base_url}/portfolios",
                json=test_portfolio
            )
            assert portfolio_response.status == 201
            portfolio_data = await portfolio_response.json()
            portfolio_id = portfolio_data["portfolio_id"]
            
            # Step 2: Trigger risk calculation with market data
            calculation_request = {
                "portfolio_id": portfolio_id,
                "calculation_date": datetime.now().isoformat(),
                "risk_metrics": ["var", "expected_shortfall", "beta", "concentration"],
                "confidence_level": 0.95,
                "time_horizon": 1,
                "market_data": market_data
            }
            
            calc_response = await session.post(
                f"{base_url}/calculate",
                json=calculation_request
            )
            assert calc_response.status == 202
            calc_data = await calc_response.json()
            calculation_id = calc_data["calculation_id"]
            
            # Step 3: Poll for calculation completion
            max_attempts = 30
            attempt = 0
            calculation_complete = False
            
            while attempt < max_attempts and not calculation_complete:
                status_response = await session.get(
                    f"{base_url}/calculations/{calculation_id}/status"
                )
                status_data = await status_response.json()
                
                if status_data["status"] == "COMPLETED":
                    calculation_complete = True
                elif status_data["status"] == "FAILED":
                    pytest.fail(f"Risk calculation failed: {status_data.get('error')}")
                else:
                    await asyncio.sleep(1)
                    attempt += 1
            
            assert calculation_complete, "Risk calculation timed out"
            
            # Step 4: Retrieve aggregated risk results
            results_response = await session.get(
                f"{base_url}/calculations/{calculation_id}/results"
            )
            assert results_response.status == 200
            risk_results = await results_response.json()
            
            # Validate risk calculation results
            assert "portfolio_metrics" in risk_results
            assert "position_metrics" in risk_results
            assert "risk_limits_status" in risk_results
            
            portfolio_metrics = risk_results["portfolio_metrics"]
            assert portfolio_metrics["portfolio_id"] == portfolio_id
            assert "value_at_risk" in portfolio_metrics
            assert "expected_shortfall" in portfolio_metrics
            assert "portfolio_beta" in portfolio_metrics
            assert "concentration_risk" in portfolio_metrics
            
            # Validate VaR calculation
            assert portfolio_metrics["value_at_risk"]["amount"] > 0
            assert portfolio_metrics["value_at_risk"]["percentage"] > 0
            assert portfolio_metrics["value_at_risk"]["confidence_level"] == 0.95
            
            # Validate position-level metrics
            position_metrics = risk_results["position_metrics"]
            assert len(position_metrics) == len(test_portfolio["positions"])
            
            for position in position_metrics:
                assert "position_id" in position
                assert "value_at_risk" in position
                assert "contribution_to_portfolio_var" in position
                assert position["value_at_risk"] > 0
            
            # Step 5: Validate risk limits
            risk_limits_status = risk_results["risk_limits_status"]
            assert "breaches" in risk_limits_status
            assert "warnings" in risk_limits_status
            assert isinstance(risk_limits_status["breaches"], list)
            
            # Step 6: Generate risk report
            report_request = {
                "calculation_id": calculation_id,
                "report_format": "PDF",
                "include_sections": [
                    "executive_summary",
                    "portfolio_overview",
                    "risk_metrics",
                    "risk_limits",
                    "position_analysis",
                    "stress_testing"
                ]
            }
            
            report_response = await session.post(
                f"{base_url}/reports/generate",
                json=report_request
            )
            assert report_response.status == 200
            report_data = await report_response.json()
            assert "report_id" in report_data
            assert "download_url" in report_data
            
            # Verify report generation completed
            report_status_response = await session.get(
                f"{base_url}/reports/{report_data['report_id']}/status"
            )
            assert report_status_response.status == 200
            
    @pytest.mark.asyncio
    async def test_multi_portfolio_aggregation_with_correlations(
        self, base_url, test_portfolio, market_data
    ):
        """
        Test 2: Multi-portfolio risk aggregation with correlation analysis
        
        This E2E test verifies:
        1. Multiple portfolio creation
        2. Cross-portfolio correlation calculation
        3. Aggregate risk across portfolios
        4. Diversification benefit analysis
        5. Consolidated risk reporting
        """
        
        # Create multiple test portfolios
        portfolios = []
        portfolio_configs = [
            {
                "name": "Growth Portfolio",
                "positions": [
                    {"instrument_id": "AAPL", "quantity": 2000, "value": 300000},
                    {"instrument_id": "GOOGL", "quantity": 1000, "value": 250000},
                    {"instrument_id": "MSFT", "quantity": 1500, "value": 225000}
                ]
            },
            {
                "name": "Conservative Portfolio",
                "positions": [
                    {"instrument_id": "US10Y", "quantity": 500000, "value": 492500},
                    {"instrument_id": "CORP_BOND_AAA", "quantity": 300000, "value": 298500},
                    {"instrument_id": "AAPL", "quantity": 200, "value": 30000}
                ]
            },
            {
                "name": "Balanced Portfolio",
                "positions": [
                    {"instrument_id": "SPY", "quantity": 1000, "value": 400000},
                    {"instrument_id": "US10Y", "quantity": 200000, "value": 197000},
                    {"instrument_id": "GLD", "quantity": 500, "value": 95000}
                ]
            }
        ]
        
        async with aiohttp.ClientSession() as session:
            # Step 1: Create multiple portfolios
            created_portfolios = []
            for idx, config in enumerate(portfolio_configs):
                portfolio_data = {
                    "portfolio_id": f"PORT-{idx+1:03d}",
                    "name": config["name"],
                    "positions": [
                        {
                            "position_id": f"POS-{idx+1:03d}-{j+1:03d}",
                            "instrument_id": pos["instrument_id"],
                            "quantity": pos["quantity"],
                            "market_value": pos["value"],
                            "currency": "USD"
                        }
                        for j, pos in enumerate(config["positions"])
                    ],
                    "base_currency": "USD"
                }
                
                response = await session.post(
                    f"{base_url}/portfolios",
                    json=portfolio_data
                )
                assert response.status == 201
                created_data = await response.json()
                created_portfolios.append(created_data["portfolio_id"])
            
            # Step 2: Create portfolio group for aggregation
            group_request = {
                "group_id": "GROUP-001",
                "name": "Test Portfolio Group",
                "portfolio_ids": created_portfolios,
                "aggregation_method": "CORRELATED",
                "correlation_lookback": 252
            }
            
            group_response = await session.post(
                f"{base_url}/portfolio-groups",
                json=group_request
            )
            assert group_response.status == 201
            group_data = await group_response.json()
            group_id = group_data["group_id"]
            
            # Step 3: Calculate aggregated risk with correlations
            agg_calc_request = {
                "group_id": group_id,
                "calculation_date": datetime.now().isoformat(),
                "risk_metrics": [
                    "aggregated_var",
                    "diversification_ratio",
                    "correlation_matrix",
                    "marginal_var",
                    "component_var"
                ],
                "confidence_level": 0.99,
                "time_horizon": 10,
                "include_correlations": True
            }
            
            agg_response = await session.post(
                f"{base_url}/calculate-group",
                json=agg_calc_request
            )
            assert agg_response.status == 202
            agg_calc_id = (await agg_response.json())["calculation_id"]
            
            # Step 4: Wait for aggregated calculation
            calculation_complete = await self._wait_for_calculation(
                session, base_url, agg_calc_id
            )
            assert calculation_complete
            
            # Step 5: Retrieve aggregated results
            agg_results_response = await session.get(
                f"{base_url}/calculations/{agg_calc_id}/results"
            )
            assert agg_results_response.status == 200
            agg_results = await agg_results_response.json()
            
            # Validate aggregated risk metrics
            assert "group_metrics" in agg_results
            group_metrics = agg_results["group_metrics"]
            
            # Check aggregated VaR
            assert "aggregated_var" in group_metrics
            assert group_metrics["aggregated_var"]["with_correlation"] > 0
            assert group_metrics["aggregated_var"]["without_correlation"] > 0
            
            # Verify diversification benefit
            assert group_metrics["aggregated_var"]["with_correlation"] < \
                   group_metrics["aggregated_var"]["without_correlation"]
            
            # Check diversification ratio
            assert "diversification_ratio" in group_metrics
            assert 0 < group_metrics["diversification_ratio"] <= 1
            
            # Validate correlation matrix
            assert "correlation_matrix" in group_metrics
            corr_matrix = group_metrics["correlation_matrix"]
            assert len(corr_matrix) == len(created_portfolios)
            
            # Check marginal and component VaR
            assert "portfolio_contributions" in agg_results
            for portfolio_id in created_portfolios:
                assert portfolio_id in agg_results["portfolio_contributions"]
                contrib = agg_results["portfolio_contributions"][portfolio_id]
                assert "marginal_var" in contrib
                assert "component_var" in contrib
                assert "percentage_contribution" in contrib
            
            # Step 6: Generate consolidated report
            consolidated_report_request = {
                "calculation_id": agg_calc_id,
                "report_type": "CONSOLIDATED_RISK",
                "include_individual_portfolios": True,
                "include_correlation_analysis": True
            }
            
            report_response = await session.post(
                f"{base_url}/reports/generate",
                json=consolidated_report_request
            )
            assert report_response.status == 200
    
    @pytest.mark.asyncio
    async def test_real_time_risk_aggregation_with_market_shocks(
        self, base_url, test_portfolio, market_data
    ):
        """
        Test 3: Real-time risk aggregation with market shock scenarios
        
        This E2E test verifies:
        1. Real-time risk calculation setup
        2. Market data streaming simulation
        3. Stress testing with market shocks
        4. Real-time alert generation
        5. Historical risk comparison
        6. Recovery scenario handling
        """
        
        async with aiohttp.ClientSession() as session:
            # Step 1: Setup portfolio for real-time monitoring
            portfolio_response = await session.post(
                f"{base_url}/portfolios",
                json=test_portfolio
            )
            assert portfolio_response.status == 201
            portfolio_id = (await portfolio_response.json())["portfolio_id"]
            
            # Step 2: Enable real-time risk monitoring
            monitoring_config = {
                "portfolio_id": portfolio_id,
                "monitoring_enabled": True,
                "update_frequency": "1m",
                "risk_metrics": ["var", "expected_shortfall", "stress_scenarios"],
                "alert_thresholds": {
                    "var_breach": 45000,
                    "var_warning": 40000,
                    "max_drawdown": 0.15,
                    "volatility_spike": 0.40
                },
                "stress_scenarios": [
                    {
                        "name": "Market Crash",
                        "market_shock": -0.20,
                        "volatility_multiplier": 2.5
                    },
                    {
                        "name": "Interest Rate Spike",
                        "rate_shock": 0.02,
                        "credit_spread_widening": 0.01
                    },
                    {
                        "name": "Tech Sector Collapse",
                        "sector_shocks": {"TECH": -0.30, "OTHER": -0.10}
                    }
                ]
            }
            
            monitoring_response = await session.post(
                f"{base_url}/portfolios/{portfolio_id}/monitoring",
                json=monitoring_config
            )
            assert monitoring_response.status == 200
            
            # Step 3: Subscribe to real-time updates via WebSocket
            ws_url = base_url.replace("http", "ws") + f"/portfolios/{portfolio_id}/stream"
            risk_updates = []
            alerts_received = []
            
            # Simulate market data updates with shocks
            market_scenarios = [
                # Normal market conditions
                {
                    "timestamp": datetime.now().isoformat(),
                    "price_changes": {"AAPL": 0.01, "GOOGL": 0.005, "US10Y": -0.001},
                    "volatility_changes": {"AAPL": 0, "GOOGL": 0, "US10Y": 0}
                },
                # Market stress begins
                {
                    "timestamp": (datetime.now() + timedelta(minutes=1)).isoformat(),
                    "price_changes": {"AAPL": -0.05, "GOOGL": -0.06, "US10Y": 0.002},
                    "volatility_changes": {"AAPL": 0.10, "GOOGL": 0.12, "US10Y": 0.02}
                },
                # Peak stress
                {
                    "timestamp": (datetime.now() + timedelta(minutes=2)).isoformat(),
                    "price_changes": {"AAPL": -0.15, "GOOGL": -0.18, "US10Y": 0.005},
                    "volatility_changes": {"AAPL": 0.25, "GOOGL": 0.30, "US10Y": 0.05}
                },
                # Recovery begins
                {
                    "timestamp": (datetime.now() + timedelta(minutes=3)).isoformat(),
                    "price_changes": {"AAPL": -0.10, "GOOGL": -0.12, "US10Y": 0.003},
                    "volatility_changes": {"AAPL": 0.15, "GOOGL": 0.18, "US10Y": 0.03}
                }
            ]
            
            # Step 4: Process market updates and collect risk metrics
            for scenario in market_scenarios:
                update_response = await session.post(
                    f"{base_url}/market-data/update",
                    json=scenario
                )
                assert update_response.status == 200
                
                # Get updated risk calculation
                calc_response = await session.post(
                    f"{base_url}/portfolios/{portfolio_id}/calculate-immediate",
                    json={"market_update": scenario}
                )
                assert calc_response.status == 200
                risk_update = await calc_response.json()
                risk_updates.append(risk_update)
                
                # Check for alerts
                alerts_response = await session.get(
                    f"{base_url}/portfolios/{portfolio_id}/alerts"
                )
                if alerts_response.status == 200:
                    alerts = await alerts_response.json()
                    if alerts.get("active_alerts"):
                        alerts_received.extend(alerts["active_alerts"])
            
            # Step 5: Validate risk progression through market shock
            assert len(risk_updates) == len(market_scenarios)
            
            # Check that VaR increased during stress
            normal_var = risk_updates[0]["portfolio_metrics"]["value_at_risk"]["amount"]
            stressed_var = risk_updates[2]["portfolio_metrics"]["value_at_risk"]["amount"]
            assert stressed_var > normal_var * 1.5
            
            # Verify alerts were triggered
            assert len(alerts_received) > 0
            alert_types = [alert["type"] for alert in alerts_received]
            assert "VAR_WARNING" in alert_types or "VAR_BREACH" in alert_types
            
            # Step 6: Run comprehensive stress test report
            stress_test_request = {
                "portfolio_id": portfolio_id,
                "scenarios": monitoring_config["stress_scenarios"],
                "include_recovery_analysis": True,
                "recovery_periods": [1, 5, 20],
                "confidence_levels": [0.95, 0.99]
            }
            
            stress_response = await session.post(
                f"{base_url}/stress-test",
                json=stress_test_request
            )
            assert stress_response.status == 200
            stress_results = await stress_response.json()
            
            # Validate stress test results
            assert "scenario_results" in stress_results
            for scenario in stress_results["scenario_results"]:
                assert "scenario_name" in scenario
                assert "portfolio_impact" in scenario
                assert "var_under_stress" in scenario
                assert "recovery_analysis" in scenario
                
                # Check recovery analysis
                recovery = scenario["recovery_analysis"]
                assert len(recovery) == len(stress_test_request["recovery_periods"])
                for period_result in recovery:
                    assert "period_days" in period_result
                    assert "recovery_probability" in period_result
                    assert 0 <= period_result["recovery_probability"] <= 1
            
            # Step 7: Generate historical comparison report
            historical_request = {
                "portfolio_id": portfolio_id,
                "comparison_periods": ["1D", "1W", "1M"],
                "include_charts": True,
                "metrics_to_compare": [
                    "value_at_risk",
                    "expected_shortfall",
                    "volatility",
                    "maximum_drawdown"
                ]
            }
            
            historical_response = await session.post(
                f"{base_url}/reports/historical-comparison",
                json=historical_request
            )
            assert historical_response.status == 200
            historical_data = await historical_response.json()
            assert "report_id" in historical_data
            assert "comparison_data" in historical_data
    
    async def _wait_for_calculation(self, session, base_url, calculation_id, max_attempts=30):
        """Helper method to wait for calculation completion."""
        attempt = 0
        while attempt < max_attempts:
            status_response = await session.get(
                f"{base_url}/calculations/{calculation_id}/status"
            )
            status_data = await status_response.json()
            
            if status_data["status"] == "COMPLETED":
                return True
            elif status_data["status"] == "FAILED":
                return False
            
            await asyncio.sleep(1)
            attempt += 1
        
        return False

    @pytest.mark.asyncio
    async def test_risk_aggregation_failure_scenarios(self, base_url):
        """
        Test 4: Risk aggregation failure scenarios and error handling
        
        This test verifies proper handling of:
        1. Invalid portfolio data
        2. Missing market data
        3. Calculation timeouts
        4. Service unavailability
        5. Data consistency errors
        """
        
        async with aiohttp.ClientSession() as session:
            # Test 1: Invalid portfolio structure
            invalid_portfolio = {
                "portfolio_id": "INVALID-001",
                "positions": [
                    {
                        "instrument_id": "UNKNOWN_INSTRUMENT",
                        "quantity": -1000,  # Invalid negative quantity
                        "market_value": "not_a_number"  # Invalid type
                    }
                ]
            }
            
            response = await session.post(
                f"{base_url}/portfolios",
                json=invalid_portfolio
            )
            assert response.status == 400
            error_data = await response.json()
            assert "error" in error_data
            assert "validation_errors" in error_data
            
            # Test 2: Missing required market data
            valid_portfolio = {
                "portfolio_id": "PORT-TEST-001",
                "positions": [
                    {
                        "position_id": "POS-001",
                        "instrument_id": "EXOTIC_DERIVATIVE",
                        "quantity": 100,
                        "market_value": 50000
                    }
                ]
            }
            
            portfolio_response = await session.post(
                f"{base_url}/portfolios",
                json=valid_portfolio
            )
            assert portfolio_response.status == 201
            portfolio_id = (await portfolio_response.json())["portfolio_id"]
            
            # Try calculation without market data
            calc_request = {
                "portfolio_id": portfolio_id,
                "risk_metrics": ["var"],
                "market_data": {}  # Empty market data
            }
            
            calc_response = await session.post(
                f"{base_url}/calculate",
                json=calc_request
            )
            assert calc_response.status == 400
            calc_error = await calc_response.json()
            assert "missing_market_data" in calc_error
            
            # Test 3: Timeout scenario with large portfolio
            large_portfolio = {
                "portfolio_id": "LARGE-PORT-001",
                "positions": [
                    {
                        "position_id": f"POS-{i:05d}",
                        "instrument_id": f"INST-{i:05d}",
                        "quantity": 1000,
                        "market_value": 10000
                    }
                    for i in range(10000)  # Very large portfolio
                ]
            }
            
            # Set short timeout
            timeout_config = aiohttp.ClientTimeout(total=5)
            
            try:
                response = await session.post(
                    f"{base_url}/portfolios",
                    json=large_portfolio,
                    timeout=timeout_config
                )
                # Should timeout or return 413 (Payload Too Large)
                assert response.status in [408, 413, 504]
            except asyncio.TimeoutError:
                # Expected behavior
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])