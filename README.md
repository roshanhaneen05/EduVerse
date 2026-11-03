# EduVerse — AI-Powered Learning Management System

EduVerse is a full-stack, modular Learning Management System (LMS) with role-based access control (Student, Instructor, Administrator), course management, interactive quizzes with server-side auto-evaluation, progress tracking, and an AI learning assistant with a local fallback.

---

## Project Structure

```
EduVerse/
├── backend/          # FastAPI Python service, SQLAlchemy, Alembic, SQLite
├── frontend/         # Angular frontend (TypeScript, standalone components)
├── docs/             # Technical architecture, API, security, and cloud docs
├── scripts/          # Automation and bootstrap helper scripts
├── .gitignore        # Git exclusion rules
├── .env.example      # Root environment template
└── README.md         # Project documentation
```

---

## Implementation Progress

- [x] **PHASE 1 — Workspace & Tooling Inspection**: Inspected environment (Python 3.13.5, Node v22.16.0, npm 11.4.1, Git 2.49.0).
- [x] **PHASE 2 — Backend Structure & Configuration**: Set up virtual environment, dependencies (`FastAPI`, `Uvicorn`, `Pydantic v2`, `SQLAlchemy`, `Alembic`, `PyJWT`, `pwdlib[argon2]`, `pytest`, `httpx`), modular architecture, configuration via Pydantic settings, health endpoint, Alembic config, and automated tests.
- [ ] **PHASE 3 — Database, Models & Migrations**: Define SQLAlchemy models (User, Course, CourseEnrollment, Lesson, LessonProgress, Quiz, Question, AnswerOption, QuizAttempt, QuizAttemptAnswer, AIConversation) and generate initial Alembic migration.
- [ ] **PHASE 4 — Authentication & Authorization**: Argon2 password hashing, JWT bearer tokens, role-based access control, registration, and login.
- [ ] **PHASE 5 — Course Management & Enrollment**: Course creation, publishing, search/filtering, and student enrollment.
- [ ] **PHASE 6 — Lessons & Progress Tracking**: Lesson ordering, completion tracking, and progress metrics.
- [ ] **PHASE 7 — Quizzes & Results**: Multiple-choice assessments, server-side scoring, attempt history.
- [ ] **PHASE 8 — Instructor & Administrator Portals**: Course analytics, student management, role assignment.
- [ ] **PHASE 9 — AI Learning Assistant**: Context-aware educational assistant with robust local demonstration provider.
- [ ] **PHASE 10 — Angular Frontend Foundation**: Project setup, routing, services, state management, UI design system.
- [ ] **PHASE 11 — Frontend Dashboards & Pages**: Complete implementation of all 18 specified pages/views.
- [ ] **PHASE 12 — Seed Demonstration Data**: Deterministic, realistic seed data for courses, users, and quizzes.
- [ ] **PHASE 13 — Automated Testing**: End-to-end backend and frontend test suites.
- [ ] **PHASE 14 — Integration & Flow Verification**: Full system runtime testing and verification.
- [ ] **PHASE 15 — Complete Documentation**: Architecture, API, Database, Security, and Azure migration docs.

