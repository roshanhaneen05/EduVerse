# EduVerse Database Architecture & Data Dictionary

The EduVerse data tier is constructed on **SQLAlchemy ORM 2.x** and version-controlled using **Alembic**.

---

## 1. Storage & Engine Configuration

- **Development Storage**: Persistent SQLite file at `backend/data/eduverse.db`.
- **Production Target**: Azure Database for PostgreSQL (Flexible Server).
- **SQLite Foreign Key Enforcement**: SQLite does not enable foreign key constraint checking by default. The database initialization script registers an engine event listener:
  ```python
  @event.listens_for(Engine, "connect")
  def _set_sqlite_pragma(dbapi_connection, connection_record):
      if isinstance(dbapi_connection, SQLite3Connection):
          cursor = dbapi_connection.cursor()
          cursor.execute("PRAGMA foreign_keys=ON;")
          cursor.close()
  ```
- **Batch Alteration**: Configured in `alembic/env.py` with `render_as_batch=True` to enable SQLite table rebuilds when altering columns or constraints.

---

## 2. Entity-Relationship Architecture

```
+----------------+          +-----------------------+          +-------------------+
|     users      | 1 ---- * |   course_enrollments  | * ---- 1 |      courses      |
+----------------+          +-----------------------+          +-------------------+
  |            |                                                         |
  | 1          | 1                                                       | 1
  |            |                                                         |
  *            *                                                         *
+---------+  +--------------------+                            +-------------------+
| ai_conv |  |  lesson_progress   |                            |      lessons      |
+---------+  +--------------------+                            +-------------------+
     |                                                                   |
     * 1                                                                 |
+---------+                                                              | 1
| ai_msg  |                                                              |
+---------+                                                              *
     |                                                         +-------------------+
     +-------------------------------------------------------- |      quizzes      |
                                                               +-------------------+
                                                                         |
                                                                         | 1
                                                                         |
                                                                         *
+--------------------+                                         +-------------------+
|   quiz_attempts    | * ------------------------------------- |     questions     |
+--------------------+                                         +-------------------+
        | 1                                                              | 1
        |                                                                |
        *                                                                *
+--------------------+                                         +-------------------+
|quiz_attempt_answers|                                         |  answer_options   |
+--------------------+                                         +-------------------+
```

---

## 3. Data Dictionary

### 3.1 `users`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY | Unique user identifier |
| `full_name` | VARCHAR(255) | NOT NULL | User's legal or display name |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL, INDEX | Login email address |
| `password_hash` | VARCHAR(255) | NOT NULL | Argon2id cryptographic hash |
| `role` | VARCHAR(50) | NOT NULL, INDEX | Role: `student`, `instructor`, `admin` |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | Account operational status |
| `created_at` | DATETIME(TZ) | NOT NULL | UTC account creation timestamp |
| `updated_at` | DATETIME(TZ) | NOT NULL | UTC profile last updated timestamp |

### 3.2 `courses`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY | Unique course identifier |
| `title` | VARCHAR(255) | NOT NULL, INDEX | Course title |
| `description` | TEXT | NOT NULL | Markdown course syllabus and overview |
| `category` | VARCHAR(100) | NOT NULL, INDEX | Topic category (e.g., Web Development) |
| `difficulty` | VARCHAR(50) | NOT NULL, DEFAULT 'Beginner' | Difficulty level |
| `is_published` | BOOLEAN | NOT NULL, DEFAULT FALSE, INDEX | Publication flag |
| `instructor_id` | INTEGER | FK -> `users.id` (CASCADE) | Course author |
| `created_at` | DATETIME(TZ) | NOT NULL | Creation timestamp |
| `updated_at` | DATETIME(TZ) | NOT NULL | Last modified timestamp |

