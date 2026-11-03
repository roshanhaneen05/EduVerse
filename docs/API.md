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

---

## 7. Administrator Portal (`/api/v1/admin`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/admin/stats` | Platform-wide metrics (users, courses, quizzes) | Admin |
| `GET` | `/admin/users` | List, search, and filter platform users | Admin |
| `PUT` | `/admin/users/{id}` | Update user role (e.g. promote) or active status | Admin |
| `PATCH` | `/admin/courses/{id}/publish` | Toggle publication on any course | Admin |

---

## 8. AI Learning Assistant (`/api/v1/ai`)

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| `POST` | `/ai/chat` | Send question to AI assistant | Authenticated |
| `GET` | `/ai/conversations` | List conversation histories | Authenticated |
| `GET` | `/ai/conversations/{id}` | Retrieve messages in conversation | Authenticated |
| `DELETE` | `/ai/conversations/{id}` | Delete conversation | Authenticated |

