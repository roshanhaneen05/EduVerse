import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson, LessonProgress
from app.models.material import LearningMaterial
from app.models.announcement import CourseAnnouncement
from app.models.discussion import CourseDiscussion, DiscussionReply
from app.models.notification import Notification
from app.models.quiz import (
    AnswerOption,
    Question,
    Quiz,
)
from app.models.user import User, UserRole
from app.security.password import hash_password
from app.services.storage import get_storage_provider


def seed_database():
    """Idempotent seed script to populate realistic demonstration data."""
    db: Session = SessionLocal()
    try:
        admin_email = os.getenv("ADMIN_EMAIL", "admin@eduverse.io")
        demo_password = os.getenv("DEMO_PASSWORD", "EduVerseDemo2026!")
        hashed_demo_pw = hash_password(demo_password)

        # 1. Users
        users_data = [
            {
                "email": admin_email,
                "full_name": "EduVerse Administrator",
                "role": UserRole.ADMIN.value,
            },
            {
                "email": "sarah.chen@eduverse.io",
                "full_name": "Dr. Sarah Chen",
                "role": UserRole.INSTRUCTOR.value,
            },
            {
                "email": "marcus.vance@eduverse.io",
                "full_name": "Marcus Vance",
                "role": UserRole.INSTRUCTOR.value,
            },
            {
                "email": "alex.rivera@eduverse.io",
                "full_name": "Alex Rivera",
                "role": UserRole.STUDENT.value,
            },
            {
                "email": "priya.patel@eduverse.io",
                "full_name": "Priya Patel",
                "role": UserRole.STUDENT.value,
            },
            {
                "email": "jordan.taylor@eduverse.io",
                "full_name": "Jordan Taylor",
                "role": UserRole.STUDENT.value,
            },
        ]

        created_users = {}
        for u in users_data:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if not existing:
                user = User(
                    email=u["email"],
                    full_name=u["full_name"],
                    password_hash=hashed_demo_pw,
                    role=u["role"],
                    is_active=True,
                )
                db.add(user)
                db.flush()
                created_users[u["email"]] = user
            else:
                created_users[u["email"]] = existing

        sarah = created_users["sarah.chen@eduverse.io"]
        marcus = created_users["marcus.vance@eduverse.io"]
        alex = created_users["alex.rivera@eduverse.io"]

        # 2. Courses
        courses_data = [
            {
                "title": "Modern Full-Stack Development with FastAPI & Angular",
                "category": "Web Development",
                "difficulty": "Intermediate",
                "description": (
                    "This comprehensive course covers full-stack web engineering from first principles. "
                    "You will master modular backend design with FastAPI and Pydantic v2, database abstraction with SQLAlchemy ORM, "
                    "Alembic schema migrations, Argon2 password security, JWT authorization, and modern Angular architecture with standalone components."
                ),
                "is_published": True,
                "instructor_id": sarah.id,
                "lessons": [
                    {
                        "title": "1. Architecture Fundamentals: Modular Monolith vs Microservices",
                        "order_index": 1,
                        "content": (
                            "### Architecture Fundamentals\n\n"
                            "A modular monolith organizes code into independent functional domain modules within a single codebase, "
                            "providing the operational simplicity of a monolith without sacrificing architectural boundaries.\n\n"
                            "#### Key Principles:\n"
                            "- Separation of Concerns\n"
                            "- Contract-First APIs with Pydantic\n"
                            "- Single Responsibility in Services"
                        ),
                    },
                    {
                        "title": "2. RESTful API Design with FastAPI and Pydantic v2",
                        "order_index": 2,
                        "content": (
                            "### RESTful API Design\n\n"
                            "FastAPI leverages Python type hints for runtime validation, serialization, and OpenAPI documentation."
                        ),
                    },
                    {
                        "title": "3. Standalone Angular Components & Reactive State",
                        "order_index": 3,
                        "content": (
                            "### Modern Angular Architecture\n\n"
                            "Angular standalone components eliminate NgModule ceremony and optimize bundle tree-shaking."
                        ),
                    },
                    {
                        "title": "4. Secure Authentication with Argon2 and JWT",
                        "order_index": 4,
                        "content": (
                            "### Authentication and Password Security\n\n"
                            "Never store passwords in plaintext. Argon2id provides memory-hard protection against ASIC/GPU attacks."
                        ),
                    },
                ],
                "quiz": {
                    "title": "Full-Stack Development Mastery Assessment",
                    "description": "Assess your understanding of FastAPI architecture, Angular components, and secure authentication.",
                    "passing_score": 75,
                    "questions": [
                        {
                            "question_text": "Which password hashing algorithm won the Password Hashing Competition and provides memory-hard protection?",
                            "order_index": 1,
                            "points": 25,
                            "options": [
                                {"option_text": "MD5 with Salt", "is_correct": False, "order_index": 1},
                                {"option_text": "SHA-256", "is_correct": False, "order_index": 2},
                                {"option_text": "Argon2id", "is_correct": True, "order_index": 3},
                                {"option_text": "Base64 Encoding", "is_correct": False, "order_index": 4},
                            ],
                        },
                        {
                            "question_text": "What is the primary benefit of standalone components in modern Angular?",
                            "order_index": 2,
                            "points": 25,
                            "options": [
                                {"option_text": "They replace TypeScript with pure JavaScript", "is_correct": False, "order_index": 1},
                                {"option_text": "They eliminate the need for NgModules and improve tree-shaking", "is_correct": True, "order_index": 2},
                                {"option_text": "They prevent the browser from executing CSS", "is_correct": False, "order_index": 3},
                                {"option_text": "They convert Angular into React", "is_correct": False, "order_index": 4},
                            ],
                        },
                        {
                            "question_text": "Where should scoring and evaluation of quiz answers occur in a secure architecture?",
                            "order_index": 3,
                            "points": 25,
                            "options": [
                                {"option_text": "Exclusively in the client-side JavaScript", "is_correct": False, "order_index": 1},
                                {"option_text": "Stored inside localStorage", "is_correct": False, "order_index": 2},
                                {"option_text": "Strictly on the backend server against persistent database answer keys", "is_correct": True, "order_index": 3},
                                {"option_text": "In a public CDN endpoint", "is_correct": False, "order_index": 4},
                            ],
                        },
                        {
                            "question_text": "What does Pydantic v2 provide when integrated with FastAPI?",
                            "order_index": 4,
                            "points": 25,
                            "options": [
                                {"option_text": "A SQL database engine", "is_correct": False, "order_index": 1},
                                {"option_text": "Type validation, serialization, and JSON schema generation", "is_correct": True, "order_index": 2},
                                {"option_text": "A CSS preprocessor", "is_correct": False, "order_index": 3},
                                {"option_text": "A replacement for Docker containers", "is_correct": False, "order_index": 4},
                            ],
                        },
                    ],
                },
            },
            {
                "title": "Cloud Computing & DevSecOps Essentials",
                "category": "Cloud & DevOps",
                "difficulty": "Beginner",
                "description": (
                    "Understand how modern applications are safely developed, tested, and deployed to cloud platforms. "
                    "Learn about continuous delivery pipelines, container best practices, and automated security scanning."
                ),
                "is_published": True,
                "instructor_id": sarah.id,
                "lessons": [
                    {
                        "title": "1. Introduction to Cloud Architecture and Infrastructure as Code",
                        "order_index": 1,
                        "content": "Cloud platforms provide scalable compute and managed databases.",
                    },
                    {
                        "title": "2. Continuous Integration & Automated Testing Pipelines",
                        "order_index": 2,
                        "content": "Automated pipelines run unit tests, security scans, and validation on every commit.",
                    },
                ],
                "quiz": {
                    "title": "Cloud & DevSecOps Fundamentals Quiz",
                    "description": "Test your knowledge on CI/CD pipelines and cloud security.",
                    "passing_score": 65,
                    "questions": [
                        {
                            "question_text": "What is the primary objective of DevSecOps compared to traditional DevOps?",
                            "order_index": 1,
                            "points": 50,
                            "options": [
                                {"option_text": "Disabling automated tests to speed up deployment", "is_correct": False, "order_index": 1},
                                {"option_text": "Embedding automated security validation throughout the development lifecycle", "is_correct": True, "order_index": 2},
                            ],
                        },
                        {
                            "question_text": "Why should sensitive credentials never be committed to Git source control?",
                            "order_index": 2,
                            "points": 50,
                            "options": [
                                {"option_text": "They become permanently visible in commit history and invite unauthorized access", "is_correct": True, "order_index": 1},
                                {"option_text": "Passwords cause Git merge conflicts", "is_correct": False, "order_index": 2},
                            ],
                        },
                    ],
                },
            },
            {
                "title": "Applied Python for Modern Data Engineering",
                "category": "Data Science",
                "difficulty": "Intermediate",
                "description": (
                    "Designed for developers looking to engineer scalable data systems with Python 3, SQLAlchemy, and data pipelines."
                ),
                "is_published": True,
                "instructor_id": marcus.id,
                "lessons": [
                    {
                        "title": "1. Idiomatic Python 3 and Modern Typing",
                        "order_index": 1,
                        "content": "Python's type hints provide clarity and catch bugs during static analysis.",
                    },
                    {
                        "title": "2. Database Persistence with SQLAlchemy ORM",
                        "order_index": 2,
                        "content": "SQLAlchemy maps Python classes to relational tables and manages transactional units of work.",
                    },
                ],
                "quiz": {
                    "title": "Python & Data Engineering Assessment",
                    "description": "Test your mastery of Python generator mechanics and SQLAlchemy ORM.",
                    "passing_score": 70,
                    "questions": [
                        {
                            "question_text": "What is the memory advantage of using a generator expression or yield over a list?",
                            "order_index": 1,
                            "points": 100,
                            "options": [
                                {"option_text": "Generators consume more RAM but run faster", "is_correct": False, "order_index": 1},
                                {"option_text": "Generators evaluate items lazily one at a time, conserving memory", "is_correct": True, "order_index": 2},
                            ],
                        },
                    ],
                },
            },
        ]

        for c_data in courses_data:
            existing_c = db.query(Course).filter(Course.title == c_data["title"]).first()
            if not existing_c:
                course = Course(
                    title=c_data["title"],
                    description=c_data["description"],
                    category=c_data["category"],
                    difficulty=c_data["difficulty"],
                    is_published=c_data["is_published"],
                    instructor_id=c_data["instructor_id"],
                )
                db.add(course)
                db.flush()

                for l_data in c_data.get("lessons", []):
                    lesson = Lesson(
                        course_id=course.id,
                        title=l_data["title"],
                        content=l_data["content"],
                        order_index=l_data["order_index"],
                    )
                    db.add(lesson)

                q_data = c_data.get("quiz")
                if q_data:
                    quiz = Quiz(
                        course_id=course.id,
                        title=q_data["title"],
                        description=q_data["description"],
                        passing_score=q_data["passing_score"],
                        is_published=True,
                        time_limit_minutes=30,
                        max_attempts=3,
                    )
                    db.add(quiz)
                    db.flush()

                    for quest_data in q_data.get("questions", []):
                        question = Question(
                            quiz_id=quiz.id,
                            question_text=quest_data["question_text"],
                            order_index=quest_data["order_index"],
                            points=quest_data["points"],
                        )
                        db.add(question)
                        db.flush()

                        for opt in quest_data.get("options", []):
                            option = AnswerOption(
                                question_id=question.id,
                                option_text=opt["option_text"],
                                is_correct=opt["is_correct"],
                                order_index=opt.get("order_index", 1),
                            )
                            db.add(option)

        db.commit()

        # 3. Create Sample Enrollment & Progress for Alex
        course1 = db.query(Course).filter(Course.title.like("%FastAPI%")).first()
        if course1 and alex:
            existing_enr = (
                db.query(CourseEnrollment)
                .filter(
                    CourseEnrollment.student_id == alex.id,
                    CourseEnrollment.course_id == course1.id,
                )
                .first()
            )
            if not existing_enr:
                enr = CourseEnrollment(
                    student_id=alex.id,
                    course_id=course1.id,
                    enrolled_at=datetime.now(timezone.utc),
                    completion_percentage=50.0,
                    status="approved",
                    reviewed_at=datetime.now(timezone.utc),
                    reviewed_by_instructor_id=course1.instructor_id,
                )
                db.add(enr)
                db.flush()

                lessons = (
                    db.query(Lesson)
                    .filter(Lesson.course_id == course1.id)
                    .order_by(Lesson.order_index)
                    .limit(2)
                    .all()
                )
                now = datetime.now(timezone.utc)
                for l in lessons:
                    db.add(
                        LessonProgress(
                            student_id=alex.id,
                            lesson_id=l.id,
                            is_completed=True,
                            completed_at=now,
                            updated_at=now,
                        )
                    )
                db.commit()

            # 5. Sample Practical Assignments
            existing_assign = db.query(Assignment).filter(Assignment.course_id == course1.id).first()
            if not existing_assign:
                from datetime import timedelta
                now = datetime.now(timezone.utc)
                due = now + timedelta(days=14)

                assign1 = Assignment(
                    course_id=course1.id,
                    title="Capstone: Modular Monolith vs Microservices Architecture Blueprint",
                    description="Design an end-to-end modular system architecture with domain boundaries and persistence strategy.",
                    instructions=(
                        "### Objectives & Deliverables\n\n"
                        "1. **Domain Boundary Definition**: Outline your core business modules (User Auth, Catalog, Enrollment, Evaluation).\n"
                        "2. **Data Layer Architecture**: Document your database modeling rationale, including indexing, foreign keys, and Alembic migrations.\n"
                        "3. **Security Analysis**: Detail how Argon2id password hashing and JWT claims enforce role-based access control (RBAC).\n"
                        "4. **API Specifications**: Provide sample RESTful request and response payloads with status code handling."
                    ),
                    max_marks=50,
                    due_date=due,
                    is_published=True,
                    allow_resubmission=True,
                    is_closed=False,
                )
                db.add(assign1)
                db.flush()

                # Graded submission from Alex Rivera
                sub1 = AssignmentSubmission(
                    assignment_id=assign1.id,
                    student_id=alex.id,
                    submission_text=(
                        "# EduVerse Architecture Blueprint\n\n"
                        "### 1. Domain Boundaries\n"
                        "Our architecture implements a clean modular monolith using FastAPI. Core bounded contexts include:\n"
                        "- Authentication: Argon2id hashing + PyJWT bearer tokens.\n"
                        "- Curriculum: Courses, hierarchical Sections, and Lessons.\n"
                        "- Assessment: Quizzes (objective) and Assignments (subjective written work).\n\n"
                        "### 2. Relational Integrity\n"
                        "Using SQLite with `PRAGMA foreign_keys=ON;` guarantees zero orphaned records. "
                        "Batch-mode Alembic migrations ensure portable schema generation ready for PostgreSQL."
                    ),
                    status="graded",
                    is_late=False,
                    submitted_at=now - timedelta(days=2),
                    updated_at=now - timedelta(days=2),
                    grade=48.0,
                    feedback="Outstanding architectural clarity! Excellent grasp of bounded contexts and relational database constraints.",
                    graded_by_id=sarah.id,
                    graded_at=now - timedelta(days=1),
                )
                db.add(sub1)

                assign2 = Assignment(
                    course_id=course1.id,
                    title="Security Audit & API Hardening Analysis",
                    description="Identify attack vectors and implement mitigation strategies for production deployments.",
                    instructions=(
                        "### Security Audit Scope\n\n"
                        "Analyze common vulnerability classes (IDOR, credential stuffing, injection, answer leakage) "
                        "and detail the programmatic guardrails EduVerse utilizes to neutralize each threat."
                    ),
                    max_marks=100,
                    due_date=now + timedelta(days=21),
                    is_published=True,
                    allow_resubmission=True,
                    is_closed=False,
                )
                db.add(assign2)
                db.commit()

        # 5. Learning Materials (Course 1)
        existing_materials = db.query(LearningMaterial).filter(LearningMaterial.course_id == course1.id).count()
        if existing_materials == 0:
            storage = get_storage_provider()
            
            # Material 1: PDF Whitepaper
            pdf_content = (
                b"%PDF-1.4\n"
                b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
                b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000102 00000 n \n"
                b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n185\n%%EOF\n"
            )
            pdf_key = "seed_architecture_whitepaper.pdf"
            storage.save_file(pdf_key, pdf_content)

            mat1 = LearningMaterial(
                course_id=course1.id,
                uploader_id=sarah.id,
                title="Full-Stack Architecture Reference Guide (PDF)",
                description="Comprehensive architecture reference covering FastAPI, SQLAlchemy ORM, and Angular standalone components.",
                original_filename="Architecture_Reference_Guide.pdf",
                storage_key=pdf_key,
                mime_type="application/pdf",
                file_size=len(pdf_content),
            )
            db.add(mat1)

            # Material 2: Plain Text Security Checklist
            txt_content = (
                b"EduVerse Security & Threat Mitigation Checklist\n"
                b"===============================================\n"
                b"1. Password Security: Enforce Argon2id with 64MB memory cost.\n"
                b"2. Authorization: Verify JWT role claims and course ownership on every endpoint.\n"
                b"3. File Storage: Never use client filenames as disk paths; use unpredictable UUID keys.\n"
                b"4. File Validation: Validate magic bytes, extensions, and content structure.\n"
                b"5. Data Protection: Prevent path traversal by validating directory boundaries.\n"
            )
            txt_key = "seed_security_checklist.txt"
            storage.save_file(txt_key, txt_content)

            mat2 = LearningMaterial(
                course_id=course1.id,
                uploader_id=sarah.id,
                title="API Security & Threat Mitigation Checklist (TXT)",
                description="Practical developer checklist for securing RESTful APIs, file uploads, and session tokens.",
                original_filename="Security_Checklist.txt",
                storage_key=txt_key,
                mime_type="text/plain",
                file_size=len(txt_content),
            )
            db.add(mat2)
            db.commit()

        # 9. Seed Announcements
        existing_announcements = db.query(CourseAnnouncement).count()
        if existing_announcements == 0 and course1:
            ann1 = CourseAnnouncement(
                course_id=course1.id,
                instructor_id=sarah.id,
                title="Welcome to Advanced Full-Stack Web Development! 🚀",
                content="Welcome everyone! Live interactive workshops will be held every Tuesday and Thursday at 4 PM EST. Please make sure to clone the starter repository and review the syllabus modules.",
                is_published=True,
            )
            ann2 = CourseAnnouncement(
                course_id=course1.id,
                instructor_id=sarah.id,
                title="Assignment 1 Deadline & Testing Checklist",
                content="A reminder that Assignment 1 is due next week. Ensure all unit tests pass locally before submitting your solution through the assignment portal.",
                is_published=True,
            )
            ann_draft = CourseAnnouncement(
                course_id=course1.id,
                instructor_id=sarah.id,
                title="Draft: Upcoming Guest Lecture Announcement",
                content="Tentative notes for guest lecture next month.",
                is_published=False,
            )
            db.add_all([ann1, ann2, ann_draft])
            db.commit()

        # 10. Seed Course Discussions & Replies
        existing_discussions = db.query(CourseDiscussion).count()
        if existing_discussions == 0 and course1 and alex:
            disc1 = CourseDiscussion(
                course_id=course1.id,
                user_id=alex.id,
                title="Best practices for FastAPI async session dependencies in tests?",
                content="When running pytest with TestClient, should we override the get_db dependency with an in-memory SQLite session or use transactions with rollback? Looking forward to your thoughts!",
                is_pinned=True,
                is_deleted=False,
            )
            disc2 = CourseDiscussion(
                course_id=course1.id,
                user_id=alex.id,
                title="Difference between Pydantic v2 model_validate and from_attributes",
                content="Can someone clarify how from_attributes replaces orm_mode in Pydantic v2?",
                is_pinned=False,
                is_deleted=False,
            )
            db.add_all([disc1, disc2])
            db.commit()

            reply1 = DiscussionReply(
                thread_id=disc1.id,
                user_id=sarah.id,
                content="Great question, Alex! For integration tests, using a separate test SQLite database file with session-scoped setup and cleanups is very predictable and closely mirrors production.",
                is_deleted=False,
            )
            db.add(reply1)
            db.commit()

            reply2 = DiscussionReply(
                thread_id=disc1.id,
                user_id=alex.id,
                parent_reply_id=reply1.id,
                content="Thank you Dr. Chen! That matches what we implemented in EduVerse tests.",
                is_deleted=False,
            )
            db.add(reply2)
            db.commit()

        # 11. Seed Notifications
        existing_notifications = db.query(Notification).count()
        if existing_notifications == 0 and alex and course1:
            notif1 = Notification(
                user_id=alex.id,
                title="New Announcement: Welcome to Advanced Full-Stack Web Development! 🚀",
                message="Dr. Sarah Chen posted an announcement in 'Full-Stack Web Development with FastAPI and Angular'.",
                notification_type="announcement",
                link_url=f"/courses/{course1.id}#announcements",
                is_read=False,
            )
            notif2 = Notification(
                user_id=alex.id,
                title="New reply on 'Best practices for FastAPI async session dependencies in tests?'",
                message="Dr. Sarah Chen replied to your discussion thread.",
                notification_type="discussion_reply",
                link_url=f"/courses/{course1.id}/discussions/1",
                is_read=False,
            )
            db.add_all([notif1, notif2])
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
