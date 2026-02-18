"""
Test for Bug 1: CSRF middleware should handle empty x-csrf-token header correctly
Tests that DELETE requests with an empty x-csrf-token header get "CSRF validation failed"
instead of "CSRF token required in header for requests without body"
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from middleware.security_middleware import CSRFMiddleware


# Create a test app
app = FastAPI()
app.add_middleware(CSRFMiddleware)


@app.delete("/test/delete")
def delete_endpoint():
    """Test DELETE endpoint"""
    return JSONResponse(
        status_code=200,
        content={"status": "deleted"}
    )


@app.get("/test/token")
def get_token(request: Request):
    """Get a CSRF token for testing"""
    return JSONResponse(
        status_code=200,
        content={"csrf_token": request.state.csrf_token}
    )


def test_delete_with_valid_csrf_header():
    """Test that DELETE with valid x-csrf-token header succeeds"""
    client = TestClient(app)
    
    # Get a valid CSRF token
    response = client.get("/test/token")
    assert response.status_code == 200
    csrf_token = response.json()["csrf_token"]
    
    # DELETE with valid CSRF token in header
    response = client.delete(
        "/test/delete",
        headers={"x-csrf-token": csrf_token}
    )
    
    # Should succeed
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"


def test_delete_with_empty_csrf_header():
    """Test that DELETE with empty x-csrf-token header gets 'CSRF validation failed' error"""
    client = TestClient(app)
    
    # DELETE with empty CSRF token in header
    response = client.delete(
        "/test/delete",
        headers={"x-csrf-token": ""}
    )
    
    # Should fail with 403 and "CSRF validation failed" message (not "token required" message)
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_delete_without_csrf_header():
    """Test that DELETE without x-csrf-token header gets 'token required' error"""
    client = TestClient(app)
    
    # DELETE without CSRF token header at all
    response = client.delete("/test/delete")
    
    # Should fail with 403 and "token required" message
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token required in header for requests without body"


def test_delete_with_invalid_csrf_header():
    """Test that DELETE with invalid x-csrf-token header gets 'CSRF validation failed' error"""
    client = TestClient(app)
    
    # DELETE with invalid CSRF token in header
    response = client.delete(
        "/test/delete",
        headers={"x-csrf-token": "invalid_token_12345"}
    )
    
    # Should fail with 403 and "CSRF validation failed" message
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
