import pytest
from fastapi.testclient import TestClient

from app.models.course import Course
from app.models.user import User


def get_token(client: TestClient, email: str, password: str = "EduVerseDemo2026!") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Failed to login {email}: {res.text}"
    return res.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestCourseAnnouncements:
    def test_announcements_creation_and_filtering(self, client: TestClient):
        # Sarah Chen is instructor of Course 1
        sarah_token = get_token(client, "sarah.chen@eduverse.io")
        # Alex Rivera is enrolled student in Course 1
        alex_token = get_token(client, "alex.rivera@eduverse.io")

        # 1. Instructor creates a published announcement
        res_pub = client.post(
            "/api/v1/courses/1/announcements",
            headers=auth_header(sarah_token),
            json={
                "title": "Welcome to Week 1 Live Sessions",
                "content": "Live sessions begin this Wednesday. Check syllabus for details.",
                "is_published": True,
            },
        )
        assert res_pub.status_code == 201
        pub_ann_id = res_pub.json()["id"]

        # 2. Instructor creates a draft announcement
        res_draft = client.post(
            "/api/v1/courses/1/announcements",
            headers=auth_header(sarah_token),
            json={
                "title": "Draft Exam Instructions",
                "content": "Secret draft instructions for the final exam.",
                "is_published": False,
            },
        )
        assert res_draft.status_code == 201
        draft_ann_id = res_draft.json()["id"]

        # 3. Instructor lists announcements: sees both published and draft
        instructor_list = client.get(
            "/api/v1/courses/1/announcements",
            headers=auth_header(sarah_token),
        )
        assert instructor_list.status_code == 200
        inst_ids = [a["id"] for a in instructor_list.json()]
        assert pub_ann_id in inst_ids
        assert draft_ann_id in inst_ids

        # 4. Enrolled student lists announcements: sees ONLY published
        student_list = client.get(
            "/api/v1/courses/1/announcements",
            headers=auth_header(alex_token),
        )
        assert student_list.status_code == 200
        student_ids = [a["id"] for a in student_list.json()]
        assert pub_ann_id in student_ids
        assert draft_ann_id not in student_ids

        # 5. Student cannot access draft directly by ID
        res_draft_detail = client.get(
            f"/api/v1/announcements/{draft_ann_id}",
            headers=auth_header(alex_token),
        )
        assert res_draft_detail.status_code in (404, 403)

    def test_announcement_permissions_and_unauthorized_access(self, client: TestClient):
        # Marcus Vance is instructor of Course 2, NOT Course 1
        marcus_token = get_token(client, "marcus.vance@eduverse.io")
        alex_token = get_token(client, "alex.rivera@eduverse.io")
        admin_token = get_token(client, "admin@eduverse.io")

        # Student cannot create announcement
        res_student_post = client.post(
            "/api/v1/courses/1/announcements",
            headers=auth_header(alex_token),
            json={"title": "Hacked Title", "content": "Student posting.", "is_published": True},
        )
        assert res_student_post.status_code == 403

        # Non-owner instructor cannot create announcement for Course 1
        res_marcus_post = client.post(
            "/api/v1/courses/1/announcements",
            headers=auth_header(marcus_token),
            json={"title": "Unauthorized Announcement", "content": "Marcus posting.", "is_published": True},
        )
        assert res_marcus_post.status_code == 403

        # Admin CAN create announcement for any course
        res_admin_post = client.post(
            "/api/v1/courses/1/announcements",
            headers=auth_header(admin_token),
            json={"title": "Platform Maintenance Notice", "content": "Scheduled server reboot tonight.", "is_published": True},
        )
        assert res_admin_post.status_code == 201

        # Admin can delete announcement
        ann_id = res_admin_post.json()["id"]
        res_del = client.delete(
            f"/api/v1/announcements/{ann_id}",
            headers=auth_header(admin_token),
        )
        assert res_del.status_code == 200


