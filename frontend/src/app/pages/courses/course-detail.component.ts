import { Component, OnInit, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { CourseService } from '../../core/services/course.service';
import { MaterialService } from '../../core/services/material.service';
import { CourseDetail } from '../../core/models/course.model';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-course-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="course-detail-page">
      @if (isLoading) {
        <div class="loading-state">
          <div class="spinner"></div>
          <span>Loading course syllabus...</span>
        </div>
      } @else if (!course) {
        <div class="container not-found card">
          <h2>Course Not Found</h2>
          <p>The requested course does not exist or may have been unpublished.</p>
          <a routerLink="/courses" class="btn btn-primary">Back to Catalog</a>
        </div>
      } @else {
        <!-- Course Hero -->
        <section class="course-hero">
          <div class="container hero-content">
            <div class="hero-main">
              <div class="badges-row">
                <span class="badge badge-primary">{{ course.category }}</span>
                <span class="badge" [ngClass]="getDifficultyBadge(course.difficulty)">
                  {{ course.difficulty }}
                </span>
              </div>
              <h1 class="course-title">{{ course.title }}</h1>
              <p class="course-description">{{ course.description }}</p>

              <div class="meta-pills">
                <div class="meta-pill">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                  </svg>
                  <span>{{ course.lessons.length }} Modular Lessons</span>
                </div>
                <div class="meta-pill">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  <span>{{ course.quizzes.length }} Graded Assessments</span>
                </div>
                <div class="meta-pill">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                  </svg>
                  <span>{{ course.enrollment_count }} Enrolled Students</span>
                </div>
              </div>
            </div>

            <!-- Enrollment / Action Card -->
            <div class="hero-action-card card">
              <div class="action-card-header">
                <h3>Course Status</h3>
                @if (course.is_enrolled) {
                  <span class="badge badge-success">Enrolled</span>
                }
              </div>

              @if (course.is_enrolled) {
                <div class="progress-box">
                  <div class="progress-header">
                    <span>Your Learning Progress</span>
                    <span class="progress-val">{{ course.user_progress_percentage || 0 }}%</span>
                  </div>
                  <div class="progress-bar-container">
                    <div class="progress-bar-fill" [style.width.%]="course.user_progress_percentage || 0"></div>
                  </div>
                </div>

                @if (course.lessons.length > 0) {
                  <a [routerLink]="['/courses', course.id, 'learn', getTargetLessonId()]" class="btn btn-primary btn-block btn-lg">
                    Continue Learning →
                  </a>
                }
                <div class="enrolled-quick-actions">
                  <a [routerLink]="['/courses', course.id, 'announcements']" class="quick-action-link">
                    📢 Announcements
                  </a>
                  <span class="quick-action-dot">·</span>
                  <a [routerLink]="['/courses', course.id, 'discussions']" class="quick-action-link">
                    💬 Discussions
                  </a>
                </div>
              } @else {
                <p class="enroll-perk">
                  Gain lifetime access to all lessons, interactive knowledge checks, and verifiable completion certificates.
                </p>

                @if (enrollMessage) {
                  <div class="alert" [ngClass]="isEnrollError ? 'alert-danger' : 'alert-success'">
                    {{ enrollMessage }}
                  </div>
                }

                @if (auth.isAuthenticated()) {
                  <button (click)="enroll()" class="btn btn-primary btn-block btn-lg" [disabled]="isEnrolling">
                    @if (isEnrolling) {
                      <span>Enrolling...</span>
                    } @else {
                      <span>Enroll in Course</span>
                    }
                  </button>
                } @else {
                  <a [routerLink]="['/login']" [queryParams]="{ returnUrl: '/courses/' + course.id }" class="btn btn-primary btn-block btn-lg">
                    Sign In to Enroll
                  </a>
                }
              }

              <div class="instructor-preview">
                <span class="instructor-title">Instructor</span>
                <div class="instructor-name">{{ course.instructor?.full_name || 'EduVerse Faculty' }}</div>
                <div class="instructor-email">{{ course.instructor?.email }}</div>
              </div>
            </div>
          </div>
        </section>

        <!-- Course Curriculum Section -->
        <section class="curriculum-section">
          <div class="container">
            <div class="curriculum-layout">
              <!-- Lessons Column -->
              <div class="curriculum-main">
                <div class="section-title-bar">
                  <h2>Curriculum Syllabus</h2>
                  <span class="badge badge-neutral">{{ course.lessons.length }} Lessons</span>
                </div>

                @if (course.lessons.length === 0) {
                  <div class="empty-curriculum card">
                    <p>Lessons for this course are currently being finalized by the instructor.</p>
                  </div>
                } @else if (hasSections()) {
                  <div class="curriculum-sections-flow">
                    @for (sec of course.sections; track sec.id) {
                      <div class="syllabus-section-block">
                        <div class="syllabus-section-header">
                          <span class="sec-pill">Section {{ sec.order_index }}</span>
                          <div class="sec-title-group">
                            <h3 class="syllabus-section-title">{{ sec.title }}</h3>
                            @if (sec.description) {
                              <p class="syllabus-section-desc">{{ sec.description }}</p>
                            }
                          </div>
                        </div>

                        <div class="lessons-list">
                          @for (lesson of getLessonsForSection(sec.id); track lesson.id) {
                            <div class="lesson-row card" [class.completed]="lesson.is_completed">
                              <div class="lesson-left">
                                <div class="lesson-number">{{ lesson.order_index }}</div>
                                <div class="lesson-info">
                                  <h4 class="lesson-title">{{ lesson.title }}</h4>
                                  <span class="lesson-status">
                                    @if (lesson.is_completed) {
                                      <span class="status-completed">✓ Completed</span>
                                    } @else {
                                      <span>Interactive Reading & Code</span>
                                    }
                                  </span>
                                </div>
                              </div>

                              <div class="lesson-right">
                                @if (course.is_enrolled) {
                                  <a [routerLink]="['/courses', course.id, 'learn', lesson.id]" class="btn btn-sm btn-outline">
                                    Start Lesson
                                  </a>
                                } @else {
                                  <span class="locked-badge" title="Enroll to unlock lesson content">🔒 Locked</span>
                                }
                              </div>
                            </div>
                          }
                        </div>
                      </div>
                    }

                    @if (getUncategorizedLessons().length > 0) {
                      <div class="syllabus-section-block">
                        <div class="syllabus-section-header">
                          <span class="sec-pill sec-pill-subtle">📌 Additional</span>
                          <h3 class="syllabus-section-title">General Curriculum Lessons</h3>
                        </div>

                        <div class="lessons-list">
                          @for (lesson of getUncategorizedLessons(); track lesson.id) {
                            <div class="lesson-row card" [class.completed]="lesson.is_completed">
                              <div class="lesson-left">
                                <div class="lesson-number">{{ lesson.order_index }}</div>
                                <div class="lesson-info">
                                  <h4 class="lesson-title">{{ lesson.title }}</h4>
                                  <span class="lesson-status">
                                    @if (lesson.is_completed) {
                                      <span class="status-completed">✓ Completed</span>
                                    } @else {
                                      <span>Interactive Reading & Code</span>
                                    }
                                  </span>
                                </div>
                              </div>

                              <div class="lesson-right">
                                @if (course.is_enrolled) {
                                  <a [routerLink]="['/courses', course.id, 'learn', lesson.id]" class="btn btn-sm btn-outline">
                                    Start Lesson
                                  </a>
                                } @else {
                                  <span class="locked-badge" title="Enroll to unlock lesson content">🔒 Locked</span>
                                }
                              </div>
                            </div>
                          }
                        </div>
                      </div>
                    }
                  </div>
                } @else {
                  <div class="lessons-list">
                    @for (lesson of course.lessons; track lesson.id) {
                      <div class="lesson-row card" [class.completed]="lesson.is_completed">
                        <div class="lesson-left">
                          <div class="lesson-number">{{ lesson.order_index }}</div>
                          <div class="lesson-info">
                            <h4 class="lesson-title">{{ lesson.title }}</h4>
                            <span class="lesson-status">
                              @if (lesson.is_completed) {
                                <span class="status-completed">✓ Completed</span>
                              } @else {
                                <span>Interactive Reading & Code</span>
                              }
                            </span>
                          </div>
                        </div>

                        <div class="lesson-right">
                          @if (course.is_enrolled) {
                            <a [routerLink]="['/courses', course.id, 'learn', lesson.id]" class="btn btn-sm btn-outline">
                              Start Lesson
                            </a>
                          } @else {
                            <span class="locked-badge" title="Enroll to unlock lesson content">🔒 Locked</span>
                          }
                        </div>
                      </div>
                    }
                  </div>
                }

                <!-- Quizzes Section -->
                <div class="section-title-bar quizzes-title-bar">
                  <h2>Knowledge Assessments</h2>
                  <span class="badge badge-neutral">{{ course.quizzes.length }} Quizzes</span>
                </div>

                @if (course.quizzes.length === 0) {
                  <div class="empty-curriculum card">
                    <p>No formal quizzes scheduled for this course yet.</p>
                  </div>
                } @else {
                  <div class="quizzes-list">
                    @for (quiz of course.quizzes; track quiz.id) {
                      <div class="quiz-row card">
                        <div class="quiz-left">
                          <div class="quiz-icon">📝</div>
                          <div class="quiz-info">
                            <h4 class="quiz-title">{{ quiz.title }}</h4>
                            <p class="quiz-desc">{{ quiz.description || 'Test your understanding with rigorous multi-choice evaluation.' }}</p>
                            <span class="quiz-meta">Passing score: <strong>{{ quiz.passing_score }}%</strong></span>
                          </div>
                        </div>

                        <div class="quiz-right">
                          @if (course.is_enrolled) {
                            <a [routerLink]="['/courses', course.id, 'quizzes', quiz.id]" class="btn btn-sm btn-primary">
                              Take Assessment
                            </a>
                          } @else {
                            <span class="locked-badge" title="Enroll to take assessment">🔒 Locked</span>
                          }
                        </div>
                      </div>
                    }
                  </div>
                }

                <!-- Practical Assignments Section -->
                <div class="section-title-bar assignments-title-bar">
                  <h2>Practical Assignments</h2>
                  <span class="badge badge-neutral">{{ course.assignments?.length || 0 }} Assignments</span>
                </div>

                @if (!course.assignments || course.assignments.length === 0) {
                  <div class="empty-curriculum card">
                    <p>No practical assignments scheduled for this course yet.</p>
                  </div>
                } @else {
                  <div class="quizzes-list">
                    @for (assign of course.assignments; track assign.id) {
                      <div class="quiz-row card">
                        <div class="quiz-left">
                          <div class="quiz-icon">💼</div>
                          <div class="quiz-info">
                            <h4 class="quiz-title">{{ assign.title }}</h4>
                            <p class="quiz-desc">{{ assign.description || 'Hands-on practical assignment and grading rubric.' }}</p>
                            <span class="quiz-meta">
                              Max Marks: <strong>{{ assign.max_marks }}</strong>
                              @if (assign.due_date) {
                                &nbsp;|&nbsp; Due: <strong>{{ assign.due_date | date:'short' }}</strong>
                              }
                              @if (assign.my_status) {
                                &nbsp;|&nbsp; Status: <span class="badge" [ngClass]="assign.my_status === 'graded' ? 'badge-success' : 'badge-warning'">{{ assign.my_status | titlecase }}</span>
                              }
                              @if (assign.my_grade !== null && assign.my_grade !== undefined) {
                                &nbsp;|&nbsp; Grade: <strong style="color: var(--success);">{{ assign.my_grade }} / {{ assign.max_marks }}</strong>
                              }
                            </span>
                          </div>
                        </div>

                        <div class="quiz-right">
                          @if (course.is_enrolled) {
                            <a [routerLink]="['/courses', course.id, 'assignments', assign.id]" class="btn btn-sm btn-primary">
                              {{ assign.my_status ? 'View Work & Grade' : 'Open Assignment' }}
                            </a>
                          } @else {
                            <span class="locked-badge" title="Enroll to view assignment">🔒 Locked</span>
                          }
                        </div>
                      </div>
                    }
                  </div>
                }

                <!-- Learning Materials Section -->
                <div class="section-title-bar materials-title-bar">
                  <h2>Learning Materials & Downloads</h2>
                  <span class="badge badge-neutral">{{ course.materials?.length || 0 }} Resources</span>
                </div>

                @if (!course.materials || course.materials.length === 0) {
                  <div class="empty-curriculum card">
                    <p>No downloadable learning materials scheduled for this course yet.</p>
                  </div>
                } @else {
                  <div class="quizzes-list">
                    @for (mat of course.materials; track mat.id) {
                      <div class="quiz-row card">
                        <div class="quiz-left">
                          <div class="mat-ext-badge" [ngClass]="getExtBadgeClass(mat.file_extension)">
                            {{ mat.file_extension || 'FILE' }}
                          </div>
                          <div class="quiz-info">
                            <h4 class="quiz-title">{{ mat.title }}</h4>
                            @if (mat.description) {
                              <p class="quiz-desc">{{ mat.description }}</p>
                            }
                            <span class="quiz-meta">
                              {{ mat.original_filename }} &nbsp;|&nbsp;
                              Size: <strong>{{ mat.file_size_formatted }}</strong> &nbsp;|&nbsp;
                              Uploaded: <strong>{{ mat.created_at | date:'mediumDate' }}</strong>
                            </span>
                          </div>
                        </div>

                        <div class="quiz-right">
                          @if (course.is_enrolled) {
                            <button (click)="downloadMaterial(mat)" class="btn btn-sm btn-primary">
                              Download
                            </button>
                          } @else {
                            <span class="locked-badge" title="Enroll in course to download materials">🔒 Locked</span>
                          }
                        </div>
                      </div>
                    }
                  </div>
                }
              </div>

              <!-- Sidebar Column: Course Community & AI Assistant -->
              <div class="curriculum-sidebar">
                <div class="community-promo-card card">
                  <div class="community-promo-header">
                    <span class="community-icon">📢</span>
                    <h3>Course Community</h3>
                  </div>
                  <p>Stay updated with faculty announcements and collaborate with fellow learners in discussion threads.</p>
                  <div class="community-promo-links">
                    <a [routerLink]="['/courses', course.id, 'announcements']" class="btn btn-outline btn-block community-btn">
                      View Announcements
                    </a>
                    <a [routerLink]="['/courses', course.id, 'discussions']" class="btn btn-outline btn-block community-btn">
                      Discussion Forum
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      }
    </div>
  `,
  styles: [`
    .course-detail-page {
      padding-bottom: 4rem;
    }
    .course-hero {
      background: linear-gradient(135deg, #ffffff 0%, #faf8ff 50%, #f5f3ff 100%);
      border-bottom: 1px solid rgba(221, 214, 254, 0.7);
      padding: 3.5rem 0;
    }
    .hero-content {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 3rem;
      align-items: start;
    }
    @media (max-width: 900px) {
      .hero-content {
        grid-template-columns: 1fr;
      }
    }
    .badges-row {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1rem;
    }
    .course-title {
      font-size: 2.25rem;
      color: #0f172a;
      font-weight: 800;
      letter-spacing: -0.02em;
      line-height: 1.25;
      margin-bottom: 1rem;
    }
    .course-description {
      font-size: 1.1rem;
      color: var(--text-muted);
      line-height: 1.6;
      margin-bottom: 2rem;
    }
    .meta-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 1.25rem;
    }
    .meta-pill {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.9rem;
      font-weight: 600;
      color: #4f46e5;
      background-color: #ffffff;
      padding: 0.45rem 0.95rem;
      border-radius: 9999px;
      border: 1px solid #ddd6fe;
      box-shadow: 0 1px 3px rgba(99, 102, 241, 0.05);
    }
    .hero-action-card {
      padding: 2rem;
      background: #ffffff;
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 10px 30px -5px rgba(99, 102, 241, 0.12);
    }
    .action-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
    }
    .progress-box {
      margin-bottom: 1.5rem;
    }
    .progress-header {
      display: flex;
      justify-content: space-between;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 0.4rem;
      color: var(--text-muted);
    }
    .progress-val {
      color: var(--primary);
      font-weight: 700;
    }
    .enroll-perk {
      font-size: 0.9rem;
      color: var(--text-muted);
      line-height: 1.5;
      margin-bottom: 1.5rem;
    }
    .btn-block {
      width: 100%;
    }
    .instructor-preview {
      margin-top: 1.75rem;
      padding-top: 1.25rem;
      border-top: 1px solid var(--border-light);
    }
    .instructor-title {
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--text-light);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .instructor-name {
      font-size: 1rem;
      font-weight: 700;
      color: var(--text-main);
      margin-top: 0.2rem;
    }
    .instructor-email {
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .curriculum-section {
      padding: 3rem 0;
    }
    .curriculum-layout {
      display: grid;
      grid-template-columns: 2.2fr 1fr;
      gap: 3rem;
      align-items: start;
    }
    @media (max-width: 900px) {
      .curriculum-layout {
        grid-template-columns: 1fr;
      }
    }
    .section-title-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 1.25rem;
    }
    .quizzes-title-bar, .assignments-title-bar {
      margin-top: 2.5rem;
    }
    .lessons-list, .quizzes-list {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .lesson-row, .quiz-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1.25rem;
      transition: var(--transition);
    }
    .lesson-row.completed {
      border-left: 4px solid var(--success);
    }
    .lesson-left, .quiz-left {
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    .lesson-number {
      width: 36px;
      height: 36px;
      border-radius: var(--radius-md);
      background-color: var(--bg-subtle);
      color: var(--text-main);
      font-weight: 800;
      font-size: 1rem;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .quiz-icon {
      font-size: 1.5rem;
    }
    .lesson-title, .quiz-title {
      font-size: 1.05rem;
      margin-bottom: 0.2rem;
    }
    .quiz-desc {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-bottom: 0.3rem;
    }
    .lesson-status {
      font-size: 0.8rem;
      color: var(--text-light);
    }
    .status-completed {
      color: var(--success);
      font-weight: 700;
    }
    .quiz-meta {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .locked-badge {
      font-size: 0.85rem;
      color: var(--text-light);
      background: var(--bg-subtle);
      padding: 0.35rem 0.65rem;
      border-radius: var(--radius-sm);
    }
    .ai-promo-card {
      padding: 1.75rem;
      background: linear-gradient(135deg, #ffffff 0%, #f5f3ff 100%);
      border-color: #ddd6fe;
    }
    .ai-promo-icon {
      font-size: 2rem;
      margin-bottom: 0.75rem;
    }
    .ai-promo-card h3 {
      font-size: 1.2rem;
      margin-bottom: 0.5rem;
    }
    .ai-promo-card p {
      font-size: 0.9rem;
      color: var(--text-muted);
      line-height: 1.5;
      margin-bottom: 1.25rem;
    }
    .materials-title-bar {
      margin-top: 2rem;
    }
    .mat-ext-badge {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 48px;
      height: 48px;
      border-radius: var(--radius-md);
      font-size: 0.75rem;
      font-weight: 800;
      letter-spacing: 0.05em;
      flex-shrink: 0;
    }
    .ext-pdf { background-color: #fee2e2; color: #b91c1c; }
    .ext-docx { background-color: #dbeafe; color: #1d4ed8; }
    .ext-pptx { background-color: #ffedd5; color: #c2410c; }
    .ext-txt { background-color: #f1f5f9; color: #475569; }
    .ext-img { background-color: #dcfce7; color: #15803d; }
    .loading-state {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
      padding: 5rem;
      color: var(--text-muted);
    }
    .spinner {
      width: 28px;
      height: 28px;
      border: 3px solid var(--border-color);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Curriculum Sections */
    .curriculum-sections-flow {
      display: flex;
      flex-direction: column;
      gap: 1.75rem;
    }
    .syllabus-section-block {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      padding: 1.25rem;
    }
    .syllabus-section-header {
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      margin-bottom: 1rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--border-light);
    }
    .sec-pill {
      font-size: 0.75rem;
      font-weight: 700;
      background: #eef2ff;
      color: var(--primary);
      padding: 0.2rem 0.5rem;
      border-radius: var(--radius-sm);
      white-space: nowrap;
    }
    .sec-pill-subtle {
      background: var(--bg-subtle);
      color: var(--text-muted);
    }
    .sec-title-group {
      flex: 1;
    }
    .syllabus-section-title {
      font-size: 1.15rem;
      margin: 0 0 0.25rem 0;
      color: var(--text-main);
    }
    .syllabus-section-desc {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin: 0;
    }
    .enrolled-quick-actions {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      margin-top: 0.75rem;
      font-size: 0.85rem;
    }
    .quick-action-link {
      color: var(--primary);
      text-decoration: none;
      font-weight: 600;
    }
    .quick-action-link:hover {
      text-decoration: underline;
    }
    .quick-action-dot {
      color: var(--text-muted);
    }
    .community-promo-card {
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }
    .community-promo-header {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.5rem;
    }
    .community-promo-header h3 {
      margin: 0;
      font-size: 1.15rem;
    }
    .community-promo-links {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      margin-top: 1rem;
    }
    .community-btn {
      font-size: 0.875rem;
      font-weight: 600;
      padding: 0.5rem 0.75rem;
    }
  `]
})
export class CourseDetailComponent implements OnInit {
  @Input() id!: string; // Bound from router param :id
  course: CourseDetail | null = null;
  isLoading = true;
  isEnrolling = false;
  enrollMessage = '';
  isEnrollError = false;

  constructor(
    private courseService: CourseService,
    private materialService: MaterialService,
    public auth: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    if (this.id) {
      this.loadCourse(Number(this.id));
    }
  }

  loadCourse(courseId: number): void {
    this.isLoading = true;
    this.courseService.getCourse(courseId).subscribe({
      next: (data) => {
        this.course = data;
        this.isLoading = false;
      },
      error: () => {
        this.course = null;
        this.isLoading = false;
      }
    });
  }

  enroll(): void {
    if (!this.course) return;
    this.isEnrolling = true;
    this.enrollMessage = '';
    this.isEnrollError = false;

    this.courseService.enrollInCourse(this.course.id).subscribe({
      next: () => {
        this.isEnrolling = false;
        this.enrollMessage = 'Successfully enrolled! You may now begin your lessons.';
        this.course!.is_enrolled = true;
        this.course!.user_progress_percentage = 0;
      },
      error: (err) => {
        this.isEnrolling = false;
        this.isEnrollError = true;
        this.enrollMessage = err.error?.detail || 'Enrollment failed. Please try again.';
      }
    });
  }

  getTargetLessonId(): number {
    if (!this.course || this.course.lessons.length === 0) return 0;
    const uncompleted = this.course.lessons.find(l => !l.is_completed);
    return uncompleted ? uncompleted.id : this.course.lessons[0].id;
  }

  getDifficultyBadge(diff: string): string {
    switch (diff) {
      case 'beginner': return 'badge-success';
      case 'intermediate': return 'badge-warning';
      case 'advanced': return 'badge-danger';
      default: return 'badge-neutral';
    }
  }

  hasSections(): boolean {
    return !!(this.course?.sections && this.course.sections.length > 0);
  }

  getLessonsForSection(sectionId: number) {
    if (!this.course) return [];
    return this.course.lessons.filter(l => l.section_id === sectionId);
  }

  getUncategorizedLessons() {
    if (!this.course) return [];
    return this.course.lessons.filter(l => !l.section_id);
  }

  downloadMaterial(mat: any): void {
    if (!mat || !mat.id) return;
    this.materialService.triggerBrowserDownload(mat.id, mat.original_filename);
  }

  getExtBadgeClass(ext?: string): string {
    switch (ext?.toUpperCase()) {
      case 'PDF': return 'ext-pdf';
      case 'DOCX': return 'ext-docx';
      case 'PPTX': return 'ext-pptx';
      case 'TXT': return 'ext-txt';
      case 'PNG':
      case 'JPG':
      case 'JPEG': return 'ext-img';
      default: return 'ext-txt';
    }
  }
}

