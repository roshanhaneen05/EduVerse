import io
from pathlib import Path
import pytest
from app.config import get_settings
from app.services.storage import get_storage_provider

settings = get_settings()


def get_token(client, email: str, password: str = "EduVerseDemo2026!") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def test_material_upload_success(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}

    # 1. Upload valid PDF
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n"
        b"0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000102 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n185\n%%EOF\n"
    )
    files = {"file": ("Chapter1_Architecture.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "title": "Architecture Blueprint Reference",
        "description": "Essential architecture diagrams and specifications.",
    }

    resp = client.post(
        "/api/v1/instructor/courses/1/materials",
        data=data,
        files=files,
        headers=sarah_headers,
    )
    assert resp.status_code == 201, resp.text
    mat = resp.json()
    assert mat["title"] == "Architecture Blueprint Reference"
    assert mat["original_filename"] == "Chapter1_Architecture.pdf"
    assert mat["mime_type"] == "application/pdf"
    assert mat["file_size"] == len(pdf_bytes)
    assert "storage_key" not in mat  # Never expose internal storage keys in public schemas!

    # 2. Upload valid PNG
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    files_png = {"file": ("system_diagram.png", io.BytesIO(png_bytes), "image/png")}
    resp_png = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "High-Level System Diagram"},
        files=files_png,
        headers=sarah_headers,
    )
    assert resp_png.status_code == 201
    assert resp_png.json()["mime_type"] == "image/png"

    # 3. Upload valid TXT
    txt_bytes = b"Course Prerequisites:\n- Basic Python knowledge\n- Familiarity with HTTP methods"
    files_txt = {"file": ("prerequisites.txt", io.BytesIO(txt_bytes), "text/plain")}
    resp_txt = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Course Prerequisites Document"},
        files=files_txt,
        headers=sarah_headers,
    )
    assert resp_txt.status_code == 201
    assert resp_txt.json()["mime_type"] == "text/plain"


def test_material_upload_security_validations(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}

    # 1. Reject empty file
    files_empty = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
    resp_empty = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Empty File"},
        files=files_empty,
        headers=sarah_headers,
    )
    assert resp_empty.status_code == 400
    assert "empty" in resp_empty.json()["detail"].lower()

    # 2. Reject forbidden executable extension (.exe)
    files_exe = {"file": ("installer.exe", io.BytesIO(b"MZfakebinarycontent"), "application/octet-stream")}
    resp_exe = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Malicious Executable"},
        files=files_exe,
        headers=sarah_headers,
    )
    assert resp_exe.status_code == 400
    assert "forbidden" in resp_exe.json()["detail"].lower()

    # 3. Reject forbidden web script extension (.html / .js)
    files_html = {"file": ("xss_payload.html", io.BytesIO(b"<html><script>alert(1)</script></html>"), "text/html")}
    resp_html = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "HTML Payload"},
        files=files_html,
        headers=sarah_headers,
    )
    assert resp_html.status_code == 400
    assert "forbidden" in resp_html.json()["detail"].lower()

    # 4. Reject spoofed MIME: file named .pdf containing DOS executable magic (MZ)
    files_spoofed = {"file": ("fake_document.pdf", io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"), "application/pdf")}
    resp_spoofed = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Spoofed Executable"},
        files=files_spoofed,
        headers=sarah_headers,
    )
    assert resp_spoofed.status_code == 400

    # 5. Reject malformed PDF (does not start with %PDF-)
    files_bad_pdf = {"file": ("corrupt.pdf", io.BytesIO(b"Random corrupt plain text header"), "application/pdf")}
    resp_bad_pdf = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Corrupt PDF"},
        files=files_bad_pdf,
        headers=sarah_headers,
    )
    assert resp_bad_pdf.status_code == 400
    assert "header" in resp_bad_pdf.json()["detail"].lower() or "malformed" in resp_bad_pdf.json()["detail"].lower()

    # 6. Reject text file containing embedded HTML/script tags
    files_bad_txt = {"file": ("notes.txt", io.BytesIO(b"<!DOCTYPE html><html><body>Dangerous</body></html>"), "text/plain")}
    resp_bad_txt = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "HTML in TXT"},
        files=files_bad_txt,
        headers=sarah_headers,
    )
    assert resp_bad_txt.status_code == 400


