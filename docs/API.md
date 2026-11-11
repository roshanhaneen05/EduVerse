# EduVerse REST API Specification

**Base URL**: `http://localhost:8000/api/v1`  
**Interactive Docs**: `http://localhost:8000/docs` (Swagger UI)  
**ReDoc**: `http://localhost:8000/redoc`

---

## 1. System Endpoints

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | API Welcome & Metadata | No |
| `GET` | `/health` | Top-level Health Check | No |
| `GET` | `/api/v1/health` | Versioned Health Check | No |

---

## 2. Authentication & Profile (`/api/v1/auth`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| `POST` | `/register` | Register new student account | Public |
| `POST` | `/login` | Authenticate and obtain JWT token | Public |
| `POST` | `/logout` | Log out and clear session cookie | Public |
| `GET` | `/me` | Get current user profile | Authenticated |
| `PUT` | `/profile` | Update profile information | Authenticated |
| `PUT` | `/password` | Change user password | Authenticated |

`POST /api/v1/auth/login` accepts `email`, `password`, and optional `remember_me` (default `true`). The server verifies the stored password hash and returns the role from the matching database user; clients must not submit or select a role. The frontend routes students, instructors, and administrators to their respective dashboards. Setting `remember_me` to `false` makes the authentication cookie session-only.

---

## 3. Course Catalog & Enrollment (`/api/v1/courses`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/courses` | Browse published courses (search, filter, paginate) | Public |
| `GET` | `/courses/{id}` | Get course detail with lesson & quiz outline | Public / Enrolled |
| `POST` | `/courses/{id}/enroll` | Enroll current student in course | Student |
| `DELETE` | `/courses/{id}/enroll` | Drop / unenroll from course | Student |

---

## 4. Student Progress (`/api/v1/enrollments`, `/api/v1/lessons`, `/api/v1/student`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/enrollments/my-courses` | List enrolled courses with progress | Student |
| `GET` | `/student/dashboard` | Student dashboard statistics & history | Student |
| `GET` | `/lessons/{id}` | Get lesson content and navigation | Enrolled Student |
| `POST` | `/lessons/{id}/complete` | Mark lesson completed, recalculate progress | Enrolled Student |

---

## 5. Quizzes & Assessments (`/api/v1/quizzes`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/quizzes/{id}` | Get quiz questions (hides answer keys) | Enrolled Student |
| `POST` | `/quizzes/{id}/submit` | Submit answers for server-side evaluation | Enrolled Student |
| `GET` | `/quizzes/attempts/{id}` | View detailed attempt result with explanations | Owner / Instructor |
| `GET` | `/quizzes/my-history` | View student's past quiz attempts | Student |

---

## 6. Instructor Portal (`/api/v1/instructor`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/instructor/dashboard` | Instructor statistics and recent student enrollments | Instructor / Admin |
| `GET` | `/instructor/enrollments` | List student name, email, course, enrollment date, and status for the instructor's courses | Instructor / Admin |
| `POST` | `/admin/email/test` | Send a test message to the supplied recipient (development only) | Admin |
| `GET` | `/instructor/courses` | List courses owned by instructor | Instructor / Admin |
| `POST` | `/instructor/courses` | Create new course | Instructor / Admin |
| `PUT` | `/instructor/courses/{id}` | Update course metadata | Course Owner / Admin |
| `DELETE` | `/instructor/courses/{id}` | Delete course | Course Owner / Admin |
| `PATCH` | `/instructor/courses/{id}/publish` | Toggle course published state | Course Owner / Admin |
| `GET` | `/instructor/courses/{id}/students` | View enrolled students & progress | Course Owner / Admin |
| `POST` | `/instructor/courses/{id}/lessons` | Add lesson to course | Course Owner / Admin |
| `PUT` | `/instructor/lessons/{id}` | Update lesson content | Course Owner / Admin |
| `DELETE` | `/instructor/lessons/{id}` | Delete lesson | Course Owner / Admin |
| `GET` | `/instructor/courses/{id}/quizzes` | Get quizzes with answer keys | Course Owner / Admin |
| `POST` | `/instructor/courses/{id}/quizzes` | Create quiz with questions and answers | Course Owner / Admin |
| `DELETE` | `/instructor/quizzes/{id}` | Delete quiz | Course Owner / Admin |