class TestCourseDiscussionsAndReplies:
    def test_discussion_thread_lifecycle(self, client: TestClient):
        alex_token = get_token(client, "alex.rivera@eduverse.io")
        sarah_token = get_token(client, "sarah.chen@eduverse.io")

        # 1. Enrolled student creates a thread
        res_create = client.post(
            "/api/v1/courses/1/discussions",
            headers=auth_header(alex_token),
            json={
                "title": "How to optimize SQLite queries in FastAPI?",
                "content": "Is it recommended to use WAL mode and connection pooling?",
            },
        )
        assert res_create.status_code == 201
        thread = res_create.json()
        thread_id = thread["id"]
        assert thread["title"] == "How to optimize SQLite queries in FastAPI?"
        assert thread["author"]["email"] == "alex.rivera@eduverse.io"

        # 2. Instructor lists discussions and verifies search
        res_list = client.get(
            "/api/v1/courses/1/discussions?search=optimize",
            headers=auth_header(sarah_token),
        )
        assert res_list.status_code == 200
        items = res_list.json()["items"]
        assert any(i["id"] == thread_id for i in items)

        # 3. Instructor pins the thread
        res_pin = client.patch(
            f"/api/v1/discussions/{thread_id}/pin",
            headers=auth_header(sarah_token),
        )
        assert res_pin.status_code == 200
        assert res_pin.json()["is_pinned"] is True

        # 4. Student attempts to pin: 403 Forbidden
        res_pin_fail = client.patch(
            f"/api/v1/discussions/{thread_id}/pin",
            headers=auth_header(alex_token),
        )
        assert res_pin_fail.status_code == 403

        # 5. Instructor replies to the thread
        res_reply = client.post(
            f"/api/v1/discussions/{thread_id}/replies",
            headers=auth_header(sarah_token),
            json={"content": "Yes, PRAGMA journal_mode=WAL significantly boosts read concurrency!"},
        )
        assert res_reply.status_code == 201
        reply_id = res_reply.json()["id"]

        # 6. Student views thread detail with replies
        res_detail = client.get(
            f"/api/v1/discussions/{thread_id}",
            headers=auth_header(alex_token),
        )
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert len(detail["replies"]) >= 1
        assert detail["replies"][-1]["id"] == reply_id

        # 7. Non-author cannot edit instructor's reply
        res_edit_fail = client.put(
            f"/api/v1/replies/{reply_id}",
            headers=auth_header(alex_token),
            json={"content": "Tampered reply content."},
        )
        assert res_edit_fail.status_code == 403

        # 8. Instructor edits their own reply
        res_edit_reply = client.put(
            f"/api/v1/replies/{reply_id}",
            headers=auth_header(sarah_token),
            json={"content": "Updated: WAL mode and proper indexing are both essential."},
        )
        assert res_edit_reply.status_code == 200
        assert "Updated:" in res_edit_reply.json()["content"]

        # 9. Soft-delete reply
        res_del_reply = client.delete(
            f"/api/v1/replies/{reply_id}",
            headers=auth_header(sarah_token),
        )
        assert res_del_reply.status_code == 200

        # Verify reply content is masked
        res_detail_after = client.get(
            f"/api/v1/discussions/{thread_id}",
            headers=auth_header(alex_token),
        )
        deleted_reply = next(r for r in res_detail_after.json()["replies"] if r["id"] == reply_id)
        assert deleted_reply["is_deleted"] is True
        assert "deleted" in deleted_reply["content"].lower()

    def test_discussion_unenrolled_student_blocked(self, client: TestClient):
        # Register a fresh student who is not enrolled in Course 1
        client.cookies.clear()
        reg_res = client.post(
            "/api/v1/auth/register",
            json={"email": "unenrolled.learner@eduverse.io", "password": "EduVerseDemo2026!", "full_name": "Unenrolled Learner"},
        )
        assert reg_res.status_code in (201, 409)
        new_token = get_token(client, "unenrolled.learner@eduverse.io")

        # Attempt to access Course 1 discussions
        res_blocked = client.get(
            "/api/v1/courses/1/discussions",
            headers=auth_header(new_token),
        )
        assert res_blocked.status_code == 403

        res_create_blocked = client.post(
            "/api/v1/courses/1/discussions",
            headers=auth_header(new_token),
            json={"title": "Spam thread", "content": "Should be rejected."},
        )
        assert res_create_blocked.status_code == 403


class TestNotificationsSubsystem:
    def test_notification_flow_and_isolation(self, client: TestClient):
        alex_token = get_token(client, "alex.rivera@eduverse.io")
        sarah_token = get_token(client, "sarah.chen@eduverse.io")

        # 1. Check Alex's unread notifications count
        res_unread = client.get(
            "/api/v1/notifications/unread-count",
            headers=auth_header(alex_token),
        )
        assert res_unread.status_code == 200
        initial_unread = res_unread.json()["unread_count"]

        # 2. Sarah posts an announcement in Course 1 (where Alex is enrolled)
        res_ann = client.post(
            "/api/v1/courses/1/announcements",
            headers=auth_header(sarah_token),
            json={
                "title": "Notification Trigger Test Announcement",
                "content": "Testing automated student notification dispatch.",
                "is_published": True,
            },
        )
        assert res_ann.status_code == 201

        # 3. Alex's unread count should have incremented
        res_unread_after = client.get(
            "/api/v1/notifications/unread-count",
            headers=auth_header(alex_token),
        )
        assert res_unread_after.json()["unread_count"] == initial_unread + 1

        # 4. Alex lists notifications and retrieves the new notification
        res_list = client.get(
            "/api/v1/notifications?limit=10",
            headers=auth_header(alex_token),
        )
        assert res_list.status_code == 200
        notifs = res_list.json()
        assert len(notifs) > 0
        newest_notif = notifs[0]
        assert "Notification Trigger Test Announcement" in newest_notif["title"]
        assert newest_notif["is_read"] is False

        # 5. Sarah cannot mark Alex's notification as read (isolation check)
        res_cross_mark = client.patch(
            f"/api/v1/notifications/{newest_notif['id']}/read",
            headers=auth_header(sarah_token),
        )
        assert res_cross_mark.status_code in (403, 404)

        # 6. Alex marks notification as read
        res_mark = client.patch(
            f"/api/v1/notifications/{newest_notif['id']}/read",
            headers=auth_header(alex_token),
        )
        assert res_mark.status_code == 200
        assert res_mark.json()["is_read"] is True

        # 7. Alex marks all remaining as read
        res_mark_all = client.post(
            "/api/v1/notifications/mark-all-read",
            headers=auth_header(alex_token),
        )
        assert res_mark_all.status_code == 200

        # Unread count should now be 0
        res_zero = client.get(
            "/api/v1/notifications/unread-count",
            headers=auth_header(alex_token),
        )
        assert res_zero.json()["unread_count"] == 0
