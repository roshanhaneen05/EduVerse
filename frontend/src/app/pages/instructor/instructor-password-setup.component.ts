import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  AbstractControl,
  FormBuilder,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  Validators
} from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

function passwordMatchValidator(control: AbstractControl): ValidationErrors | null {
  const password = control.get('password')?.value;
  const confirmPassword = control.get('confirmPassword')?.value;
  return password && confirmPassword && password !== confirmPassword ? { mismatch: true } : null;
}

@Component({
  selector: 'app-instructor-password-setup',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <main class="setup-page">
      <section class="setup-card card">
        <a routerLink="/" class="brand">EduVerse</a>
        <h1>Set your instructor password</h1>
        <p>Choose a password for your instructor account. This secure link can only be used once.</p>
        @if (errorMessage) { <div class="alert alert-danger">{{ errorMessage }}</div> }
        @if (successMessage) {
          <div class="alert alert-success">
            {{ successMessage }} <a routerLink="/instructor/login">Sign in</a>
          </div>
        } @else {
          <form [formGroup]="passwordForm" (ngSubmit)="submit()">
            <label class="field">
              <span>New password</span>
              <input class="form-input" type="password" formControlName="password" autocomplete="new-password" />
            </label>
            <label class="field">
              <span>Confirm password</span>
              <input class="form-input" type="password" formControlName="confirmPassword" autocomplete="new-password" />
            </label>
            @if (passwordForm.get('password')?.touched && passwordForm.get('password')?.invalid) {
              <small>Password must be at least 8 characters and contain a letter and a number.</small>
            }
            @if (passwordForm.hasError('mismatch') && passwordForm.get('confirmPassword')?.touched) {
              <small>Passwords do not match.</small>
            }
            <button class="btn btn-primary btn-block" type="submit" [disabled]="passwordForm.invalid || isSubmitting">
              {{ isSubmitting ? 'Saving...' : 'Set Password' }}
            </button>
          </form>
        }
      </section>
    </main>
  `,
  styles: [`
    .setup-page { min-height: calc(100vh - 120px); display: grid; place-items: center; padding: 2rem 1rem; background: linear-gradient(135deg, #fff8fb, #f8f4ff); }
    .setup-card { width: min(100%, 470px); padding: 2rem; border: 1px solid #f1c8da; }
    .brand { display: inline-block; margin-bottom: 1.5rem; color: #a91f61; font-size: 1.4rem; font-weight: 800; text-decoration: none; }
    h1 { margin: 0 0 .5rem; color: #28212a; font-size: 1.65rem; }
    p { margin: 0 0 1.5rem; color: var(--text-muted); line-height: 1.5; }
    .field { display: flex; flex-direction: column; gap: .45rem; margin-bottom: 1rem; font-weight: 650; }
    small { display: block; margin: -.25rem 0 .8rem; color: #a42338; }
    button { margin-top: .5rem; }
  `]
})
export class InstructorPasswordSetupComponent {
  private readonly token: string;
  isSubmitting = false;
  errorMessage = '';
  successMessage = '';
  passwordForm: FormGroup;

  constructor(
    private fb: FormBuilder,
    private route: ActivatedRoute,
    private auth: AuthService
  ) {
    this.token = this.route.snapshot.queryParamMap.get('token') || '';
    this.passwordForm = this.fb.group({
      password: ['', [Validators.required, Validators.minLength(8), Validators.pattern(/(?=.*[A-Za-z])(?=.*\d)/)]],
      confirmPassword: ['', Validators.required]
    }, { validators: passwordMatchValidator });
  }

  submit(): void {
    if (!this.token) {
      this.errorMessage = 'This password link is missing or invalid. Contact your administrator for a new link.';
      return;
    }
    if (this.passwordForm.invalid) {
      this.passwordForm.markAllAsTouched();
      return;
    }
    this.isSubmitting = true;
    this.errorMessage = '';
    this.auth.setInstructorPassword({
      token: this.token,
      new_password: this.passwordForm.get('password')?.value || ''
    }).subscribe({
      next: response => {
        this.isSubmitting = false;
        this.successMessage = response.message;
      },
      error: error => {
        this.isSubmitting = false;
        this.errorMessage = error.error?.detail || 'Unable to set password. Request a new link from your administrator.';
      }
    });
  }
}