### Enrollment email notifications

Successful student enrollment is committed before the backend attempts an instructor notification. The response includes `email_notification_status` (`sent`, `failed`, or `not_configured`); an SMTP failure does not undo the enrollment. Notification delivery uses the assigned instructor's address from the database.

Configure these values in `backend/.env` (see `backend/.env.example`): `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=true`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `DEFAULT_FROM_EMAIL`. Enable 2-Step Verification on the sending Google account and create an App Password; use that App Password for `EMAIL_HOST_PASSWORD`, not your normal account password. Set `DEFAULT_FROM_EMAIL` to the sending address. SMTP credentials remain backend-only. The legacy `SMTP_*` environment names are accepted for compatibility. Restart the backend after editing `.env`.

To check connectivity and send a notification, start the backend, authenticate as a student, and `POST /api/v1/courses/{course_id}/enroll` for a published course that does not already have an enrollment for that student. A successful response reports `email_notification_status: "sent"` only after Gmail accepts the message; `failed` and `not_configured` are logged and enrollment remains saved. A second request for the same student/course returns `409` and does not send another email.

An administrator can test SMTP without enrolling a student by posting `{"recipient_email":"you@example.com"}` to `/api/v1/admin/email/test` with the admin bearer token. This endpoint exists only when `ENVIRONMENT=development`; it reports success only after SMTP accepts the message and never returns credentials.

The enrollment status migration and any remaining migrations can be applied from `backend` with:

```powershell
python -m alembic upgrade head
```

If the backend virtual environment is activated, `alembic upgrade head` is equivalent. Existing enrollments are retained; rows with 100% completion are marked `completed`, and the rest are marked `active`.

---

## 7. Administrator Portal (`/api/v1/admin`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/admin/stats` | Platform-wide metrics (users, courses, quizzes) | Admin |
| `GET` | `/admin/users` | List, search, and filter platform users | Admin |
| `PUT` | `/admin/users/{id}` | Update user role (e.g. promote) or active status | Admin |
| `PATCH` | `/admin/courses/{id}/publish` | Toggle publication on any course | Admin |
| `GET` | `/admin/analytics/dashboard` | Consolidated overview, student, course, instructor, trend, and activity analytics | Admin |
| `GET` | `/admin/analytics/overview` | Platform summary statistics | Admin |
| `GET` | `/admin/analytics/students` | Student counts, enrollment metrics, and performance rankings | Admin |
| `GET` | `/admin/analytics/courses` | Course counts, categories, enrollment, and completion rankings | Admin |
| `GET` | `/admin/analytics/instructors` | Instructor course and enrollment metrics | Admin |
| `GET` | `/admin/analytics/trends` | Monthly registrations, enrollments, and lesson activity | Admin |
| `GET` | `/admin/analytics/activities` | Recent registrations, course creation, enrollments, and completions | Admin |
| `GET` | `/admin/analytics/export?format=csv\|pdf` | Download a CSV or PDF analytics report | Admin |

Analytics routes accept optional `start_date` and `end_date` query parameters in `YYYY-MM-DD` format. Supply both dates together; the start and end dates are inclusive. Account totals, active-account counts, and published-course totals are lifetime values. Enrollment, completion, new-registration, activity, and trend values use the selected period where applicable. Student activity is based on recorded lesson-progress updates; course completion activity uses completed lesson timestamps and completed enrollment records. These analytics endpoints do not return student email addresses or other contact details. No database migration is required.

The Angular dashboard is available at `/admin/analytics` and is limited to authenticated administrators by the existing role guard. The API independently enforces the administrator role.

---

## 8. AI Learning Assistant (`/api/v1/ai`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| `POST` | `/ai/chat` | Send question to AI assistant | Authenticated |
| `GET` | `/ai/conversations` | List conversation histories | Authenticated |
| `GET` | `/ai/conversations/{id}` | Retrieve messages in conversation | Authenticated |
| `DELETE` | `/ai/conversations/{id}` | Delete conversation | Authenticated |
