import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { User } from '../../core/models/user.model';

function passwordMatchValidator(control: AbstractControl): ValidationErrors | null {
  const newPass = control.get('new_password');
  const confirmPass = control.get('confirm_password');
  if (newPass && confirmPass && newPass.value !== confirmPass.value) {
    return { passwordMismatch: true };
  }
  return null;
}

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <div class="profile-page">
      <div class="container profile-container">
        <div class="page-header">
          <h1>Account Settings & Profile</h1>
          <p class="subtitle">Manage your personal information, role details, and security credentials.</p>
        </div>

        <div class="profile-layout">
          <!-- Left: User Identity Card -->
          <div class="identity-card card">
            <div class="avatar-large">
              {{ getInitials(user?.full_name) }}
            </div>
            <h2 class="user-display-name">{{ user?.full_name }}</h2>
            <div class="user-email-text">{{ user?.email }}</div>

            <div class="role-badge-container">
              <span class="badge" [ngClass]="getRoleBadgeClass(user?.role)">
                {{ user?.role }}
              </span>
              <span class="badge" [ngClass]="user?.is_active ? 'badge-success' : 'badge-danger'">
                {{ user?.is_active ? 'Active Account' : 'Inactive' }}
              </span>
            </div>

            <div class="profile-metadata">
              <div class="meta-line">
                <span class="meta-label">Member Since:</span>
                <span class="meta-val">{{ user?.created_at | date:'mediumDate' }}</span>
              </div>
              <div class="meta-line">
                <span class="meta-label">User ID:</span>
                <span class="meta-val">#{{ user?.id }}</span>
              </div>
            </div>
          </div>

          <!-- Right: Forms -->
          <div class="forms-column">
            <!-- Profile Info Form -->
            <div class="card form-card">
              <h3>Personal Information</h3>
              <p class="form-desc">Update your display name visible to instructors and classmates.</p>

              @if (profileSuccess) {
                <div class="alert alert-success">{{ profileSuccess }}</div>
              }
              @if (profileError) {
                <div class="alert alert-danger">{{ profileError }}</div>
              }

              <form [formGroup]="profileForm" (ngSubmit)="onSaveProfile()">
                <div class="form-group">
                  <label class="form-label" for="full_name">Full Name</label>
                  <input
                    id="full_name"
                    type="text"
                    class="form-input"
                    formControlName="full_name"
                  />
                </div>

                <div class="form-group">
                  <label class="form-label">Email Address (Read-Only)</label>
                  <input
                    type="text"
                    class="form-input read-only-input"
                    [value]="user?.email"
                    disabled
                  />
                  <small class="form-hint">Email address cannot be modified once registered.</small>
                </div>

                <button type="submit" class="btn btn-primary" [disabled]="profileForm.invalid || isSavingProfile">
                  @if (isSavingProfile) {
                    <span>Saving...</span>
                  } @else {
                    <span>Save Changes</span>
                  }
                </button>
              </form>
            </div>

            <!-- Password Change Form -->
            <div class="card form-card">
              <h3>Change Password</h3>
              <p class="form-desc">Ensure your account is protected by an Argon2id-hashed secure password.</p>

              @if (passwordSuccess) {
                <div class="alert alert-success">{{ passwordSuccess }}</div>
              }
              @if (passwordError) {
                <div class="alert alert-danger">{{ passwordError }}</div>
              }

              <form [formGroup]="passwordForm" (ngSubmit)="onChangePassword()">
                <div class="form-group">
                  <label class="form-label" for="current_password">Current Password</label>
                  <input
                    id="current_password"
                    type="password"
                    class="form-input"
                    formControlName="current_password"
                    placeholder="Enter current password"
                  />
                </div>

                <div class="form-group">
                  <label class="form-label" for="new_password">New Password</label>
                  <input
                    id="new_password"
                    type="password"
                    class="form-input"
                    formControlName="new_password"
                    placeholder="Min. 8 characters with upper, lower, number, symbol"
                  />
                </div>

                <div class="form-group">
                  <label class="form-label" for="confirm_password">Confirm New Password</label>
                  <input
                    id="confirm_password"
                    type="password"
                    class="form-input"
                    formControlName="confirm_password"
                    placeholder="Re-enter new password"
                  />
                  @if (passwordForm.hasError('passwordMismatch') && passwordForm.get('confirm_password')?.touched) {
                    <div class="form-error">New passwords do not match.</div>
                  }
                </div>

                <button type="submit" class="btn btn-secondary" [disabled]="passwordForm.invalid || isChangingPassword">
                  @if (isChangingPassword) {
                    <span>Updating Password...</span>
                  } @else {
                    <span>Update Password</span>
                  }
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .profile-page {
      padding: 2.5rem 0 4rem 0;
      background-color: var(--bg-app);
    }
    .profile-container {
      max-width: 1000px;
    }
    .page-header {
      margin-bottom: 2rem;
    }
    .subtitle {
      color: var(--text-muted);
      font-size: 1.05rem;
    }
    .profile-layout {
      display: grid;
      grid-template-columns: 300px 1fr;
      gap: 2rem;
      align-items: start;
    }
    @media (max-width: 768px) {
      .profile-layout {
        grid-template-columns: 1fr;
      }
    }
    .identity-card {
      padding: 2rem;
      text-align: center;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .avatar-large {
      width: 72px;
      height: 72px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
      color: #ffffff;
      font-size: 1.75rem;
      font-weight: 800;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 1rem;
      box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);
    }
    .user-display-name {
      font-size: 1.3rem;
      margin-bottom: 0.25rem;
    }
    .user-email-text {
      font-size: 0.875rem;
      color: var(--text-muted);
      margin-bottom: 1rem;
    }
    .role-badge-container {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1.5rem;
    }
    .profile-metadata {
      width: 100%;
      padding-top: 1.25rem;
      border-top: 1px solid var(--border-light);
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      font-size: 0.85rem;
    }
    .meta-line {
      display: flex;
      justify-content: space-between;
    }
    .meta-label {
      color: var(--text-light);
    }
    .meta-val {
      font-weight: 600;
      color: var(--text-main);
    }
    .forms-column {
      display: flex;
      flex-direction: column;
      gap: 2rem;
    }
    .form-card {
      padding: 2rem;
    }
    .form-card h3 {
      font-size: 1.25rem;
      margin-bottom: 0.35rem;
    }
    .form-desc {
      font-size: 0.9rem;
      color: var(--text-muted);
      margin-bottom: 1.5rem;
    }
    .read-only-input {
      background-color: var(--bg-subtle) !important;
      cursor: not-allowed;
      color: var(--text-muted) !important;
    }
    .form-hint {
      display: block;
      margin-top: 0.35rem;
      font-size: 0.8rem;
      color: var(--text-light);
    }
  `]
})
export class ProfileComponent implements OnInit {
  user: User | null = null;
  profileForm: FormGroup;
  passwordForm: FormGroup;

  isSavingProfile = false;
  profileSuccess = '';
  profileError = '';

  isChangingPassword = false;
  passwordSuccess = '';
  passwordError = '';

  constructor(
    private auth: AuthService,
    private fb: FormBuilder
  ) {
    this.profileForm = this.fb.group({
      full_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(100)]]
    });

    this.passwordForm = this.fb.group({
      current_password: ['', [Validators.required]],
      new_password: ['', [Validators.required, Validators.minLength(8)]],
      confirm_password: ['', [Validators.required]]
    }, { validators: passwordMatchValidator });
  }

  ngOnInit(): void {
    this.user = this.auth.currentUser();
    if (this.user) {
      this.profileForm.patchValue({
        full_name: this.user.full_name
      });
    }

    // Refresh me from server
    this.auth.getMe().subscribe({
      next: (u) => {
        this.user = u;
        this.profileForm.patchValue({ full_name: u.full_name });
      }
    });
  }

  getInitials(name?: string): string {
    if (!name) return 'U';
    return name
      .split(' ')
      .map(part => part.charAt(0).toUpperCase())
      .slice(0, 2)
      .join('');
  }

  getRoleBadgeClass(role?: string): string {
    switch (role) {
      case 'admin': return 'badge-danger';
      case 'instructor': return 'badge-warning';
      default: return 'badge-primary';
    }
  }

  onSaveProfile(): void {
    if (this.profileForm.invalid) return;
    this.isSavingProfile = true;
    this.profileSuccess = '';
    this.profileError = '';

    this.auth.updateProfile({ full_name: this.profileForm.value.full_name }).subscribe({
      next: (updated) => {
        this.isSavingProfile = false;
        this.user = updated;
        this.profileSuccess = 'Profile successfully updated!';
      },
      error: (err) => {
        this.isSavingProfile = false;
        this.profileError = err.error?.detail || 'Failed to update profile.';
      }
    });
  }

  onChangePassword(): void {
    if (this.passwordForm.invalid) return;
    this.isChangingPassword = true;
    this.passwordSuccess = '';
    this.passwordError = '';

    const { current_password, new_password } = this.passwordForm.value;

    this.auth.changePassword({ current_password, new_password }).subscribe({
      next: (res) => {
        this.isChangingPassword = false;
        this.passwordSuccess = res.message || 'Password successfully updated!';
        this.passwordForm.reset();
      },
      error: (err) => {
        this.isChangingPassword = false;
        this.passwordError = err.error?.detail || 'Password change failed.';
      }
    });
  }
}