### 3.3 `course_enrollments`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY | Unique enrollment identifier |
| `student_id` | INTEGER | FK -> `users.id` (CASCADE), INDEX | Enrolled student |
| `course_id` | INTEGER | FK -> `courses.id` (CASCADE), INDEX | Enrolled course |
| `enrolled_at` | DATETIME(TZ) | NOT NULL | Timestamp of enrollment |
| `completion_percentage` | FLOAT | NOT NULL, DEFAULT 0.0 | Overall progress (0.0 to 100.0) |
*Constraints*: `uq_student_course_enrollment` (`student_id`, `course_id`), `ck_enrollment_completion_percentage` (`0.0 <= completion_percentage <= 100.0`).

### 3.4 `lessons`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY | Unique lesson identifier |
| `course_id` | INTEGER | FK -> `courses.id` (CASCADE), INDEX | Parent course |
| `title` | VARCHAR(255) | NOT NULL | Lesson title |
| `content` | TEXT | NOT NULL | Educational learning text / markdown |
| `order_index` | INTEGER | NOT NULL, DEFAULT 1 | Display sequence order (>= 1) |
| `created_at` | DATETIME(TZ) | NOT NULL | Creation timestamp |
| `updated_at` | DATETIME(TZ) | NOT NULL | Last modified timestamp |

### 3.5 `lesson_progress`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY | Unique progress record identifier |
| `student_id` | INTEGER | FK -> `users.id` (CASCADE), INDEX | Student user |
| `lesson_id` | INTEGER | FK -> `lessons.id` (CASCADE), INDEX | Completed lesson |
| `is_completed` | BOOLEAN | NOT NULL, DEFAULT FALSE | Completion status flag |
| `completed_at` | DATETIME(TZ) | NULLABLE | UTC timestamp of completion |
| `updated_at` | DATETIME(TZ) | NOT NULL | Last update timestamp |
*Constraints*: `uq_student_lesson_progress` (`student_id`, `lesson_id`).

### 3.6 `quizzes`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY | Unique quiz identifier |
| `course_id` | INTEGER | FK -> `courses.id` (CASCADE), INDEX | Parent course |
| `title` | VARCHAR(255) | NOT NULL | Assessment title |
| `description` | TEXT | NULLABLE | Instructions for students |
| `passing_score` | INTEGER | NOT NULL, DEFAULT 70 | Passing threshold (0 to 100) |
| `created_at` | DATETIME(TZ) | NOT NULL | Creation timestamp |
| `updated_at` | DATETIME(TZ) | NOT NULL | Modification timestamp |

### 3.7 `questions` & `answer_options`
- `questions`: `id`, `quiz_id` (FK), `question_text`, `order_index` (>= 1), `points` (>= 1).
- `answer_options`: `id`, `question_id` (FK), `option_text`, `is_correct` (BOOLEAN).

### 3.8 `quiz_attempts` & `quiz_attempt_answers`
- `quiz_attempts`: `id`, `quiz_id` (FK, `ondelete='SET NULL'`), `student_id` (FK, `ondelete='SET NULL'`), `score` (percentage), `total_points`, `passed` (BOOLEAN), `started_at`, `submitted_at`.
- `quiz_attempt_answers`: `id`, `attempt_id` (FK, CASCADE), `question_id` (FK, CASCADE), `selected_option_id` (FK, `SET NULL`), `is_correct` (BOOLEAN), `awarded_points` (INTEGER).
*Constraint*: `uq_attempt_question` (`attempt_id`, `question_id`).

### 3.9 `ai_conversations` & `ai_messages`
- `ai_conversations`: `id`, `user_id` (FK, CASCADE), `title`, `created_at`, `updated_at`.
- `ai_messages`: `id`, `conversation_id` (FK, CASCADE), `role` (`user`, `assistant`, `system`), `content`, `created_at`.

---

## 4. Alembic Workflow & Commands

```powershell
# Inspect current applied revision
cd C:\EduVerse\backend
.\.venv\Scripts\alembic.exe current
# Expected: fb4ef543d5d3 (head)

# Apply migrations
.\.venv\Scripts\alembic.exe upgrade head

# Generate a new migration
.\.venv\Scripts\alembic.exe revision --autogenerate -m "migration_description"
```
