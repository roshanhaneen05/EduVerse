# EduVerse Security Architecture & DevSecOps Foundation

## 1. Threat Modeling & Defensive Controls

EduVerse implements security by design across authentication, data integrity, authorization, and network layers.

### 1.1 Password Hashing (Argon2id)
- **Standard**: Argon2id via `pwdlib` and `argon2-cffi`.
- **Memory-Hard Defense**: Configured to resist ASIC and GPU-accelerated brute-force attacks.
- **Strength Validation**: Enforces length >= 8, requiring letters and numerical characters.
- **Zero Plaintext Storage**: Passwords are never logged, serialized, or stored unhashed.

### 1.2 Authentication & Token Security
- **Stateless JWTs**: Cryptographically signed with HS256 algorithm and configured expiration (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **HttpOnly Cookies**: Supported via `SameSite=Lax` and `HttpOnly=True` flag to prevent XSS credential theft.
- **Privilege Escalation Defense**: Public `/register` endpoint strictly forces user role to `student`. Even if a client sends `{"role": "admin"}`, the backend rejects or overrides the role to `student`.

### 1.3 Role-Based Access Control (RBAC)
- Enforced at both router and dependency injection layers in FastAPI:
  - `require_admin`: Confirms user role is `admin`.
  - `require_instructor`: Confirms user is `instructor` or `admin`.
  - `check_course_ownership`: Validates that course modifications can only be performed by the owning instructor or system administrator.
- Client-side Angular Route Guards mirror permissions to prevent unauthorized UI rendering.

### 1.4 Assessment Integrity
- **Server-Side Scoring**: Quiz scores are never accepted from client requests. The server grades submissions directly against database answer keys.
- **Answer Key Masking**: The quiz presentation endpoint (`GET /api/v1/quizzes/{id}`) strips out `is_correct` flags and explanation notes until the user submits.
- **Result Confidentiality**: Students are forbidden from accessing assessment attempts that belong to other users.

### 1.5 CORS & Network Boundaries
- Local development permits origins `http://localhost:4200` and `http://127.0.0.1:4200`.
- All requests outside allowed origins are blocked by FastAPI's `CORSMiddleware`.

---

## 2. DevSecOps CI/CD Integration

### 2.1 GitHub Actions Workflow (`.github/workflows/ci.yml`)
Automated pipeline runs on every pull request and push to `main`:
1. **Python Security Linting**: `bandit` for static application security testing (SAST).
2. **Dependency Vulnerability Scanning**: `pip-audit` or `safety` checks for vulnerable libraries.
3. **Automated Unit & Integration Testing**: `pytest` running full coverage test suites.
4. **Angular Lint & Build**: Validates TypeScript compilation and bundle integrity.

