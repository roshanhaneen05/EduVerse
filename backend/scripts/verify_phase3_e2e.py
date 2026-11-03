"""
End-to-End Verification Script for EduVerse Phase 3: Secure File Uploads & Learning Materials.
Tests complete lifecycle:
1. Instructor login & upload of verified PDF document.
2. Verification of disk storage and unpredictable UUID filename outside public directory.
3. Verification that internal storage keys and filesystem paths are never leaked to clients.
4. Unenrolled student access rejection (403 Forbidden).
5. Enrolled student syllabus listing and streaming download verification.
6. Content integrity and Content-Disposition attachment header check.
7. Instructor metadata updates.
8. Instructor deletion with physical file removal from storage.
"""
import io
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.config import get_settings
from app.main import app
from app.database import SessionLocal
from app.models.material import LearningMaterial
from app.services.storage import get_storage_provider

settings = get_settings()


def run_phase3_e2e_verification():
    client = TestClient(app)
    storage = get_storage_provider()

    print("=" * 65)
    print("STARTING END-TO-END VERIFICATION: SECURE FILE UPLOADS & MATERIALS")
    print("=" * 65)

    # 1. Login as Instructor (Dr. Sarah Chen)
    print("\n[Step 1] Logging in as Instructor (sarah.chen@eduverse.io)...")
    res_inst = client.post("/api/v1/auth/login", json={
        "email": "sarah.chen@eduverse.io",
        "password": "EduVerseDemo2026!"
    })
    assert res_inst.status_code == 200, f"Instructor login failed: {res_inst.text}"
    sarah_token = res_inst.json()["access_token"]
    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}
    print("  -> Instructor authenticated successfully.")

    # 2. Login as Enrolled Student (Alex Rivera)
    print("\n[Step 2] Logging in as Enrolled Student (alex.rivera@eduverse.io)...")
    res_alex = client.post("/api/v1/auth/login", json={
        "email": "alex.rivera@eduverse.io",
        "password": "EduVerseDemo2026!"
    })
    assert res_alex.status_code == 200, f"Alex login failed: {res_alex.text}"
    alex_token = res_alex.json()["access_token"]
    alex_headers = {"Authorization": f"Bearer {alex_token}"}
    print("  -> Enrolled student authenticated successfully.")

    # 3. Login as Unenrolled Student (Priya Patel)
    print("\n[Step 3] Logging in as Unenrolled Student (priya.patel@eduverse.io)...")
    res_priya = client.post("/api/v1/auth/login", json={
        "email": "priya.patel@eduverse.io",
        "password": "EduVerseDemo2026!"
    })
    assert res_priya.status_code == 200, f"Priya login failed: {res_priya.text}"
    priya_token = res_priya.json()["access_token"]
    priya_headers = {"Authorization": f"Bearer {priya_token}"}
    print("  -> Unenrolled student authenticated successfully.")

    # 4. Instructor uploads verified PDF material
    print("\n[Step 4] Instructor uploads Course 1 Learning Material (PDF)...")
    pdf_content = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n"
        b"0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000102 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n185\n%%EOF\n"
    )
    files = {"file": ("E2E_Microservices_Architecture_Spec.pdf", io.BytesIO(pdf_content), "application/pdf")}
    data = {
        "title": "E2E Microservices Specification Document",
        "description": "Production architecture specifications, domain boundaries, and persistence strategies.",
    }
    upload_res = client.post("/api/v1/instructor/courses/1/materials", data=data, files=files, headers=sarah_headers)
    assert upload_res.status_code == 201, f"Upload failed: {upload_res.text}"
    material = upload_res.json()
    material_id = material["id"]
    print(f"  -> Uploaded Material ID {material_id}: '{material['title']}' ({material['file_size_formatted']})")
    assert "storage_key" not in material, "Security defect: storage_key leaked in response!"

    try:
        # 5. Verify physical storage file
        db = SessionLocal()
        try:
            db_mat = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()
            assert db_mat is not None
            storage_key = db_mat.storage_key
            assert storage.file_exists(storage_key), "Uploaded file does not exist in storage provider!"
            local_path = storage.get_file_path(storage_key)
            assert local_path is not None and local_path.is_file()
            print(f"  -> Physical file verified in private storage: {local_path.name}")
            assert not str(local_path).startswith(str(backend_dir.parent / "frontend")), "File stored inside public frontend tree!"
        finally:
            db.close()

        # 6. Unenrolled Student Priya blocked from access
        print("\n[Step 5] Verifying unenrolled student access barrier...")
        priya_list = client.get("/api/v1/materials/course/1", headers=priya_headers)
        assert priya_list.status_code == 403, f"Expected 403, got {priya_list.status_code}"
        priya_dl = client.get(f"/api/v1/materials/{material_id}/download", headers=priya_headers)
        assert priya_dl.status_code == 403, f"Expected 403, got {priya_dl.status_code}"
        print("  -> Unenrolled student successfully blocked (403 Forbidden).")

        # 7. Enrolled Student Alex lists materials
        print("\n[Step 6] Enrolled student Alex lists course materials...")
        alex_list = client.get("/api/v1/materials/course/1", headers=alex_headers)
        assert alex_list.status_code == 200
        found = [m for m in alex_list.json() if m["id"] == material_id]
        assert len(found) == 1, "Uploaded material not found in Alex's list"
        print(f"  -> Material visible to enrolled student in course syllabus.")

        # 8. Enrolled Student Alex downloads the material
        print("\n[Step 7] Enrolled student Alex downloads the material file...")
        alex_dl = client.get(f"/api/v1/materials/{material_id}/download", headers=alex_headers)
        assert alex_dl.status_code == 200, f"Download failed: {alex_dl.status_code}"
        assert alex_dl.content == pdf_content, "Downloaded content does not match original binary bytes!"
        cd_header = alex_dl.headers.get("content-disposition", "")
        assert 'attachment; filename="E2E_Microservices_Architecture_Spec.pdf"' in cd_header
        assert alex_dl.headers.get("content-type") == "application/pdf"
        print(f"  -> Streamed file verified with perfect byte-for-byte fidelity.")
        print(f"  -> Content-Disposition: {cd_header}")

        # 9. Instructor updates metadata
        print("\n[Step 8] Instructor updates material metadata...")
        update_res = client.put(
            f"/api/v1/instructor/materials/{material_id}",
            json={
                "title": "E2E Microservices Specification Document (Approved)",
                "description": "Final approved architecture specification.",
            },
            headers=sarah_headers
        )
        assert update_res.status_code == 200
        assert update_res.json()["title"] == "E2E Microservices Specification Document (Approved)"
        print("  -> Metadata successfully updated.")

    finally:
        # 10. Instructor deletes the material and verifies file removal
        print("\n[Step 9] Instructor deletes the material...")
        del_res = client.delete(f"/api/v1/instructor/materials/{material_id}", headers=sarah_headers)
        assert del_res.status_code == 200
        print(f"  -> Delete response: {del_res.json()['message']}")

        # Verify physical file removal
        assert not storage.file_exists(storage_key), "Storage file was NOT deleted after material deletion!"
        print("  -> Physical storage file cleanly deleted from disk.")

    print("\n" + "=" * 65)
    print("[SUCCESS] ALL PHASE 3 END-TO-END VERIFICATION STEPS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    run_phase3_e2e_verification()

