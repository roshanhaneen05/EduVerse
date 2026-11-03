import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

export type PortalType = 'student' | 'instructor' | 'admin';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="light-login-page">
      <!-- Ambient Decorative Curved Waves in Background -->
      <div class="bg-decorative-waves" aria-hidden="true">
        <svg class="corner-wave top-right-wave" viewBox="0 0 500 500" fill="none">
          <path d="M500,0 C380,80 320,220 500,380 L500,0 Z" fill="rgba(196, 181, 253, 0.45)"/>
        </svg>
        <svg class="corner-wave bottom-left-wave" viewBox="0 0 500 500" fill="none">
          <path d="M0,500 C140,420 180,300 0,160 L0,500 Z" fill="rgba(196, 181, 253, 0.5)"/>
        </svg>
      </div>

      <!-- Top Navigation Header -->
      <header class="top-nav-header">
        <div class="header-brand">
          <div class="brand-cap-wrap">
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
              <path d="M16 4L2 11L16 18L30 11L16 4Z" fill="#4f46e5"/>
              <path d="M6 14.5V21C6 24.5 10.5 27.5 16 27.5C21.5 27.5 26 24.5 26 21V14.5" stroke="#4f46e5" stroke-width="2.5" stroke-linecap="round"/>
              <path d="M30 11V21M30 21L28 19M30 21L32 19" stroke="#4f46e5" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <span class="header-brand-name">EduVerse</span>
        </div>

        <nav class="header-nav-links">
          <a routerLink="/courses" class="nav-item">Courses</a>
          <a class="nav-item" (click)="onNavClick('about')">About</a>
          <a class="nav-item" (click)="onNavClick('support')">Support</a>
        </nav>
      </header>

      <!-- Main Split Content Area -->
      <main class="page-body-grid">
        <!-- Left Hero Area -->
        <div class="hero-left-column">
          <!-- LMS Pill Badge -->
          <div class="lms-pill-badge">
            <svg width="15" height="15" viewBox="0 0 32 32" fill="none">
              <path d="M16 4L2 11L16 18L30 11L16 4Z" fill="#6d28d9"/>
              <path d="M6 14.5V21C6 24.5 10.5 27.5 16 27.5C21.5 27.5 26 24.5 26 21V14.5" stroke="#6d28d9" stroke-width="2.5" stroke-linecap="round"/>
            </svg>
            <span>Learning Management System</span>
          </div>

          <!-- Main Hero Headline -->
          <h1 class="main-hero-heading">
            A Smarter Way to<br/>
            <span class="gradient-accent-text">
              Learn & Grow
              <svg class="swoosh-underline" width="175" height="12" viewBox="0 0 175 12" fill="none">
                <path d="M3 9C55 3 120 3 172 9" stroke="#6366f1" stroke-width="4" stroke-linecap="round"/>
              </svg>
            </span>
          </h1>

          <!-- Tagline Subtitle -->
          <p class="hero-subtitle">
            Access courses, track your progress, submit assignments, and learn anytime, anywhere with EduVerse.
          </p>

          <!-- Middle-Bottom Interactive Row: 3 Feature Cards on Left + Desk Laptop Artwork on Right -->
          <div class="features-and-desk-row">
            <!-- 3 Vertical Feature Cards -->
            <div class="feature-cards-stack">
              <div class="feature-item-card">
                <div class="card-icon-box">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                  </svg>
                </div>
                <div class="card-text-col">
                  <div class="feature-card-title">Interactive Courses</div>
                  <div class="feature-card-sub">Engaging and structured learning</div>
                </div>
              </div>

              <div class="feature-item-card">
                <div class="card-icon-box">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 20V10M12 20V4M6 20v-6"/>
                  </svg>
                </div>
                <div class="card-text-col">
                  <div class="feature-card-title">Track Progress</div>
                  <div class="feature-card-sub">Monitor your performance</div>
                </div>
              </div>

              <div class="feature-item-card">
                <div class="card-icon-box">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <path d="M22 21v-2a4 4 0 0 0-3-3.87"/>
                    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                  </svg>
                </div>
                <div class="card-text-col">
                  <div class="feature-card-title">Learn Together</div>
                  <div class="feature-card-sub">Connect with instructors and peers</div>
                </div>
              </div>
            </div>

            <!-- Modern 3D Educational Artwork -->
            <div class="hero-artwork-box">
              <img
                src="/assets/images/learning-hero-illustration.png"
                alt="EduVerse Learning Hub"
                class="hero-artwork-img"
              />
            </div>
          </div>
        </div>

        <!-- Right Login Card Area -->
        <div class="form-right-column">
          <div class="login-auth-card">
            <!-- Brand Header -->
            <div class="card-brand-center">
              <div class="card-logo-row">
                <div class="card-cap-wrap">
                  <svg width="30" height="30" viewBox="0 0 32 32" fill="none">
                    <path d="M16 4L2 11L16 18L30 11L16 4Z" fill="#4f46e5"/>
                    <path d="M6 14.5V21C6 24.5 10.5 27.5 16 27.5C21.5 27.5 26 24.5 26 21V14.5" stroke="#4f46e5" stroke-width="2.5" stroke-linecap="round"/>
                    <path d="M30 11V21M30 21L28 19M30 21L32 19" stroke="#4f46e5" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
                <span class="card-brand-title">EduVerse</span>
              </div>
              <h2 class="card-welcome-title">Welcome Back</h2>
              <p class="card-welcome-sub">Sign in to your EduVerse account</p>
            </div>

            <!-- Role Selector Tabs -->
            <div class="card-role-track" role="tablist">
              <button
                type="button"
                class="role-pill-btn"
                [class.active]="selectedRole === 'student'"
                (click)="selectRole('student')"
                role="tab"
                [attr.aria-selected]="selectedRole === 'student'"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
                  <path d="M6 12v5c3 3 9 3 12 0v-5"/>
                </svg>
                <span>Student</span>
              </button>

              <button
                type="button"
                class="role-pill-btn"
                [class.active]="selectedRole === 'instructor'"
                (click)="selectRole('instructor')"
                role="tab"
                [attr.aria-selected]="selectedRole === 'instructor'"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
                  <circle cx="9" cy="7" r="4"/>
                  <line x1="19" y1="8" x2="19" y2="14"/>
                  <line x1="22" y1="11" x2="16" y2="11"/>
                </svg>
                <span>Instructor</span>
              </button>

              <button
                type="button"
                class="role-pill-btn"
                [class.active]="selectedRole === 'admin'"
                (click)="selectRole('admin')"
                role="tab"
                [attr.aria-selected]="selectedRole === 'admin'"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect width="20" height="14" x="2" y="3" rx="2"/>
                  <line x1="8" x2="16" y1="21" y2="21"/>
                  <line x1="12" x2="12" y1="17" y2="21"/>
                </svg>
                <span>Admin</span>
              </button>
            </div>

            <!-- Error or Info Alert -->
            @if (errorMessage) {
              <div class="card-message alert-danger">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <span>{{ errorMessage }}</span>
              </div>
            }

            @if (infoNotice) {
              <div class="card-message alert-info">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="16" x2="12" y2="12"/>
                  <line x1="12" y1="8" x2="12.01" y2="8"/>
                </svg>
                <span>{{ infoNotice }}</span>
              </div>
            }

            <!-- Form -->
            <form [formGroup]="loginForm" (ngSubmit)="onSubmit()" class="login-inputs-form">
              <!-- Email Address -->
              <div class="field-wrapper">
                <div class="field-title-row">
                  <svg class="field-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect width="20" height="16" x="2" y="4" rx="2"/>
                    <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
                  </svg>
                  <label for="email" class="field-label-text">Email Address</label>
                </div>
                <input
                  id="email"
                  type="email"
                  class="field-input"
                  formControlName="email"
                  placeholder="Enter your email address"
                  [class.has-error]="isFieldInvalid('email')"
                  autocomplete="email"
                />
                @if (isFieldInvalid('email')) {
                  <div class="validation-error">Please enter a valid email address.</div>
                }
              </div>

              <!-- Password -->
              <div class="field-wrapper">
                <div class="password-top-line">
                  <div class="field-title-row">
                    <svg class="field-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                    <label for="password" class="field-label-text">Password</label>
                  </div>
                  <a class="forgot-link-text" (click)="onForgotPassword($event)">Forgot Password?</a>
                </div>
                <div class="password-box">
                  <input
                    id="password"
                    [type]="showPassword ? 'text' : 'password'"
                    class="field-input with-toggle"
                    formControlName="password"
                    placeholder="Enter your password"
                    [class.has-error]="isFieldInvalid('password')"
                    autocomplete="current-password"
                  />
                  <button
                    type="button"
                    class="eye-toggle-button"
                    (click)="showPassword = !showPassword"
                    [attr.aria-label]="showPassword ? 'Hide password' : 'Show password'"
                  >
                    @if (showPassword) {
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>
                        <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/>
                        <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/>
                        <line x1="2" x2="22" y1="2" y2="22"/>
                      </svg>
                    } @else {
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
                        <circle cx="12" cy="12" r="3"/>
                      </svg>
                    }
                  </button>
                </div>
                @if (isFieldInvalid('password')) {
                  <div class="validation-error">Password is required.</div>
                }
              </div>

              <!-- Sign In Button -->
              <button
                type="submit"
                class="signin-purple-btn"
                [disabled]="loginForm.invalid || isLoading"
              >
                @if (isLoading) {
                  <div class="btn-spinner"></div>
                  <span>Signing In...</span>
                } @else {
                  <span>Sign In</span>
                  <span class="arrow-circle">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M5 12h14"/>
                      <path d="m12 5 7 7-7 7"/>
                    </svg>
                  </span>
                }
              </button>
            </form>

            <!-- Line Divider -->
            <div class="card-divider-line">
              <span class="divider-caption">New to EduVerse?</span>
            </div>

            <!-- Create Account Button -->
            <a routerLink="/register" class="create-account-pill-btn">
              Create Account
            </a>
          </div>
        </div>
      </main>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      width: 100vw;
      min-height: 100vh;
      overflow-x: hidden;
    }

    .light-login-page {
      position: relative;
      min-height: 100vh;
      width: 100vw;
      background: linear-gradient(135deg, #fbfaff 0%, #f6f3fe 50%, #ede8fc 100%);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      font-family: inherit;
    }

    /* Ambient Corner Waves matching the image exactly */
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

    /* Top Navigation Header */
    .top-nav-header {
      position: relative;
      z-index: 10;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1.5rem 3.5rem 0.5rem 3.5rem;
    }
    .header-brand {
      display: flex;
      align-items: center;
      gap: 0.65rem;
    }
    .brand-cap-wrap {
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .header-brand-name {
      font-size: 1.55rem;
      font-weight: 800;
      color: #1e1b4b;
      letter-spacing: -0.02em;
    }
    .header-nav-links {
      display: flex;
      align-items: center;
      gap: 2.25rem;
    }
    .nav-item {
      font-size: 0.95rem;
      font-weight: 600;
      color: #334155;
      text-decoration: none;
      cursor: pointer;
      transition: color 0.15s ease;
    }
    .nav-item:hover {
      color: #4f46e5;
    }

    /* Main Split Content Area */
    .page-body-grid {
      position: relative;
      z-index: 5;
      flex: 1;
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      align-items: center;
      padding: 1.5rem 3.5rem 2.5rem 3.5rem;
      gap: 2.5rem;
      max-width: 1440px;
      margin: 0 auto;
      width: 100%;
      box-sizing: border-box;
    }

    /* Left Hero Column */
    .hero-left-column {
      display: flex;
      flex-direction: column;
      justify-content: center;
    }

    .lms-pill-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.4rem 1.05rem;
      background: #ede9fe;
      border: 1px solid #ddd6fe;
      border-radius: 9999px;
      color: #6d28d9;
      font-size: 0.825rem;
      font-weight: 600;
      letter-spacing: 0.01em;
      margin-bottom: 1.35rem;
      align-self: flex-start;
      box-shadow: 0 2px 6px rgba(109, 40, 217, 0.08);
    }

    .main-hero-heading {
      font-size: 3.25rem;
      font-weight: 800;
      line-height: 1.15;
      color: #0f172a;
      letter-spacing: -0.03em;
      margin: 0 0 1.25rem 0;
    }

    .gradient-accent-text {
      color: #4f46e5;
      position: relative;
      display: inline-block;
    }
    .swoosh-underline {
      position: absolute;
      bottom: -6px;
      left: 0;
      pointer-events: none;
    }

    .hero-subtitle {
      font-size: 1rem;
      color: #475569;
      line-height: 1.6;
      max-width: 440px;
      margin: 0 0 2rem 0;
      font-weight: 400;
    }

    /* Row with 3 Feature Cards and Desk Artwork */
    .features-and-desk-row {
      display: flex;
      align-items: flex-end;
      gap: 1.5rem;
      position: relative;
    }

    .feature-cards-stack {
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
      flex-shrink: 0;
      z-index: 2;
    }

    .feature-item-card {
      display: flex;
      align-items: center;
      gap: 0.85rem;
      padding: 0.65rem 0.95rem;
      background: rgba(255, 255, 255, 0.75);
      border: 1px solid rgba(226, 232, 240, 0.9);
      border-radius: 14px;
      backdrop-filter: blur(8px);
      box-shadow: 0 4px 14px rgba(99, 102, 241, 0.06);
      width: 275px;
      transition: all 0.2s ease;
    }
    .feature-item-card:hover {
      background: #ffffff;
      transform: translateY(-2px);
      box-shadow: 0 6px 18px rgba(99, 102, 241, 0.12);
    }
    .card-icon-box {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      background: #ffffff;
      border: 1px solid #e0e7ff;
      box-shadow: 0 2px 6px rgba(99, 102, 241, 0.12);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .card-text-col {
      display: flex;
      flex-direction: column;
    }
    .feature-card-title {
      font-size: 0.875rem;
      font-weight: 700;
      color: #0f172a;
      line-height: 1.25;
    }
    .feature-card-sub {
      font-size: 0.75rem;
      color: #64748b;
      margin-top: 0.15rem;
      line-height: 1.3;
    }

    /* 3D Education Artwork */
    .hero-artwork-box {
      position: relative;
      flex: 1;
      max-width: 320px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .hero-artwork-img {
      width: 100%;
      height: auto;
      max-height: 250px;
      object-fit: cover;
      border-radius: 20px;
      box-shadow: 0 16px 36px -10px rgba(99, 102, 241, 0.22), 0 0 1px 1px rgba(99, 102, 241, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.9);
      transition: all 0.3s ease;
    }
    .hero-artwork-img:hover {
      transform: translateY(-3px) scale(1.01);
      box-shadow: 0 20px 42px -10px rgba(99, 102, 241, 0.3);
    }

    /* Right Login Card Column */
    .form-right-column {
      display: flex;
      justify-content: center;
      align-items: center;
    }

    .login-auth-card {
      background: #ffffff;
      border-radius: 28px;
      width: 100%;
      max-width: 440px;
      padding: 2.35rem 2.4rem 2.2rem 2.4rem;
      box-shadow: 0 25px 60px -15px rgba(99, 102, 241, 0.16), 0 0 1px 1px rgba(0, 0, 0, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.9);
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
    }

    .card-brand-center {
      text-align: center;
      margin-bottom: 1.35rem;
    }
    .card-logo-row {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.55rem;
      margin-bottom: 0.8rem;
    }
    .card-cap-wrap {
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .card-brand-title {
      font-size: 1.55rem;
      font-weight: 800;
      color: #1e1b4b;
      letter-spacing: -0.02em;
    }
    .card-welcome-title {
      font-size: 1.65rem;
      font-weight: 800;
      color: #0f172a;
      margin: 0 0 0.35rem 0;
      letter-spacing: -0.02em;
    }
    .card-welcome-sub {
      font-size: 0.85rem;
      color: #64748b;
      margin: 0;
    }

    /* Role Tabs */
    .card-role-track {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 4px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 4px;
      margin-bottom: 1.35rem;
    }
    .role-pill-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
      padding: 0.55rem 0.35rem;
      border-radius: 8px;
      border: none;
      background: transparent;
      color: #475569;
      font-size: 0.825rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .role-pill-btn:hover:not(.active) {
      color: #0f172a;
      background-color: #f1f5f9;
    }
    .role-pill-btn.active {
      background: #4f46e5;
      color: #ffffff;
      font-weight: 600;
      box-shadow: 0 2px 8px rgba(79, 70, 229, 0.28);
    }

    /* Alerts */
    .card-message {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.65rem 0.85rem;
      border-radius: 10px;
      font-size: 0.8rem;
      margin-bottom: 1.15rem;
    }
    .alert-danger {
      background-color: #fee2e2;
      color: #991b1b;
      border: 1px solid #fecaca;
    }
    .alert-info {
      background-color: #e0f2fe;
      color: #0369a1;
      border: 1px solid #bae6fd;
    }

    /* Form Fields */
    .login-inputs-form {
      display: flex;
      flex-direction: column;
      gap: 1.1rem;
    }
    .field-wrapper {
      display: flex;
      flex-direction: column;
    }
    .field-title-row {
      display: flex;
      align-items: center;
      gap: 0.45rem;
      margin-bottom: 0.45rem;
      color: #0f172a;
    }
    .field-icon {
      color: #334155;
    }
    .field-label-text {
      font-size: 0.825rem;
      font-weight: 700;
      color: #0f172a;
      margin: 0;
      cursor: pointer;
    }
    .password-top-line {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 0.45rem;
    }
    .forgot-link-text {
      color: #4f46e5;
      font-size: 0.8rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
    }
    .forgot-link-text:hover {
      text-decoration: underline;
    }

    .field-input {
      width: 100%;
      height: 42px;
      padding: 0 0.95rem;
      border: 1px solid #d1d5db;
      border-radius: 10px;
      font-size: 0.875rem;
      color: #0f172a;
      background-color: #ffffff;
      transition: border-color 0.15s, box-shadow 0.15s;
      box-sizing: border-box;
      outline: none;
    }
    .field-input::placeholder {
      color: #9ca3af;
      font-size: 0.85rem;
    }
    .field-input:focus {
      border-color: #4f46e5;
      box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
    }
    .field-input.has-error {
      border-color: #ef4444;
    }
    .validation-error {
      color: #ef4444;
      font-size: 0.75rem;
      margin-top: 0.3rem;
      font-weight: 500;
    }

    .password-box {
      position: relative;
      display: flex;
      align-items: center;
    }
    .field-input.with-toggle {
      padding-right: 2.75rem;
    }
    .eye-toggle-button {
      position: absolute;
      right: 8px;
      background: none;
      border: none;
      padding: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      color: #64748b;
      border-radius: 6px;
      transition: color 0.15s;
    }
    .eye-toggle-button:hover {
      color: #0f172a;
    }

    /* Submit Button */
    .signin-purple-btn {
      width: 100%;
      height: 46px;
      margin-top: 0.35rem;
      background: #4f46e5;
      color: #ffffff;
      border: none;
      border-radius: 12px;
      font-size: 0.95rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.55rem;
      cursor: pointer;
      box-shadow: 0 4px 14px rgba(79, 70, 229, 0.28);
      transition: all 0.2s ease;
    }
    .signin-purple-btn:hover:not(:disabled) {
      background: #4338ca;
      transform: translateY(-1px);
      box-shadow: 0 6px 18px rgba(79, 70, 229, 0.36);
    }
    .signin-purple-btn:disabled {
      opacity: 0.65;
      cursor: not-allowed;
      transform: none;
    }
    .arrow-circle {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.22);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .btn-spinner {
      width: 16px;
      height: 16px;
      border: 2px solid #ffffff;
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    /* Divider */
    .card-divider-line {
      display: flex;
      align-items: center;
      text-align: center;
      margin: 1.35rem 0 1rem 0;
    }
    .card-divider-line::before,
    .card-divider-line::after {
      content: '';
      flex: 1;
      border-bottom: 1px solid #e2e8f0;
    }
    .divider-caption {
      padding: 0 0.85rem;
      font-size: 0.8rem;
      color: #64748b;
      font-weight: 500;
    }

    /* Create Account Button */
    .create-account-pill-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 42px;
      border-radius: 12px;
      border: 1.5px solid #4f46e5;
      background: #ffffff;
      color: #4338ca;
      font-weight: 700;
      font-size: 0.875rem;
      text-decoration: none;
      transition: all 0.2s ease;
      box-sizing: border-box;
    }
    .create-account-pill-btn:hover {
      background-color: #f5f3ff;
      border-color: #4338ca;
    }

    /* Responsive Design */
    @media (max-width: 1100px) {
      .top-nav-header {
        padding: 1.25rem 2rem 0.5rem 2rem;
      }
      .page-body-grid {
        padding: 1rem 2rem 2rem 2rem;
        gap: 2rem;
      }
      .main-hero-heading {
        font-size: 2.75rem;
      }
    }

    @media (max-width: 900px) {
      .page-body-grid {
        grid-template-columns: 1fr;
      }
      .features-and-desk-row {
        flex-direction: column;
        align-items: flex-start;
      }
      .hero-artwork-box {
        max-width: 260px;
        align-self: center;
      }
    }
  `]
})
export class LoginComponent implements OnInit {
  loginForm: FormGroup;
  selectedRole: PortalType = 'student';
  showPassword = false;
  isLoading = false;
  errorMessage = '';
  infoNotice = '';
  returnUrl = '';

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router,
    private route: ActivatedRoute
  ) {
    this.loginForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required]]
    });
  }

  ngOnInit(): void {
    this.returnUrl = this.route.snapshot.queryParams['returnUrl'] || '';
    const roleParam = this.route.snapshot.queryParams['role'] || this.route.snapshot.queryParams['portal'];
    if (roleParam === 'instructor' || roleParam === 'admin' || roleParam === 'student') {
      this.selectedRole = roleParam;
    }
  }

  selectRole(role: PortalType): void {
    this.selectedRole = role;
    this.errorMessage = '';
    this.infoNotice = '';
  }

  isFieldInvalid(field: string): boolean {
    const control = this.loginForm.get(field);
    return !!(control && control.invalid && (control.dirty || control.touched));
  }

  onForgotPassword(event: Event): void {
    event.preventDefault();
    this.infoNotice = 'To reset your credentials, please contact your institution platform administrator or email support@eduverse.io.';
  }

  onNavClick(target: string): void {
    if (target === 'about') {
      this.infoNotice = 'EduVerse LMS is an enterprise learning management platform built for modern academic and technical training.';
    } else if (target === 'support') {
      this.infoNotice = 'For support and technical assistance, please reach out to support@eduverse.io.';
    }
  }

  onSubmit(): void {
    if (this.loginForm.invalid) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.infoNotice = '';

    const credentials = {
      email: this.loginForm.value.email.trim(),
      password: this.loginForm.value.password
    };

    this.auth.login(credentials).subscribe({
      next: (res) => {
        this.isLoading = false;
        const userRole = res.user.role;

        if (this.returnUrl) {
          this.router.navigateByUrl(this.returnUrl);
          return;
        }

        // Direct routing based on selected role and user role
        if (this.selectedRole === 'admin') {
          if (userRole === 'admin') {
            this.router.navigate(['/admin/dashboard']);
          } else {
            this.router.navigate([userRole === 'instructor' ? '/instructor/dashboard' : '/student/dashboard']);
          }
        } else if (this.selectedRole === 'instructor') {
          if (userRole === 'instructor' || userRole === 'admin') {
            this.router.navigate(['/instructor/dashboard']);
          } else {
            this.router.navigate(['/student/dashboard']);
          }
        } else {
          // Student role
          if (userRole === 'admin') {
            this.router.navigate(['/admin/dashboard']);
          } else if (userRole === 'instructor') {
            this.router.navigate(['/instructor/dashboard']);
          } else {
            this.router.navigate(['/student/dashboard']);
          }
        }
      },
      error: (err) => {
        this.isLoading = false;
        if (err.status === 0) {
          this.errorMessage = 'Unable to connect to the EduVerse backend server. Please verify backend is running at http://127.0.0.1:8000.';
        } else {
          this.errorMessage = err.error?.detail || 'Invalid email or password. Please verify your credentials and try again.';
        }
      }
    });
  }
}
