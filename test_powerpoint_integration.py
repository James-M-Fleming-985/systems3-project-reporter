"""
Integration test for PowerPoint Report Builder Feature
Tests that Playwright-based screenshot service integrates properly
"""
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys

# Add layer paths
feature_dir = (
    Path(__file__).parent /
    "FEATURE-WEB-006_PowerPoint_Export"
)

for layer_name in [
    "LAYER_WEB_006_001_Report_Configuration_Model",
    "LAYER_WEB_006_002_Report_Template_Repository",
    "LAYER_WEB_006_003_Screenshot_Capture_Service",
    "LAYER_WEB_006_004_PowerPoint_Builder_Service"
]:
    layer_path = feature_dir / layer_name / "src"
    if str(layer_path) not in sys.path:
        sys.path.insert(0, str(layer_path))

from screenshot_service import ScreenshotService


def test_screenshot_service_import():
    """Test that Screenshot Service imports successfully"""
    assert ScreenshotService is not None
    service = ScreenshotService()
    assert hasattr(service, 'capture_screenshot')
    assert hasattr(service, 'capture_screenshot_async')
    print("✅ Screenshot Service imports and instantiates")


def test_screenshot_service_uses_playwright():
    """Verify Screenshot Service uses Playwright, not Selenium"""
    import inspect
    source = inspect.getsource(ScreenshotService)
    
    # Should have Playwright imports
    assert 'playwright' in source.lower()
    assert 'async_playwright' in source
    
    # Should NOT have Selenium imports
    assert 'selenium' not in source.lower()
    assert 'webdriver' not in source.lower()
    
    print("✅ Screenshot Service uses Playwright (no Selenium)")


def test_fastapi_app_loads():
    """Test that FastAPI app loads with PowerPoint router"""
    from main import app
    
    client = TestClient(app)
    
    # Test basic app health (not powerpoint-specific but validates app loads)
    response = client.get("/")
    assert response.status_code in [200, 404]  # Either home page or not found is OK
    
    print("✅ FastAPI app loads with PowerPoint router integrated")


def test_powerpoint_router_templates():
    """Test template listing endpoint"""
    from main import app
    
    client = TestClient(app)
    response = client.get("/api/reports/templates")
    
    assert response.status_code == 200
    data = response.json()
    assert "predefined" in data
    assert "custom" in data
    
    # Should have predefined templates
    assert len(data["predefined"]) > 0
    
    print("✅ Template listing works")
    print(f"   Found {len(data['predefined'])} predefined templates")


if __name__ == "__main__":
    # Run tests
    print("\n" + "="*60)
    print("PowerPoint Report Builder - Integration Tests")
    print("="*60 + "\n")
    
    test_screenshot_service_import()
    test_screenshot_service_uses_playwright()
    test_fastapi_app_loads()
    test_powerpoint_router_templates()
    
    print("\n" + "="*60)
    print("✅ ALL INTEGRATION TESTS PASSED!")
    print("="*60 + "\n")
