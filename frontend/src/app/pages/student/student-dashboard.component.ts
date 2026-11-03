import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { StudentService } from '../../core/services/student.service';
import { EnhancedStudentDashboardResponse, EnrolledCourseDetail } from '../../core/models/student.model';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-student-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="dashboard-page">
      <div class="container">
        <!-- Sub-Navigation Bar for Student Portal -->
        <div class="student-nav-bar">
          <a routerLink="/student/dashboard" class="nav-pill active">Overview</a>
          <a routerLink="/student/my-learning" class="nav-pill">My Learning</a>
          <a routerLink="/student/assignments" class="nav-pill">Assignments & Tasks</a>
          <a routerLink="/student/quiz-history" class="nav-pill">Assessment History</a>
        </div>

        <!-- Dashboard Welcome Banner -->
        <div class="welcome-banner card">
          <div class="welcome-text">
            <div class="user-greeting-badge">
              <span class="online-indicator"></span>
              <span>Learner Portal</span>
            </div>
            <h1>Welcome back, {{ auth.currentUser()?.full_name }}! 👋</h1>
            <p>Track your academic syllabus velocity, manage upcoming deadlines, and resume your lessons.</p>
          </div>
          <div class="welcome-actions">
            <a routerLink="/courses" class="btn btn-primary">Browse Catalog</a>
            <a routerLink="/student/my-learning" class="btn btn-secondary">My Enrolled Courses</a>
          </div>
        </div>

        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Aggregating your real-time learning records...</span>
          </div>
        } @else if (errorMessage) {
          <div class="card error-card">
            <h3>Unable to load dashboard</h3>
            <p>{{ errorMessage }}</p>
            <button (click)="loadDashboard()" class="btn btn-primary">Try Again</button>
          </div>
        } @else if (data) {
          <!-- Stats Metrics Cards Grid -->
          <div class="stats-grid">
            <div class="stat-card card">
              <div class="stat-icon icon-blue">📚</div>
              <div class="stat-info">
                <span class="stat-val">{{ data.stats.enrolled_courses_count }}</span>
                <span class="stat-label">Enrolled Courses</span>
                <span class="stat-sub">{{ data.stats.in_progress_courses_count }} in progress</span>
              </div>
            </div>

            <div class="stat-card card">
              <div class="stat-icon icon-indigo">📈</div>
              <div class="stat-info">
                <span class="stat-val">{{ data.stats.overall_progress_percentage }}%</span>
                <span class="stat-label">Overall Progress</span>
                <span class="stat-sub">{{ data.stats.completed_courses_count }} courses completed</span>
              </div>
            </div>

            <div class="stat-card card">
              <div class="stat-icon icon-amber">📝</div>
              <div class="stat-info">
                <span class="stat-val">{{ data.stats.quizzes_passed }} / {{ data.stats.total_quizzes_taken }}</span>
                <span class="stat-label">Quizzes Passed</span>
                <span class="stat-sub">Avg Score: {{ data.stats.average_quiz_score }}%</span>
              </div>
            </div>

            <div class="stat-card card">
              <div class="stat-icon icon-emerald">📋</div>
              <div class="stat-info">
                <span class="stat-val">{{ data.stats.submitted_assignments_count }} / {{ data.stats.total_assignments_count }}</span>
                <span class="stat-label">Tasks Submitted</span>
                <span class="stat-sub">{{ data.stats.pending_assignments_count }} pending tasks</span>
              </div>
            </div>
          </div>

          <!-- Highlighted Continue Learning Hero Card (If Active Course Exists) -->
          @if (activeCourseToContinue) {
            <div class="continue-hero card">
              <div class="continue-hero-content">
                <div class="hero-tag">
                  <span class="pulse-dot"></span>
                  <span>Resume Where You Left Off</span>
                </div>
                <h2>{{ activeCourseToContinue.course_title }}</h2>
                <p class="hero-lesson-sub">
                  Next Step: <strong>{{ activeCourseToContinue.next_lesson_title || 'Continue Lesson' }}</strong> · {{ activeCourseToContinue.completed_lessons }} of {{ activeCourseToContinue.total_lessons }} lessons finished
                </p>
                <div class="hero-progress-bar">
                  <div class="hero-progress-fill" [style.width.%]="activeCourseToContinue.completion_percentage"></div>
                </div>
              </div>
              <div class="continue-hero-action">
                <button (click)="continueCourse(activeCourseToContinue)" class="btn btn-primary btn-lg">
                  Continue Learning →
                </button>
              </div>
            </div>
          }

          <!-- Two-Column Operational Row: Upcoming Deadlines & Recent Grades -->
          <div class="two-col-grid">
            <!-- Upcoming Assignment Deadlines -->
            <div class="card panel-card">
              <div class="panel-header">
                <div>
                  <h3>Upcoming Deadlines</h3>
                  <p class="panel-sub">Assignments due in your enrolled courses</p>
                </div>
                <a routerLink="/student/assignments" class="panel-link">View All Tasks →</a>
              </div>

              @if (data.upcoming_deadlines.length === 0) {
                <div class="empty-panel">
                  <span class="empty-icon">🎉</span>
                  <p>No upcoming assignment deadlines! You're completely up to date.</p>
                </div>
              } @else {
                <div class="deadline-list">
                  @for (d of data.upcoming_deadlines; track d.assignment_id) {
                    <div class="deadline-item">
                      <div class="deadline-info">
                        <strong>{{ d.assignment_title }}</strong>
                        <span class="deadline-course">{{ d.course_title }} · Max {{ d.max_marks }} marks</span>
                      </div>
                      <div class="deadline-meta">
                        <span class="badge" [ngClass]="d.is_submitted ? 'badge-success' : 'badge-warning'">
                          {{ d.is_submitted ? 'Submitted' : 'Pending' }}
                        </span>
                        <span class="due-date-text">Due: {{ d.due_date | date:'shortDate' }}</span>
                      </div>
                    </div>
                  }
                </div>
              }
            </div>

            <!-- Recent Assessment Grades & Feedback -->
            <div class="card panel-card">
              <div class="panel-header">
                <div>
                  <h3>Recent Assessment Grades</h3>
                  <p class="panel-sub">Latest feedback and scores earned</p>
                </div>
                <a routerLink="/student/quiz-history" class="panel-link">History →</a>
              </div>

              @if (data.recent_grades.length === 0) {
                <div class="empty-panel">
                  <span class="empty-icon">📊</span>
                  <p>No assessment grades recorded yet. Complete a quiz or assignment!</p>
                </div>
              } @else {
                <div class="grade-list">
                  @for (g of data.recent_grades; track g.assessment_type + g.reference_id) {
                    <div class="grade-item">
                      <div class="grade-info">
                        <div class="grade-title-row">
                          <span class="badge" [ngClass]="g.assessment_type === 'quiz' ? 'badge-primary' : 'badge-secondary'">
                            {{ g.assessment_type === 'quiz' ? 'Quiz' : 'Assignment' }}
                          </span>
                          <strong>{{ g.title }}</strong>
                        </div>
                        <span class="grade-course">{{ g.course_title }}</span>
                        @if (g.feedback) {
                          <p class="grade-feedback">"{{ g.feedback }}"</p>
                        }
                      </div>
                      <div class="grade-score-box">
                        <span class="grade-val" [class.text-success]="g.passed" [class.text-danger]="g.passed === false">
                          {{ g.score_or_grade }} / {{ g.max_score_or_grade }}
                        </span>
                        <span class="grade-date">{{ g.date | date:'shortDate' }}</span>
                      </div>
                    </div>
                  }
                </div>
              }
            </div>
          </div>

          <!-- Recently Accessed Lessons Section -->
          @if (data.recently_accessed_lessons.length > 0) {
            <div class="section-block">
              <div class="section-header">
                <div>
                  <h2>Recently Accessed Lessons</h2>
                  <p class="section-sub">Your verified learning history across curriculum modules</p>
                </div>
              </div>

              <div class="table-container card">
                <table>
                  <thead>
                    <tr>
                      <th>Lesson Title</th>
                      <th>Course</th>
                      <th>Status</th>
                      <th>Last Engaged</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (l of data.recently_accessed_lessons; track l.lesson_id) {
                      <tr>
                        <td>
                          <strong>{{ l.lesson_title }}</strong>
                        </td>
                        <td>{{ l.course_title }}</td>
                        <td>
                          <span class="badge" [ngClass]="l.is_completed ? 'badge-success' : 'badge-warning'">
                            {{ l.is_completed ? 'Completed' : 'In Progress' }}
                          </span>
                        </td>
                        <td class="date-cell">{{ l.updated_at | date:'medium' }}</td>
                        <td>
                          <a [routerLink]="['/courses', l.course_id, 'learn', l.lesson_id]" class="btn btn-sm btn-outline">
                            {{ l.is_completed ? 'Review' : 'Resume' }} →
                          </a>
                        </td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            </div>
          }

          <!-- Recommended Courses for You -->
          @if (data.recommended_courses.length > 0) {
            <div class="section-block">
              <div class="section-header">
                <div>
                  <h2>Recommended For You</h2>
                  <p class="section-sub">Curated offerings matching your academic interests</p>
                </div>
                <a routerLink="/courses" class="panel-link">Browse Full Catalog →</a>
              </div>

              <div class="rec-grid">
                @for (c of data.recommended_courses; track c.id) {
                  <div class="rec-card card">
                    <div class="rec-top">
                      <div class="badge-row">
                        <span class="badge badge-primary">{{ c.category }}</span>
                        <span class="badge" [ngClass]="getDifficultyBadge(c.difficulty)">
                          {{ c.difficulty }}
                        </span>
                      </div>
                      <h3>
                        <a [routerLink]="['/courses', c.id]">{{ c.title }}</a>
                      </h3>
                      <p class="rec-desc">{{ c.description | slice:0:110 }}...</p>
                    </div>
                    <div class="rec-footer">
                      <span class="inst-name">By {{ c.instructor?.full_name || 'Faculty' }}</span>
                      <a [routerLink]="['/courses', c.id]" class="btn btn-sm btn-primary">
                        View Course →
                      </a>
                    </div>
                  </div>
                }
              </div>
            </div>
          }
        }
      </div>
    </div>
  `,
  styles: [`
    .dashboard-page {
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
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
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
    .welcome-banner {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 2.25rem 2.5rem;
      margin-bottom: 2.25rem;
      background: linear-gradient(135deg, #ffffff 0%, #faf8ff 50%, #f5f3ff 100%);
      border: 1px solid #ddd6fe;
      border-radius: 20px;
      box-shadow: 0 10px 30px -5px rgba(99, 102, 241, 0.1);
      flex-wrap: wrap;
      gap: 1.5rem;
    }
    .user-greeting-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      background: #ede9fe;
      color: #6d28d9;
      border: 1px solid #ddd6fe;
      padding: 0.25rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 700;
      margin-bottom: 0.65rem;
    }
    .online-indicator {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background-color: #10b981;
    }
    .welcome-text h1 {
      font-size: 1.85rem;
      color: #0f172a;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 0.35rem;
    }
    .welcome-text p {
      color: #64748b;
      font-size: 0.95rem;
      margin: 0;
    }
    .welcome-actions {
      display: flex;
      gap: 0.85rem;
      flex-wrap: wrap;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.35rem;
      margin-bottom: 2.25rem;
    }
    .stat-card {
      display: flex;
      align-items: center;
      gap: 1.25rem;
      padding: 1.5rem;
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 6px 20px -3px rgba(99, 102, 241, 0.06);
    }
    .stat-icon {
      font-size: 1.75rem;
      width: 52px;
      height: 52px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .icon-blue { background: #ede9fe; }
    .icon-indigo { background: #e0e7ff; }
    .icon-amber { background: #fef3c7; }
    .icon-emerald { background: #dcfce7; }
    .stat-info {
      display: flex;
      flex-direction: column;
    }
    .stat-val {
      font-size: 1.85rem;
      font-weight: 800;
      color: #0f172a;
      line-height: 1.1;
    }
    .stat-label {
      color: #475569;
      font-size: 0.875rem;
      font-weight: 700;
      margin-top: 0.25rem;
    }
    .stat-sub {
      font-size: 0.775rem;
      color: #94a3b8;
      margin-top: 0.2rem;
    }
    .continue-hero {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 2rem 2.25rem;
      margin-bottom: 2.25rem;
      background: linear-gradient(135deg, #312e81 0%, #4338ca 60%, #4f46e5 100%);
      color: #ffffff;
      border: none;
      border-radius: 20px;
      box-shadow: 0 12px 35px -5px rgba(79, 70, 229, 0.3);
      flex-wrap: wrap;
      gap: 1.5rem;
    }
    .hero-tag {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background: rgba(255, 255, 255, 0.18);
      color: #ede9fe;
      padding: 0.3rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.02em;
      margin-bottom: 0.5rem;
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      background-color: #a5b4fc;
      border-radius: 50%;
    }
    .continue-hero h2 {
      color: #ffffff;
      font-size: 1.55rem;
      font-weight: 800;
      margin-bottom: 0.35rem;
    }
    .hero-lesson-sub {
      color: #e0e7ff;
      font-size: 0.925rem;
      margin-bottom: 0.85rem;
    }
    .hero-progress-bar {
      background: rgba(255, 255, 255, 0.25);
      border-radius: 9999px;
      height: 8px;
      width: 100%;
      max-width: 400px;
      overflow: hidden;
    }
    .hero-progress-fill {
      background-color: #38bdf8;
      height: 100%;
    }
    .two-col-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1.5rem;
      margin-bottom: 2rem;
    }
    .panel-card {
      padding: 1.5rem;
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1.25rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--border-light);
    }
    .panel-header h3 {
      font-size: 1.15rem;
      margin-bottom: 0.15rem;
    }
    .panel-sub {
      font-size: 0.8rem;
      color: var(--text-muted);
      margin: 0;
    }
    .panel-link {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--primary);
      text-decoration: none;
      white-space: nowrap;
    }
    .deadline-list, .grade-list {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }
    .deadline-item, .grade-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.75rem;
      background: var(--bg-subtle);
      border-radius: var(--radius-md);
      gap: 1rem;
    }
    .deadline-info, .grade-info {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }
    .deadline-course, .grade-course {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .deadline-meta, .grade-score-box {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.2rem;
      flex-shrink: 0;
    }
    .due-date-text, .grade-date {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .grade-title-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .grade-feedback {
      font-size: 0.75rem;
      font-style: italic;
      color: var(--text-muted);
      margin: 0.2rem 0 0 0;
    }
    .grade-val {
      font-weight: 800;
      font-size: 0.95rem;
    }
    .section-block {
      margin-top: 2rem;
    }
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 1rem;
    }
    .section-header h2 {
      font-size: 1.35rem;
      margin-bottom: 0.15rem;
    }
    .section-sub {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin: 0;
    }
    .rec-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1.25rem;
    }
    .rec-card {
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 1.25rem;
    }
    .badge-row {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 0.5rem;
    }
    .rec-top h3 {
      font-size: 1.05rem;
      margin-bottom: 0.4rem;
    }
    .rec-desc {
      font-size: 0.85rem;
      color: var(--text-muted);
      line-height: 1.4;
      margin: 0;
    }
    .rec-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 1rem;
      padding-top: 0.75rem;
      border-top: 1px solid var(--border-light);
    }
    .inst-name {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .date-cell {
      font-size: 0.8rem;
      color: var(--text-muted);
      white-space: nowrap;
    }
    .empty-panel {
      text-align: center;
      padding: 2.5rem 1rem;
      color: var(--text-muted);
      font-size: 0.9rem;
    }
    .empty-icon {
      font-size: 2rem;
      display: block;
      margin-bottom: 0.5rem;
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
export class StudentDashboardComponent implements OnInit {
  data: EnhancedStudentDashboardResponse | null = null;
  isLoading = true;
  errorMessage = '';

  constructor(
    public auth: AuthService,
    private studentService: StudentService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadDashboard();
  }

  loadDashboard(): void {
    this.isLoading = true;
    this.errorMessage = '';

    this.studentService.getDashboard().subscribe({
      next: (res) => {
        this.data = res;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || 'Failed to load your learning dashboard.';
      }
    });
  }

  get activeCourseToContinue(): EnrolledCourseDetail | null {
    if (!this.data || this.data.enrolled_courses.length === 0) return null;
    // Prefer the first incomplete course with next_lesson_id
    const incomplete = this.data.enrolled_courses.find(c => c.status === 'in_progress' && c.next_lesson_id);
    return incomplete || this.data.enrolled_courses[0];
  }

  continueCourse(course: EnrolledCourseDetail): void {
    if (course.next_lesson_id) {
      this.router.navigate(['/courses', course.course_id, 'learn', course.next_lesson_id]);
    } else {
      // Fallback: request from backend continue endpoint
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
