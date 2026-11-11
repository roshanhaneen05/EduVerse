import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

export type RegisterRole = 'student' | 'instructor';

function passwordMatchValidator(control: AbstractControl): ValidationErrors | null {
  const password = control.get('password');
  const confirmPassword = control.get('confirm_password');
  if (password && confirmPassword && password.value !== confirmPassword.value) {
    return { passwordMismatch: true };
  }
  return null;
}

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="auth-page">
      <!-- Ambient Decorative Curved Waves in Background -->
      <div class="bg-decorative-waves" aria-hidden="true">
        <svg class="corner-wave top-right-wave" viewBox="0 0 500 500" fill="none">
          <path d="M500,0 C380,80 320,220 500,380 L500,0 Z" fill="rgba(196, 181, 253, 0.45)"/>
        </svg>
        <svg class="corner-wave bottom-left-wave" viewBox="0 0 500 500" fill="none">
          <path d="M0,500 C140,420 180,300 0,160 L0,500 Z" fill="rgba(196, 181, 253, 0.5)"/>
        </svg>
      </div>

      <div class="auth-card card">
        <div class="auth-header">
          <div class="auth-cap-wrap">
            <svg width="34" height="34" viewBox="0 0 32 32" fill="none">
              <path d="M16 4L2 11L16 18L30 11L16 4Z" fill="#4f46e5"/>
              <path d="M6 14.5V21C6 24.5 10.5 27.5 16 27.5C21.5 27.5 26 24.5 26 21V14.5" stroke="#4f46e5" stroke-width="2.5" stroke-linecap="round"/>
              <path d="M30 11V21M30 21L28 19M30 21L32 19" stroke="#4f46e5" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <span class="auth-brand-name">EduVerse</span>
          <h2>
            @if (selectedRole === 'instructor') {
              Register as Instructor
            } @else {
              Create Student Account
            }
          </h2>
          <p class="auth-subtitle">
            @if (selectedRole === 'instructor') {
              Share your expertise, publish courses, and inspire learners worldwide
            } @else {
              Join thousands of students and start your learning journey today
            }
          </p>
        </div>

        @if (errorMessage) {
          <div class="alert alert-danger">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>{{ errorMessage }}</span>
          </div>
        }

        <form [formGroup]="registerForm" (ngSubmit)="onSubmit()" class="auth-form">
          <div class="form-group">
            <label class="form-label" for="full_name">
              {{ selectedRole === 'instructor' ? 'Instructor Full Name' : 'Full Name' }}
            </label>
            <input
              id="full_name"
              type="text"
              class="form-input"
              formControlName="full_name"
              [placeholder]="selectedRole === 'instructor' ? 'e.g. Dr. Sarah Chen' : 'e.g. Jordan Taylor'"
              [class.input-error]="isFieldInvalid('full_name')"
            />
            @if (isFieldInvalid('full_name')) {
              <div class="form-error">Full name is required (min 2 characters).</div>
            }
          </div>

          <div class="form-group">
            <label class="form-label" for="email">Email Address</label>
            <input
              id="email"
              type="email"
              class="form-input"
              formControlName="email"
              [placeholder]="selectedRole === 'instructor' ? 'e.g. instructor@eduverse.io' : 'e.g. student@eduverse.io'"
              [class.input-error]="isFieldInvalid('email')"
            />
            @if (isFieldInvalid('email')) {
              <div class="form-error">Please enter a valid email address.</div>
            }
          </div>

          <div class="form-group">
            <label class="form-label" for="password">Password</label>
            <input
              id="password"
              type="password"
              class="form-input"
              formControlName="password"
              placeholder="At least 8 characters, including a letter and number"
              [class.input-error]="isFieldInvalid('password')"
            />
            @if (isFieldInvalid('password')) {
              <div class="form-error">
                Password must be at least 8 characters and contain a letter and a number.
              </div>
            }
          </div>

          <div class="form-group">
            <label class="form-label" for="confirm_password">Confirm Password</label>
            <input
              id="confirm_password"
              type="password"
              class="form-input"
              formControlName="confirm_password"
              placeholder="Re-enter password"
              [class.input-error]="registerForm.hasError('passwordMismatch') && registerForm.get('confirm_password')?.touched"
            />
            @if (registerForm.hasError('passwordMismatch') && registerForm.get('confirm_password')?.touched) {
              <div class="form-error">Passwords do not match.</div>
            }
          </div>

          <button type="submit" class="btn btn-primary btn-block" [disabled]="registerForm.invalid || isLoading">
            @if (isLoading) {
              <div class="spinner-sm"></div>
              <span>Creating {{ selectedRole === 'instructor' ? 'Instructor' : 'Student' }} Account...</span>
            } @else {
              <span>Register as {{ selectedRole === 'instructor' ? 'Instructor' : 'Student' }}</span>
              <span class="arrow-circle">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 12h14"/>
                  <path d="m12 5 7 7-7 7"/>
                </svg>
              </span>
            }
          </button>
        </form>

        <div class="card-divider-line">
          <span class="divider-caption">Already have an account?</span>
        </div>

        <a [routerLink]="['/', selectedRole, 'login']" class="signin-pill-btn">
          Sign In
        </a>
      </div>
    </div>
  `,
  styles: [`
    .auth-page {
      position: relative;
      min-height: calc(100vh - 120px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 3rem 1.5rem;
      background: linear-gradient(135deg, #fbfaff 0%, #f6f3fe 50%, #ede8fc 100%);
      overflow: hidden;
    }

    .bg-decorative-waves {
      position: absolute;
      inset: 0;
      pointer-events: none;
      overflow: hidden;
      z-index: 1;
    }
    .corner-wave {
      position: absolute;
      width: 420px;
      height: 420px;
    }
    .top-right-wave {
      top: 0;
      right: 0;
    }
    .bottom-left-wave {
      bottom: 0;
      left: 0;
    }

    .auth-card {
      position: relative;
      z-index: 5;
      max-width: 480px;
      width: 100%;
      padding: 2.5rem 2.25rem;
      background: #ffffff;
      border: 1px solid rgba(221, 214, 254, 0.7);
      border-radius: 24px;
      box-shadow: 0 15px 35px -10px rgba(99, 102, 241, 0.12);
    }
    .auth-header {
      text-align: center;
      margin-bottom: 1.75rem;
    }
    .auth-cap-wrap {
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 0.35rem;
    }
    .auth-brand-name {
      font-size: 1.45rem;
      font-weight: 800;
      color: #1e1b4b;
      letter-spacing: -0.02em;
      display: block;
      margin-bottom: 0.75rem;
    }
    .auth-header h2 {
      font-size: 1.55rem;
      font-weight: 800;
      color: #0f172a;
      letter-spacing: -0.02em;
      margin-bottom: 0.35rem;
    }
    .auth-subtitle {
      color: #64748b;
      font-size: 0.925rem;
      line-height: 1.5;
    }

    .btn-block {
      width: 100%;
      margin-top: 1.25rem;
      padding: 0.85rem;
      font-size: 1rem;
      border-radius: 12px;
      gap: 0.6rem;
    }
    .arrow-circle {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.25);
    }
    .input-error {
      border-color: var(--danger) !important;
    }

    .card-divider-line {
      position: relative;
      text-align: center;
      margin: 1.75rem 0 1.25rem 0;
    }
    .card-divider-line::before {
      content: '';
      position: absolute;
      top: 50%;
      left: 0;
      right: 0;
      height: 1px;
      background: #e2e8f0;
      z-index: 1;
    }
    .divider-caption {
      position: relative;
      z-index: 2;
      background: #ffffff;
      padding: 0 0.85rem;
      font-size: 0.8rem;
      font-weight: 600;
      color: #94a3b8;
    }

    .signin-pill-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      padding: 0.8rem 1rem;
      border: 1.5px solid #ddd6fe;
      border-radius: 12px;
      background: #ffffff;
      color: #4f46e5;
      font-size: 0.95rem;
      font-weight: 700;
      text-decoration: none;
      transition: all 0.2s ease;
      box-shadow: 0 2px 6px rgba(99, 102, 241, 0.05);
    }
    .signin-pill-btn:hover {
      background: #ede9fe;
      border-color: #c4b5fd;
      color: #4338ca;
      transform: translateY(-1px);
    }

    .spinner-sm {
      width: 18px;
      height: 18px;
      border: 2.5px solid #ffffff;
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  `]
})
export class RegisterComponent implements OnInit {
  registerForm: FormGroup;
  selectedRole: RegisterRole = 'student';
  isLoading = false;
  errorMessage = '';

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router,
    private route: ActivatedRoute
  ) {
    this.registerForm = this.fb.group({
      full_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(100)]],
      email: ['', [Validators.required, Validators.email]],
      password: [
        '',
        [Validators.required, Validators.minLength(8), Validators.pattern(/(?=.*[A-Za-z])(?=.*\d)/)]
      ],
      confirm_password: ['', [Validators.required]]
    }, { validators: passwordMatchValidator });
  }

  ngOnInit(): void {
    const role = this.route.snapshot.data['role'];
    this.selectedRole = role === 'instructor' ? 'instructor' : 'student';
  }

  isFieldInvalid(field: string): boolean {
    const control = this.registerForm.get(field);
    return !!(control && control.invalid && (control.dirty || control.touched));
  }

  onSubmit(): void {
    if (this.registerForm.invalid) return;

    this.isLoading = true;
    this.errorMessage = '';

    const { full_name, email, password } = this.registerForm.value;

    this.auth.register({
      full_name: full_name.trim(),
      email: email.trim(),
      password,
      role: this.selectedRole
    }).subscribe({
      next: () => {
        // Automatically login the newly created user
        this.auth.login({ email: email.trim(), password }).subscribe({
          next: (res) => {
            this.isLoading = false;
            const targetRole = res.user?.role || this.selectedRole;
            if (targetRole === 'instructor') {
              this.router.navigate(['/instructor/dashboard']);
            } else {
              this.router.navigate(['/student/dashboard']);
            }
          },
          error: () => {
            this.isLoading = false;
            this.router.navigate([`/${this.selectedRole}/login`]);
          }
        });
      },
      error: (err) => {
        this.isLoading = false;
        if (err.status === 0) {
          this.errorMessage = 'Unable to connect to the EduVerse backend at http://127.0.0.1:8000. Start the backend in a separate terminal and try again.';
          return;
        }

        const detail = err.error?.detail;
        if (typeof detail === 'string') {
          this.errorMessage = detail;
        } else if (Array.isArray(detail)) {
          this.errorMessage = detail
            .map((item: { msg?: string }) => item.msg)
            .filter((message: string | undefined): message is string => !!message)
            .join(' ');
        } else {
          this.errorMessage = 'Registration failed. Please check your information and try again.';
        }
      }
    });
  }
}
