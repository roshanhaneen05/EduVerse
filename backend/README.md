# EduVerse — Backend Service

The EduVerse backend is a modular monolith built with **Python 3.10+**, **FastAPI**, **SQLAlchemy ORM 2.x**, **Pydantic v2**, and **Alembic**.

---

## 1. Database Architecture & Storage

- **Database Engine**: SQLite 3 by default for local development; MySQL is supported with `mysql+pymysql://...` in `DATABASE_URL`, and PostgreSQL remains supported.
- **Persistent Storage Location**: `C:\EduVerse\backend\data\eduverse.db` (configured via `DATABASE_URL` in `.env`).
- **Foreign Key Enforcement**: SQLite does not enable foreign keys by default. EduVerse automatically activates `PRAGMA foreign_keys=ON;` on every database connection via an engine connection listener in [database.py](file:///C:/EduVerse/backend/app/database.py).
- **Session Lifecycle**: Database sessions are provided per request via FastAPI dependency injection (`get_db`) and closed in `finally` blocks.

---

## 2. Implemented Models & Relationships

All models are defined in [app/models/](file:///C:/EduVerse/backend/app/models/) and exported in [__init__.py](file:///C:/EduVerse/backend/app/models/__init__.py):

1. **`User`** ([user.py](file:///C:/EduVerse/backend/app/models/user.py)):
   - Fields: `id`, `full_name`, `email` (unique index), `password_hash`, `role` (`student`, `instructor`, `admin`), `is_active`, `created_at`, `updated_at`.
   - Constraints: `ck_users_role_valid` check constraint.
   - Relationships: `courses`, `enrollments`, `lesson_progress`, `quiz_attempts`, `ai_conversations`.

2. **`Course`** ([course.py](file:///C:/EduVerse/backend/app/models/course.py)):
   - Fields: `id`, `title` (indexed), `description`, `category` (indexed), `difficulty`, `is_published` (indexed), `instructor_id` (FK -> `users.id`), `created_at`, `updated_at`.
   - Relationships: `instructor`, `lessons`, `quizzes`, `enrollments`.

3. **`CourseEnrollment`** ([enrollment.py](file:///C:/EduVerse/backend/app/models/enrollment.py)):
   - Fields: `id`, `student_id` (FK -> `users.id`), `course_id` (FK -> `courses.id`), `enrolled_at`, `completion_percentage`.
   - Constraints: `uq_student_course_enrollment` (unique student-course pair), `ck_enrollment_completion_percentage` (0.0 to 100.0).

4. **`Lesson`** ([lesson.py](file:///C:/EduVerse/backend/app/models/lesson.py)):
   - Fields: `id`, `course_id` (FK -> `courses.id`), `title`, `content`, `order_index` (>= 1), `created_at`, `updated_at`.
   - Relationships: `course`, `progress_records`.

5. **`LessonProgress`** ([lesson.py](file:///C:/EduVerse/backend/app/models/lesson.py)):
   - Fields: `id`, `student_id` (FK -> `users.id`), `lesson_id` (FK -> `lessons.id`), `is_completed`, `completed_at`, `updated_at`.
   - Constraints: `uq_student_lesson_progress` (unique student-lesson pair).

6. **`Quiz`** ([quiz.py](file:///C:/EduVerse/backend/app/models/quiz.py)):
   - Fields: `id`, `course_id` (FK -> `courses.id`), `title`, `description`, `passing_score` (0 to 100), `created_at`, `updated_at`.
   - Relationships: `course`, `questions`, `attempts`.

7. **`Question`** ([quiz.py](file:///C:/EduVerse/backend/app/models/quiz.py)):
   - Fields: `id`, `quiz_id` (FK -> `quizzes.id`), `question_text`, `order_index` (>= 1), `points` (>= 1).
   - Relationships: `quiz`, `options`.

8. **`AnswerOption`** ([quiz.py](file:///C:/EduVerse/backend/app/models/quiz.py)):
   - Fields: `id`, `question_id` (FK -> `questions.id`), `option_text`, `is_correct`.
   - Relationships: `question`.

9. **`QuizAttempt`** ([quiz.py](file:///C:/EduVerse/backend/app/models/quiz.py)):
   - Fields: `id`, `quiz_id` (FK -> `quizzes.id`, `ondelete="SET NULL"`), `student_id` (FK -> `users.id`, `ondelete="SET NULL"`), `score`, `total_points`, `passed`, `started_at`, `submitted_at`.
   - Historical preservation: Deleting users or quizzes sets foreign keys to NULL without deleting attempt history.

10. **`QuizAttemptAnswer`** ([quiz.py](file:///C:/EduVerse/backend/app/models/quiz.py)):
    - Fields: `id`, `attempt_id` (FK -> `quiz_attempts.id`), `question_id` (FK -> `questions.id`), `selected_option_id` (FK -> `answer_options.id`), `is_correct`, `awarded_points`.
    - Constraints: `uq_attempt_question` (prevents duplicate answers to the same question within an attempt).

11. **`AIConversation` & `AIMessage`** ([ai.py](file:///C:/EduVerse/backend/app/models/ai.py)):
    - `AIConversation`: `id`, `user_id` (FK -> `users.id`), `title`, `created_at`, `updated_at`.
    - `AIMessage`: `id`, `conversation_id` (FK -> `ai_conversations.id`), `role`, `content`, `created_at`.

---

## 3. Database Migrations (Alembic)

Migrations are managed with Alembic using `render_as_batch=True` to support SQLite schema operations safely.

### Inspect Current Revision
```powershell
cd C:\EduVerse\backend
.\.venv\Scripts\alembic.exe current
```
*Expected output*: `7b2c4e6a9d10 (head)` after applying all migrations.

### Generate New Revision
```powershell
.\.venv\Scripts\alembic.exe revision --autogenerate -m "description_of_changes"
```

### Apply Migrations
```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

The instructor-management migration adds one-to-one instructor profiles and expiring, single-use password setup tokens. It backfills existing instructor accounts so their course ownership and access remain intact. Public instructor sign-up is disabled; administrators create accounts in the Admin Dashboard. Configure `FRONTEND_BASE_URL` and the existing `EMAIL_*` settings in `backend/.env` for clickable setup, reset, and account-status emails.

The student AI-learning migration adds separate, student-owned practice quizzes and attempts, study preferences/plans/tasks, deadline records, and persistent study reminders. Existing instructor-authored assessments and student enrollment/progress tables are reused without changing their behavior.

### Configure AI Learning Tools

Set the following in `backend/.env` to enable AI quiz generation, short-answer grading, and personalized plan generation:

```env
AI_PROVIDER=gemini
AI_API_KEY=your-google-gemini-api-key
AI_MODEL=gemini-3.8-flash
AI_TIMEOUT_SECONDS=45
```

The Google Gemini API key is read only from the backend environment and is never returned by the API. With no key configured, AI-learning generation returns an explicit service-unavailable response rather than fabricated results. An existing `AI_PROVIDER=openai` value is temporarily accepted for compatibility, but still uses Google Gemini; update it to `gemini`. The legacy AI assistant remains unchanged.

Student-only endpoints are under `/api/v1/student/ai-learning`: `/courses`, `/quizzes`, `/quizzes/history`, `/attempts/{id}`, and `/planner` (including plan, task, preference, and reminder operations). Every quiz, attempt, plan, task, and reminder is scoped to the authenticated student; quiz generation also requires an approved course enrollment and a selected module or lesson.

---

## 4. Running Database & Automated Tests

EduVerse uses an isolated SQLite database (`data/test_eduverse.db`) during test runs.

```powershell
cd C:\EduVerse\backend
# Run the dedicated database test suite:
.\.venv\Scripts\python.exe -m pytest -v tests/test_database.py

# Run the complete test suite:
.\.venv\Scripts\python.exe -m pytest -v
```

## 5. Additive Demo Data

Run the idempotent demo seeder from the backend directory:

```powershell
cd C:\Users\SWATHY\EduVerse\backend
..\.venv\Scripts\python.exe .\seed_data.py
```

The script writes only to the existing `data\eduverse.db`, uses the application's Argon2 password hasher, and does not update or delete existing rows. It reuses matching demo accounts and course records. Newly created demo accounts use `EduVerseDemo2026!` unless `DEMO_PASSWORD` is set in the environment. The script prints per-table insert counts, final table totals, and the foreign-key integrity result.
