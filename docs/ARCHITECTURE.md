# EduVerse Architecture & System Design

## 1. System Overview

EduVerse is designed as a **Modular Monolith** education platform built for high reliability, developer velocity, and seamless future migration to distributed cloud architectures.

```
+-------------------------------------------------------------------------------+
|                       EduVerse User Interface (Angular)                       |
|      Standalone Components - Reactive Forms - RxJS - CSS Design System        |
+-------------------------------------------------------------------------------+
                                        |
                          HTTPS / JSON REST API / JWT
                                        |
+-------------------------------------------------------------------------------+
|                        FastAPI Backend Modular Service                        |
|                                                                               |
|  +-------------------+  +--------------------+  +--------------------------+  |
|  |  Routing Layer    |  |  Security / RBAC   |  |   AI Learning Assistant  |  |
|  |  /auth, /courses, |  |  Argon2id Hashing  |  |   Local Fallback Engine  |  |
|  |  /lessons, /quiz  |  |  JWT Bearer Tokens |  |   Extensible LLM Provider|  |
|  +-------------------+  +--------------------+  +--------------------------+  |
|           |                       |                           |               |
|  +-------------------------------------------------------------------------+  |
|  |                     Domain Services & Business Logic                    |  |
|  |   CourseService - LessonService - QuizEvaluationService - AuthService   |  |
|  +-------------------------------------------------------------------------+  |
|           |                                                                   |
|  +-------------------------------------------------------------------------+  |
|  |                    Data Access & Persistence Layer                      |  |
|  |        SQLAlchemy ORM 2.x - Pydantic v2 Schemas - Alembic Migrations    |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
                                        |
                   Local SQLite / Cloud PostgreSQL (Target)
```

---

## 2. Backend Modular Monolith Design

### 2.1 Layer Separation
1. **Routing Layer (`app/routers/`)**: Receives HTTP requests, validates query/path parameters, applies RBAC dependencies, and delegates directly to the service layer. Routers contain zero business logic.
2. **Service Layer (`app/services/`)**: Contains all core domain logic (e.g., server-side quiz evaluation, progress percentage recalculation, course slug generation, AI reasoning engine).
3. **Data Access Layer (`app/models/`, `app/database.py`)**: Defines relational models with strict constraints, indexes, cascade deletions, and relationship mappings.
4. **Validation Schemas (`app/schemas/`)**: Pydantic v2 data models for input validation, type coercion, and safe serialization.
5. **Security & RBAC (`app/security/`)**: Password hashing with Argon2id, stateless JWT encoding/decoding, role verification, and request cookie parsing.

### 2.2 Database Portability
The database abstraction utilizes SQLAlchemy 2.0. In local development, SQLite is stored in `backend/data/eduverse.db`. Because all dialect-specific types are avoided and schema changes are managed via Alembic version scripts, switching to Azure Database for PostgreSQL requires only updating `DATABASE_URL` in `.env`.

---

## 3. Frontend Architecture (Angular)

1. **Standalone Components**: Eliminates `NgModule` overhead, enables clear dependency trees, and optimizes tree-shaking for faster page loads.
2. **Authentication Interceptor**: Automatically attaches the JWT `Authorization: Bearer <token>` header to outbound requests and handles `401 Unauthorized` responses gracefully.
3. **Route Guards**:
   - `auth.guard.ts`: Protects authenticated routes (Dashboard, Profile, AI Assistant).
   - `role.guard.ts`: Enforces role-based navigation (Instructor dashboard, Administrator portal).
4. **State Services**:
   - `AuthService`: Signals user state, role, and current session.
   - `CourseService`, `QuizService`, `AIService`: Manages data fetching, reactive observables, and cached catalogs.

---

## 4. Scalability & Extensibility

- **Decoupled Deployment**: The frontend (static build artifacts) and backend (ASGI Python app) can be deployed independently onto Azure Container Apps, AKS, or static web hosting (Azure Static Web Apps).
- **Service Extraction**: If traffic grows on specific modules (e.g., AI Assistant or Quiz Grading), the modular design allows extracting `app/services/quiz_service.py` or `app/services/ai_service.py` into distinct microservices without altering database models.