def test_instructor_course_ownership_enforcement(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    marcus_token = get_token(client, "marcus.vance@eduverse.io")
    alex_token = get_token(client, "alex.rivera@eduverse.io")

    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}
    marcus_headers = {"Authorization": f"Bearer {marcus_token}"}
    alex_headers = {"Authorization": f"Bearer {alex_token}"}

    pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\ntrailer<</Root 1 0 R>>\n%%EOF\n"
    files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    # 1. Student cannot upload material -> 403 Forbidden
    student_upload = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Student Upload Attempt"},
        files=files,
        headers=alex_headers,
    )
    assert student_upload.status_code == 403

    # 2. Marcus (teaches Course 2) cannot upload to Course 1 (Sarah's course) -> 403 Forbidden
    marcus_upload = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Marcus Hijack Course 1"},
        files=files,
        headers=marcus_headers,
    )
    assert marcus_upload.status_code == 403

    # 3. Sarah uploads to Course 1
    sarah_upload = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Sarah Exclusive Guide"},
        files={"file": ("sarah_guide.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=sarah_headers,
    )
    assert sarah_upload.status_code == 201
    mat_id = sarah_upload.json()["id"]

    # 4. Marcus cannot update Sarah's material -> 403 Forbidden
    marcus_update = client.put(
        f"/api/v1/instructor/materials/{mat_id}",
        json={"title": "Marcus Unauthorized Edit"},
        headers=marcus_headers,
    )
    assert marcus_update.status_code == 403

    # 5. Marcus cannot delete Sarah's material -> 403 Forbidden
    marcus_delete = client.delete(
        f"/api/v1/instructor/materials/{mat_id}",
        headers=marcus_headers,
    )
    assert marcus_delete.status_code == 403


def test_student_enrollment_access_and_downloads(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    alex_token = get_token(client, "alex.rivera@eduverse.io")  # Enrolled in Course 1
    priya_token = get_token(client, "priya.patel@eduverse.io")  # NOT enrolled in Course 1

    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}
    alex_headers = {"Authorization": f"Bearer {alex_token}"}
    priya_headers = {"Authorization": f"Bearer {priya_token}"}

    pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\ntrailer<</Root 1 0 R>>\n%%EOF\n"
    create_resp = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Course 1 Enrolled Study Pack"},
        files={"file": ("study_pack.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=sarah_headers,
    )
    assert create_resp.status_code == 201
    mat_id = create_resp.json()["id"]

    # 1. Enrolled student Alex can list materials -> 200 OK
    alex_list = client.get("/api/v1/materials/course/1", headers=alex_headers)
    assert alex_list.status_code == 200
    assert any(m["id"] == mat_id for m in alex_list.json())

    # 2. Unenrolled student Priya cannot list materials -> 403 Forbidden
    priya_list = client.get("/api/v1/materials/course/1", headers=priya_headers)
    assert priya_list.status_code == 403
    assert "enrolled" in priya_list.json()["detail"].lower()

    # 3. Unenrolled student Priya cannot access metadata -> 403 Forbidden
    priya_detail = client.get(f"/api/v1/materials/{mat_id}", headers=priya_headers)
    assert priya_detail.status_code == 403

    # 4. Enrolled student Alex can download file -> 200 OK
    alex_download = client.get(f"/api/v1/materials/{mat_id}/download", headers=alex_headers)
    assert alex_download.status_code == 200
    assert alex_download.content == pdf_bytes
    assert 'attachment; filename="study_pack.pdf"' in alex_download.headers.get("content-disposition", "")

    # 5. Unenrolled student Priya cannot download file -> 403 Forbidden
    priya_download = client.get(f"/api/v1/materials/{mat_id}/download", headers=priya_headers)
    assert priya_download.status_code == 403


def test_material_update_and_safe_deletion(client):
    sarah_token = get_token(client, "sarah.chen@eduverse.io")
    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}

    txt_content = b"Sample ephemeral material content for lifecycle testing."
    upload_resp = client.post(
        "/api/v1/instructor/courses/1/materials",
        data={"title": "Initial Draft Material", "description": "Draft description"},
        files={"file": ("ephemeral_note.txt", io.BytesIO(txt_content), "text/plain")},
        headers=sarah_headers,
    )
    assert upload_resp.status_code == 201
    mat_id = upload_resp.json()["id"]

    # 1. Update metadata
    update_resp = client.put(
        f"/api/v1/instructor/materials/{mat_id}",
        json={"title": "Updated Official Guide", "description": "Revised production description"},
        headers=sarah_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Official Guide"
    assert update_resp.json()["description"] == "Revised production description"

    # 2. Delete material
    del_resp = client.delete(f"/api/v1/instructor/materials/{mat_id}", headers=sarah_headers)
    assert del_resp.status_code == 200
    assert "deleted" in del_resp.json()["message"].lower()

    # 3. Confirm material record no longer exists in DB
    get_deleted = client.get(f"/api/v1/materials/{mat_id}", headers=sarah_headers)
    assert get_deleted.status_code == 404

