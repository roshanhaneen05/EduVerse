import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { StudentService } from '../../core/services/student.service';
import { EnrolledCourseDetail } from '../../core/models/student.model';

@Component({
  selector: 'app-my-learning',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="my-learning-page">
      <div class="container">
        <!-- Sub-Navigation Bar for Student Portal -->
        <div class="student-nav-bar">
          <a routerLink="/student/dashboard" class="nav-pill">Overview</a>
          <a routerLink="/student/my-learning" class="nav-pill active">My Learning</a>
          <a routerLink="/student/assignments" class="nav-pill">Assignments & Tasks</a>
          <a routerLink="/student/quiz-history" class="nav-pill">Assessment History</a>
        </div>

        <!-- Header -->
        <div class="page-header">
          <div>
            <h1>My Learning</h1>
            <p class="subtitle">Track your enrolled academic curriculum, progress velocity, and lesson completion.</p>
          </div>
          <div class="header-actions">
            <a routerLink="/courses" class="btn btn-primary">
              + Explore More Courses
            </a>
          </div>
        </div>

        @if (feedbackMessage) {
          <div class="alert alert-danger">
            {{ feedbackMessage }}
          </div>
        }

        <!-- Filter Bar -->
        <div class="filter-bar card">
          <div class="filter-buttons">
            <button
              (click)="setFilter('all')"
              class="filter-btn"
              [class.active]="currentFilter === 'all'"
            >
              All Courses ({{ courses.length }})
            </button>
            <button
              (click)="setFilter('in_progress')"
              class="filter-btn"
              [class.active]="currentFilter === 'in_progress'"
            >
              In Progress ({{ inProgressCount }})
            </button>
            <button
              (click)="setFilter('completed')"
              class="filter-btn"
              [class.active]="currentFilter === 'completed'"
            >
              Completed ({{ completedCount }})
            </button>
          </div>
        </div>

        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading your academic enrollments...</span>
          </div>
        } @else if (filteredCourses.length === 0) {
          <div class="empty-block card">
            <div class="empty-emoji">🎓</div>
            @if (currentFilter === 'completed') {
              <h3>No completed courses yet</h3>
              <p>Finish all syllabus lessons in an active course to mark it completed.</p>
              <button (click)="setFilter('in_progress')" class="btn btn-secondary">View In-Progress Courses</button>
            } @else if (currentFilter === 'in_progress') {
              <h3>No in-progress courses</h3>
              <p>You have finished all your enrolled courses or haven't started one yet.</p>
              <a routerLink="/courses" class="btn btn-primary">Browse Course Catalog</a>
            } @else {
              <h3>You are not enrolled in any courses</h3>
              <p>Explore our catalogue of full-stack engineering, cloud architecture, and data science courses.</p>
              <a routerLink="/courses" class="btn btn-primary">Browse Course Catalog</a>
            }
          </div>
        } @else {
          <!-- Enrolled Courses Grid -->
          <div class="courses-grid">
            @for (c of filteredCourses; track c.enrollment_id) {
              <div class="course-card card">
                <div class="card-top">
                  <div class="badge-row">
                    <span class="badge badge-primary">{{ c.course_category }}</span>
                    <span class="badge" [ngClass]="getDifficultyBadge(c.course_difficulty)">
                      {{ c.course_difficulty }}
                    </span>
                    @if (c.status === 'completed') {
                      <span class="badge badge-success">✓ 100% Completed</span>
                    }
                  </div>

                  <h3 class="course-title">
                    <a [routerLink]="['/courses', c.course_id]">{{ c.course_title }}</a>
                  </h3>
                  <p class="instructor-sub">
                    Faculty: <strong>{{ c.instructor_name }}</strong>
                  </p>
                </div>

                <div class="progress-section">
                  <div class="progress-labels">
                    <span class="lesson-count-sub">
                      <strong>{{ c.completed_lessons }}</strong> / {{ c.total_lessons }} lessons completed
                      @if (c.remaining_lessons > 0) {
                        · <span class="rem-text">{{ c.remaining_lessons }} remaining</span>
                      }
                    </span>
                    <span class="pct-val">{{ c.completion_percentage }}%</span>
                  </div>
                  <div class="progress-bar-container">
                    <div
                      class="progress-bar-fill"
                      [style.width.%]="c.completion_percentage"
                      [class.fill-success]="c.status === 'completed'"
                    ></div>
                  </div>
                  @if (c.next_lesson_title && c.status !== 'completed') {
                    <p class="next-step-hint">
                      Next: <strong>{{ c.next_lesson_title }}</strong>
                    </p>
                  }
                </div>

                <div class="card-footer">
                  <div class="date-info">
                    <span>Enrolled {{ c.enrolled_at | date:'mediumDate' }}</span>
                  </div>
                  <button (click)="continueCourse(c)" class="btn btn-sm btn-primary">
                    {{ c.status === 'completed' ? 'Review Course' : 'Continue Learning' }} →
                  </button>
                </div>
              </div>
            }
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .my-learning-page {
      padding: 2.5rem 0 4rem 0;
      min-height: calc(100vh - 120px);
    }
    .student-nav-bar {
      display: flex;
      gap: 0.65rem;
      margin-bottom: 2rem;
      border-bottom: 1px solid rgba(221, 214, 254, 0.6);
      padding-bottom: 0.85rem;
      overflow-x: auto;
    }
    .nav-pill {
      padding: 0.55rem 1.15rem;
      border-radius: 9999px;
      font-size: 0.9rem;
      font-weight: 600;
      color: #64748b;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      text-decoration: none;
      white-space: nowrap;
      transition: all 0.2s ease;
    }
    .nav-pill:hover {
      background-color: #ede9fe;
      border-color: #ddd6fe;
      color: #4f46e5;
    }
    .nav-pill.active {
      background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
      border-color: transparent;
      color: #ffffff;
      box-shadow: 0 4px 14px rgba(79, 70, 229, 0.28);
    }
    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.75rem;
      flex-wrap: wrap;
      gap: 1.25rem;
    }
    .page-header h1 {
      font-size: 2.15rem;
      color: #0f172a;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 0.35rem;
    }
    .subtitle {
      color: #64748b;
      font-size: 1.05rem;
    }
    .filter-bar {
      padding: 0.85rem 1.35rem;
      margin-bottom: 2rem;
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 4px 15px rgba(99, 102, 241, 0.05);
    }
    .filter-buttons {
      display: flex;
      gap: 0.65rem;
      flex-wrap: wrap;
    }
    .filter-btn {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      padding: 0.5rem 1.1rem;
      border-radius: 9999px;
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      color: #64748b;
      transition: all 0.2s;
    }
    .filter-btn:hover {
      background-color: #ede9fe;
      border-color: #ddd6fe;
      color: #4f46e5;
    }
    .filter-btn.active {
      background-color: #ede9fe;
      border-color: #c4b5fd;
      color: #4f46e5;
      font-weight: 700;
    }
    .courses-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1.75rem;
    }
    .course-card {
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 1.6rem;
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 8px 25px -4px rgba(99, 102, 241, 0.07);
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .course-card:hover {
      transform: translateY(-3px);
      box-shadow: 0 16px 36px -8px rgba(99, 102, 241, 0.14);
    }
    .badge-row {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 0.85rem;
      flex-wrap: wrap;
    }
    .course-title {
      font-size: 1.2rem;
      margin-bottom: 0.4rem;
      line-height: 1.35;
    }
    .course-title a {
      color: var(--text-primary);
      text-decoration: none;
    }
    .course-title a:hover {
      color: var(--primary);
    }
    .instructor-sub {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-bottom: 1.25rem;
    }
    .progress-section {
      margin: 1rem 0 1.25rem 0;
    }
    .progress-labels {
      display: flex;
      justify-content: space-between;
      font-size: 0.825rem;
      margin-bottom: 0.4rem;
    }
    .lesson-count-sub {
      color: var(--text-muted);
    }
    .rem-text {
      color: var(--text-muted);
    }
    .pct-val {
      font-weight: 700;
      color: var(--primary);
    }
    .progress-bar-container {
      background-color: var(--border-light);
      border-radius: var(--radius-sm);
      height: 8px;
      overflow: hidden;
    }
    .progress-bar-fill {
      background-color: var(--primary);
      height: 100%;
      transition: width 0.3s ease;
    }
    .progress-bar-fill.fill-success {
      background-color: var(--success);
    }
    .next-step-hint {
      font-size: 0.775rem;
      color: var(--text-muted);
      margin-top: 0.4rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .card-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 1rem;
      border-top: 1px solid var(--border-light);
    }
    .date-info {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .empty-block {
      text-align: center;
      padding: 4rem 2rem;
    }
    .empty-emoji {
      font-size: 3rem;
      margin-bottom: 1rem;
    }
    .empty-block h3 {
      font-size: 1.4rem;
      margin-bottom: 0.5rem;
    }
    .empty-block p {
      color: var(--text-muted);
      margin-bottom: 1.5rem;
    }
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
  `]
})
export class MyLearningComponent implements OnInit {
  courses: EnrolledCourseDetail[] = [];
  currentFilter: 'all' | 'in_progress' | 'completed' = 'all';
  isLoading = true;
  feedbackMessage = '';

  constructor(
    private studentService: StudentService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadCourses();
  }

  loadCourses(): void {
    this.isLoading = true;
    this.studentService.getMyLearning('all').subscribe({
      next: (list) => {
        this.courses = list;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.feedbackMessage = err.error?.detail || 'Failed to load your enrolled courses.';
      }
    });
  }

  setFilter(filter: 'all' | 'in_progress' | 'completed'): void {
    this.currentFilter = filter;
  }

  get filteredCourses(): EnrolledCourseDetail[] {
    if (this.currentFilter === 'in_progress') {
      return this.courses.filter(c => c.status === 'in_progress');
    }
    if (this.currentFilter === 'completed') {
      return this.courses.filter(c => c.status === 'completed');
    }
    return this.courses;
  }

  get inProgressCount(): number {
    return this.courses.filter(c => c.status === 'in_progress').length;
  }

  get completedCount(): number {
    return this.courses.filter(c => c.status === 'completed').length;
  }

  continueCourse(course: EnrolledCourseDetail): void {
    if (course.next_lesson_id) {
      this.router.navigate(['/courses', course.course_id, 'learn', course.next_lesson_id]);
    } else {
      this.studentService.continueCourse(course.course_id).subscribe({
        next: (cont) => {
          if (cont.next_lesson_id) {
            this.router.navigate(['/courses', course.course_id, 'learn', cont.next_lesson_id]);
          } else {
            this.router.navigate(['/courses', course.course_id]);
          }
        },
        error: () => {
          this.router.navigate(['/courses', course.course_id]);
        }
      });
    }
  }

  getDifficultyBadge(difficulty: string): string {
    switch (difficulty?.toLowerCase()) {
      case 'beginner': return 'badge-success';
      case 'intermediate': return 'badge-primary';
      case 'advanced': return 'badge-warning';
      default: return 'badge-neutral';
    }
  }
}

