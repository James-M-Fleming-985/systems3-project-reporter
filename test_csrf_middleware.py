"""
Test CSRF Middleware Fix for File Uploads
Tests that the CSRF middleware checks the header FIRST before consuming the request body
"""
import pytest
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from middleware.security_middleware import CSRFMiddleware, generate_csrf_token
import io


# Create a test app
app = FastAPI()
app.add_middleware(CSRFMiddleware)


@app.post("/test/upload")
def upload_endpoint(file: UploadFile = File(...)):
    """Test file upload endpoint"""
    content = file.file.read()
    return JSONResponse(
        status_code=200,
        content={
            "filename": file.filename,
            "size": len(content),
            "content": content.decode("utf-8") if content else ""
        }
    )


@app.post("/test/form")
def form_endpoint():
    """Test traditional form submission - this will be tested by client"""
    # This endpoint just needs to exist for testing
    return JSONResponse(
        status_code=200,
        content={"received": "ok"}
    )


@app.get("/test/token")
def get_token(request: Request):
    """Get a CSRF token for testing"""
    return JSONResponse(
        status_code=200,
        content={"csrf_token": request.state.csrf_token}
    )


def test_file_upload_with_header_csrf():
    """Test that file uploads work when CSRF token is in header"""
    client = TestClient(app)
    
    # Get a valid CSRF token
    response = client.get("/test/token")
    assert response.status_code == 200
    csrf_token = response.json()["csrf_token"]
    
    # Create a test file
    test_content = "This is a test file content"
    file_data = io.BytesIO(test_content.encode("utf-8"))
    
    # Upload file with CSRF token in header
    response = client.post(
        "/test/upload",
        files={"file": ("test.txt", file_data, "text/plain")},
        headers={"x-csrf-token": csrf_token}
    )
    
    # Should succeed
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["size"] == len(test_content)
    assert data["content"] == test_content


def test_file_upload_without_csrf_fails():
    """Test that file uploads fail without CSRF token"""
    client = TestClient(app)
    
    # Create a test file
    test_content = "This is a test file content"
    file_data = io.BytesIO(test_content.encode("utf-8"))
    
    # Upload file without CSRF token
    response = client.post(
        "/test/upload",
        files={"file": ("test.txt", file_data, "text/plain")}
    )
    
    # Should fail with 403
    assert response.status_code == 403
    assert "CSRF token missing" in response.json()["detail"]


def test_traditional_form_with_token_in_body():
    """Test that traditional form submissions still work with token in body"""
    client = TestClient(app)
    
    # Get a valid CSRF token
    response = client.get("/test/token")
    assert response.status_code == 200
    csrf_token = response.json()["csrf_token"]
    
    # Submit form with CSRF token in body
    response = client.post(
        "/test/form",
        data={
            "csrf_token": csrf_token,
            "field1": "value1",
            "field2": "value2"
        }
    )
    
    # Should succeed
    assert response.status_code == 200
    data = response.json()
    assert "received" in data


def test_traditional_form_without_csrf_fails():
    """Test that traditional form submissions fail without CSRF token"""
    client = TestClient(app)
    
    # Submit form without CSRF token
    response = client.post(
        "/test/form",
        data={
            "field1": "value1",
            "field2": "value2"
        }
    )
    
    # Should fail with 403
    assert response.status_code == 403
    assert "CSRF token missing" in response.json()["detail"]


def test_get_requests_dont_need_csrf():
    """Test that GET requests don't require CSRF tokens"""
    client = TestClient(app)
    
    # GET request should work without CSRF token
    response = client.get("/test/token")
    assert response.status_code == 200


def test_header_takes_precedence_over_form():
    """Test that header is checked before form body"""
    client = TestClient(app)
    
    # Get a valid CSRF token
    response = client.get("/test/token")
    assert response.status_code == 200
    csrf_token = response.json()["csrf_token"]
    
    # Create a test file
    test_content = "Test file for precedence check"
    file_data = io.BytesIO(test_content.encode("utf-8"))
    
    # Upload file with CSRF token in BOTH header and form
    # The header should be used, preventing body consumption
    response = client.post(
        "/test/upload",
        files={
            "file": ("test.txt", file_data, "text/plain"),
        },
        headers={"x-csrf-token": csrf_token},
        data={"csrf_token": "wrong_token_in_body"}
    )
    
    # Should succeed because header token is valid
    # If form was read first, the file would be consumed and this would fail
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["size"] == len(test_content)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
