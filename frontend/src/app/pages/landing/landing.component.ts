import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { CourseService } from '../../core/services/course.service';
import { Course } from '../../core/models/course.model';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="landing-page">
      <!-- Hero Section -->
      <section class="hero-section">
        <div class="container hero-container">
          <div class="hero-badge">
            <span class="pulse-dot"></span>
            <span>Next-Generation AI Learning Platform</span>
          </div>
          <h1 class="hero-title">
            Learn Smarter. Build Faster. <br/>
            Master Skills with <span class="gradient-text">EduVerse</span>
          </h1>
          <p class="hero-subtitle">
            An enterprise-grade Learning Management System powered by intelligent assistance,
            rigorous assessments, and seamless progress tracking.
          </p>

          <div class="hero-actions">
            <a routerLink="/courses" class="btn btn-primary btn-lg">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              Explore Course Catalog
            </a>
            @if (!auth.isAuthenticated()) {
              <a routerLink="/register" class="btn btn-secondary btn-lg">
                Create Free Account
              </a>
            } @else {
              <a routerLink="/student/dashboard" class="btn btn-secondary btn-lg">
                Go to My Learning
              </a>
            }
          </div>

          <!-- Quick Demo Accounts Helper -->
          <div class="demo-accounts-card">
            <div class="demo-header">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="16" x2="12" y2="12"/>
                <line x1="12" y1="8" x2="12.01" y2="8"/>
              </svg>
              <strong>Pre-Configured Demonstration Accounts</strong>
              <span class="password-hint">(Password: <code>EduVerseDemo2026!</code>)</span>
            </div>
            <div class="demo-pills">
              <a routerLink="/login" [queryParams]="{ role: 'student' }" class="demo-pill student">
                <span class="role-tag">Student</span>
                <span>alex.rivera&#64;eduverse.io</span>
              </a>
              <a routerLink="/login" [queryParams]="{ role: 'instructor' }" class="demo-pill instructor">
                <span class="role-tag">Instructor</span>
                <span>sarah.chen&#64;eduverse.io</span>
              </a>
              <a routerLink="/login" [queryParams]="{ role: 'admin' }" class="demo-pill admin">
                <span class="role-tag">Admin</span>
                <span>admin&#64;eduverse.io</span>
              </a>
            </div>
          </div>
        </div>
      </section>

      <!-- Key Features Section -->
      <section class="features-section">
        <div class="container">
          <div class="section-header text-center">
            <h2 class="section-title">Built for Real Academic & Engineering Mastery</h2>
            <p class="section-subtitle">Everything you need to deliver, learn, and evaluate technical curriculum.</p>
          </div>

          <div class="features-grid">
            <div class="feature-card card">
              <div class="feature-icon icon-indigo">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z"/>
                </svg>
              </div>
              <h3>AI Learning Assistant</h3>
              <p>On-demand conversational tutor that clarifies complex topics, debugs concepts, and provides contextual study prompts with instant local fallback.</p>
            </div>

            <div class="feature-card card">
              <div class="feature-icon icon-sky">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <line x1="16" y1="13" x2="8" y2="13"/>
                  <line x1="16" y1="17" x2="8" y2="17"/>
                  <polyline points="10 9 9 9 8 9"/>
                </svg>
              </div>
              <h3>Modular Lessons & Progress</h3>
              <p>Granular ordered lessons with student-level completion tracking, recalculating progress percentages dynamically across the curriculum.</p>
            </div>

            <div class="feature-card card">
              <div class="feature-icon icon-emerald">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="9 11 12 14 22 4"/>
                  <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                </svg>
              </div>
              <h3>Tamper-Proof Assessments</h3>
              <p>Zero answer leakage in public APIs. Server-side auto-grading verifies answers securely with post-submission review and historical attempt retention.</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Featured Courses Section -->
      <section class="featured-courses-section">
        <div class="container">
          <div class="section-header-row">
            <div>
              <h2 class="section-title">Popular Courses</h2>
              <p class="section-subtitle">Start mastering key full-stack and cloud disciplines today.</p>
            </div>
            <a routerLink="/courses" class="btn btn-outline">View All Courses →</a>
          </div>

          @if (loadingCourses) {
            <div class="loading-state">
              <div class="spinner"></div>
              <span>Loading courses...</span>
            </div>
          } @else if (featuredCourses.length > 0) {
            <div class="courses-grid">
              @for (course of featuredCourses; track course.id) {
                <div class="course-card card">
                  <div class="course-header">
                    <span class="badge badge-primary">{{ course.category }}</span>
                    <span class="badge" [ngClass]="getDifficultyBadge(course.difficulty)">
                      {{ course.difficulty }}
                    </span>
                  </div>
                  <h3 class="course-title">{{ course.title }}</h3>
                  <p class="course-desc">{{ course.description }}</p>
                  
                  <div class="course-meta">
                    <div class="meta-item">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                      </svg>
                      <span>{{ course.lesson_count }} Lessons</span>
                    </div>
                    <div class="meta-item">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                      </svg>
                      <span>{{ course.quiz_count }} Quizzes</span>
                    </div>
                  </div>

                  <div class="course-footer">
                    <div class="instructor-info">
                      <span class="inst-label">By</span>
                      <span class="inst-name">{{ course.instructor?.full_name || 'EduVerse Faculty' }}</span>
                    </div>
                    <a [routerLink]="['/courses', course.id]" class="btn btn-sm btn-primary">
                      View Syllabus
                    </a>
                  </div>
                </div>
              }
            </div>
          }
        </div>
      </section>
    </div>
  `,
  styles: [`
    .hero-section {
      padding: 5rem 0 4rem 0;
      background: linear-gradient(180deg, #ffffff 0%, var(--bg-app) 100%);
      text-align: center;
    }
    .hero-container {
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .hero-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background-color: var(--primary-light);
      color: var(--primary);
      padding: 0.35rem 0.85rem;
      border-radius: var(--radius-full);
      font-size: 0.85rem;
      font-weight: 700;
      margin-bottom: 1.5rem;
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      background-color: var(--primary);
      border-radius: 50%;
      box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.3);
    }
    .hero-title {
      font-size: 3.25rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.15;
      max-width: 850px;
      margin-bottom: 1.25rem;
    }
    @media (max-width: 768px) {
      .hero-title { font-size: 2.25rem; }
    }
    .gradient-text {
      background: linear-gradient(135deg, var(--primary) 0%, #0ea5e9 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .hero-subtitle {
      font-size: 1.2rem;
      color: var(--text-muted);
      max-width: 680px;
      margin-bottom: 2rem;
    }
    .hero-actions {
      display: flex;
      gap: 1rem;
      margin-bottom: 2.5rem;
    }
    .demo-accounts-card {
      background: #ffffff;
      border: 1px solid var(--primary-border);
      border-radius: var(--radius-lg);
      padding: 1.25rem 1.75rem;
      max-width: 780px;
      width: 100%;
      box-shadow: 0 10px 25px -5px rgba(79, 70, 229, 0.08);
    }
    .demo-header {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      font-size: 0.95rem;
      color: var(--text-main);
      margin-bottom: 1rem;
      flex-wrap: wrap;
    }
    .password-hint {
      color: var(--text-muted);
      font-size: 0.85rem;
    }
    .password-hint code {
      background-color: var(--bg-subtle);
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
      font-weight: 700;
      color: var(--primary);
    }
    .demo-pills {
      display: flex;
      justify-content: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .demo-pill {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 0.85rem;
      border-radius: var(--radius-md);
      font-size: 0.85rem;
      font-weight: 600;
      text-decoration: none;
      transition: var(--transition);
      border: 1px solid transparent;
    }
    .demo-pill.student {
      background-color: #eef2ff;
      color: #3730a3;
      border-color: #c7d2fe;
    }
    .demo-pill.instructor {
      background-color: #fef3c7;
      color: #92400e;
      border-color: #fde68a;
    }
    .demo-pill.admin {
      background-color: #fee2e2;
      color: #991b1b;
      border-color: #fecaca;
    }
    .demo-pill:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-sm);
    }
    .role-tag {
      font-weight: 800;
      text-transform: uppercase;
      font-size: 0.7rem;
      letter-spacing: 0.05em;
    }
    .features-section {
      padding: 5rem 0;
      background-color: var(--bg-card);
    }
    .section-title {
      font-size: 2rem;
      margin-bottom: 0.5rem;
    }
    .section-subtitle {
      color: var(--text-muted);
      font-size: 1.05rem;
      margin-bottom: 3rem;
    }
    .text-center { text-align: center; }
    .features-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 2rem;
    }
    .feature-card {
      padding: 2rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .feature-icon {
      width: 48px;
      height: 48px;
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .icon-indigo { background-color: var(--primary-light); color: var(--primary); }
    .icon-sky { background-color: var(--accent-light); color: #0284c7; }
    .icon-emerald { background-color: var(--success-light); color: #059669; }
    .feature-card h3 { font-size: 1.25rem; }
    .feature-card p { color: var(--text-muted); font-size: 0.95rem; line-height: 1.6; }
    .featured-courses-section {
      padding: 5rem 0;
      background-color: var(--bg-app);
    }
    .section-header-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 2.5rem;
    }
    .courses-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 2rem;
    }
    .course-card {
      display: flex;
      flex-direction: column;
      height: 100%;
    }
    .course-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 1rem;
    }
    .course-title {
      font-size: 1.2rem;
      margin-bottom: 0.6rem;
    }
    .course-desc {
      color: var(--text-muted);
      font-size: 0.9rem;
      line-height: 1.5;
      flex: 1 0 auto;
      margin-bottom: 1.25rem;
    }
    .course-meta {
      display: flex;
      gap: 1.25rem;
      padding: 0.75rem 0;
      border-top: 1px solid var(--border-light);
      border-bottom: 1px solid var(--border-light);
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-bottom: 1.25rem;
    }
    .meta-item {
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .course-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .instructor-info {
      display: flex;
      flex-direction: column;
    }
    .inst-label { font-size: 0.75rem; color: var(--text-light); }
    .inst-name { font-size: 0.85rem; font-weight: 600; color: var(--text-main); }
    .loading-state {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
      padding: 3rem;
      color: var(--text-muted);
    }
    .spinner {
      width: 24px;
      height: 24px;
      border: 3px solid var(--border-color);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  `]
})
export class LandingComponent implements OnInit {
  featuredCourses: Course[] = [];
  loadingCourses = true;

  constructor(
    public auth: AuthService,
    private courseService: CourseService
  ) {}

  ngOnInit(): void {
    this.courseService.getCourses({ limit: 3 }).subscribe({
      next: (courses) => {
        this.featuredCourses = courses;
        this.loadingCourses = false;
      },
      error: () => {
        this.loadingCourses = false;
      }
    });
  }

  getDifficultyBadge(diff: string): string {
    switch (diff) {
      case 'beginner': return 'badge-success';
      case 'intermediate': return 'badge-warning';
      case 'advanced': return 'badge-danger';
      default: return 'badge-neutral';
    }
  }
}

