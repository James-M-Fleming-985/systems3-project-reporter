"""
Test CSRF Middleware Path Fixes
Tests for the remaining issues from PR #10:
1. CSRF middleware path matching for schedule import endpoint
2. DELETE requests without content-type should fail gracefully
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from middleware.security_middleware import CSRFMiddleware, generate_csrf_token
import io


# Create a test app
app = FastAPI()
app.add_middleware(CSRFMiddleware)


@app.post("/dashboard/api/schedule/{project_name}/import")
def schedule_import_endpoint(project_name: str):
    """Test schedule import endpoint with proper dashboard prefix"""
    return JSONResponse(
        status_code=200,
        content={"message": f"Schedule imported for {project_name}"}
    )


@app.delete("/dashboard/api/schedule/{project_name}/tables/{table_id}/rows/{row_id}")
def delete_row_endpoint(project_name: str, table_id: str, row_id: str):
    """Test DELETE endpoint for schedule rows"""
    return JSONResponse(
        status_code=200,
        content={"message": f"Row {row_id} deleted from table {table_id}"}
    )


@app.get("/test/token")
def get_token(request: Request):
    """Get a CSRF token for testing"""
    return JSONResponse(
        status_code=200,
        content={"csrf_token": request.state.csrf_token}
    )


def test_schedule_import_with_dashboard_prefix():
    """
    Test that schedule import endpoint works with /dashboard prefix
    Bug 1: Path should be /dashboard/api/schedule/{project}/import
    The middleware should now use "in" check instead of startswith
    """
    client = TestClient(app)
    
    # Create a test file for import
    test_content = "test,schedule,data"
    file_data = io.BytesIO(test_content.encode("utf-8"))
    
    # Import schedule with file upload (should be exempt from CSRF)
    response = client.post(
        "/dashboard/api/schedule/test-project/import",
        files={"file": ("schedule.csv", file_data, "text/csv")}
    )
    
    # Should succeed without CSRF token because it's file upload on import endpoint
    assert response.status_code == 200
    data = response.json()
    assert "imported" in data["message"].lower()


def test_delete_row_with_csrf_header():
    """
    Test that DELETE request works with CSRF header
    Bug 2: DELETE requests need x-csrf-token header
    """
    client = TestClient(app)
    
    # Get a valid CSRF token
    response = client.get("/test/token")
    assert response.status_code == 200
    csrf_token = response.json()["csrf_token"]
    
    # DELETE row with CSRF token in header
    response = client.delete(
        "/dashboard/api/schedule/test-project/tables/table1/rows/row1",
        headers={"x-csrf-token": csrf_token}
    )
    
    # Should succeed
    assert response.status_code == 200
    data = response.json()
    assert "deleted" in data["message"].lower()


def test_delete_row_without_csrf_fails_gracefully():
    """
    Test that DELETE request without CSRF header fails gracefully
    Bug 3: Bodiless DELETE should fail with clear error, not form-reading error
    """
    client = TestClient(app)
    
    # DELETE row without CSRF token
    response = client.delete(
        "/dashboard/api/schedule/test-project/tables/table1/rows/row1"
    )
    
    # Should fail with 403 and clear message about needing header
    assert response.status_code == 403
    detail = response.json()["detail"]
    # Should mention either "header" or "body" in the error message
    assert "header" in detail.lower() or "body" in detail.lower()


def test_json_content_type_still_exempt():
    """
    Ensure JSON requests are still exempt from CSRF
    This should not be affected by our changes
    """
    client = TestClient(app)
    
    # POST with JSON content-type should still be exempt
    response = client.post(
        "/dashboard/api/schedule/test-project/import",
        json={"test": "data"},
        headers={"content-type": "application/json"}
    )
    
    # Should succeed even without CSRF token (auth middleware would handle it)
    # We're just testing that CSRF middleware passes it through
    assert response.status_code in [200, 422]  # 422 if endpoint doesn't accept JSON


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
