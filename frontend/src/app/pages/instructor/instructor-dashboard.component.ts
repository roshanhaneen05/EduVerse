import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { InstructorService } from '../../core/services/instructor.service';
import { EnhancedInstructorDashboardStats } from '../../core/models/analytics.model';
import { Course } from '../../core/models/course.model';
import { InstructorEnrollment } from '../../core/models/enrollment.model';

@Component({
  selector: 'app-instructor-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="instructor-page">
      <div class="container">
        <!-- Header -->
        <div class="page-header">
          <div>
            <h1>Instructor Faculty Hub</h1>
            <p class="subtitle">Design courses, author curriculum lessons, configure assessments, and inspect learner progress.</p>
          </div>
          <a routerLink="/instructor/courses/new" class="btn btn-primary btn-lg">
            + Create New Course
          </a>
        </div>

        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading faculty metrics...</span>
          </div>
        } @else if (errorMessage) {
          <div class="card error-card">
            <h3>Unable to load dashboard</h3>
            <p>{{ errorMessage }}</p>
            <button (click)="fetchData()" class="btn btn-primary">Retry</button>
          </div>
        } @else {
          <!-- Stats Grid -->
          @if (stats) {
            <div class="stats-grid">
              <div class="stat-card card">
                <div class="stat-icon icon-blue">📚</div>
                <div class="stat-info">
                  <span class="stat-val">{{ stats.total_courses }}</span>
                  <span class="stat-label">Total Courses</span>
                  <span class="stat-sub">{{ stats.published_courses }} published</span>
                </div>
              </div>

              <div class="stat-card card">
                <div class="stat-icon icon-amber">👥</div>
                <div class="stat-info">
                  <span class="stat-val">{{ stats.total_students_enrolled }}</span>
                  <span class="stat-label">Total Enrollments</span>
                  <span class="stat-sub">{{ stats.unique_students_count }} unique learners</span>
                </div>
              </div>

              <div class="stat-card card">
                <div class="stat-icon icon-indigo">📝</div>
                <div class="stat-info">
                  <span class="stat-val">{{ stats.total_assignments }}</span>
                  <span class="stat-label">Active Assignments</span>
                  <span class="stat-sub">
                    @if (stats.pending_grading_count > 0) {
                      <strong class="pending-warn">{{ stats.pending_grading_count }} pending grading</strong>
                    } @else {
                      {{ stats.total_assignment_submissions }} submissions
                    }
                  </span>
                </div>
              </div>

              <div class="stat-card card">
                <div class="stat-icon icon-green">🎯</div>
                <div class="stat-info">
                  <span class="stat-val">{{ stats.average_quiz_score }}%</span>
                  <span class="stat-label">Avg Quiz Score</span>
                  <span class="stat-sub">{{ stats.total_quiz_attempts }} total attempts</span>
                </div>
              </div>

              <div class="stat-card card">
                <div class="stat-icon icon-purple">📊</div>
                <div class="stat-info">
                  <span class="stat-val">{{ stats.average_student_progress }}%</span>
                  <span class="stat-label">Avg Progress</span>
                  <span class="stat-sub">{{ stats.course_completion_rate }}% completion rate</span>
                </div>
              </div>
            </div>
          }

          <!-- Managed Courses List -->
          <div class="section-block">
            <div class="section-header">
              <h2>My Managed Courses</h2>
              <span class="badge badge-neutral">{{ myCourses.length }} Courses</span>
            </div>

            @if (myCourses.length === 0) {
              <div class="empty-block card">
                <h3>No courses created yet</h3>
                <p>Get started by creating your first course and adding learning materials.</p>
                <a routerLink="/instructor/courses/new" class="btn btn-primary">Create Course Now</a>
              </div>
            } @else {
              <div class="table-container card">
                <table>
                  <thead>
                    <tr>
                      <th>Course Title</th>
                      <th>Category</th>
                      <th>Level</th>
                      <th>Status</th>
                      <th>Curriculum</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (course of myCourses; track course.id) {
                      <tr>
                        <td>
                          <strong>{{ course.title }}</strong>
                        </td>
                        <td>{{ course.category }}</td>
                        <td>
                          <span class="badge" [ngClass]="getDifficultyBadge(course.difficulty)">
                            {{ course.difficulty }}
                          </span>
                        </td>
                        <td>
                          <span class="badge" [ngClass]="course.is_published ? 'badge-success' : 'badge-warning'">
                            {{ course.is_published ? 'Published' : 'Draft / Unpublished' }}
                          </span>
                        </td>
                        <td>
                          <span class="curriculum-summary">
                            {{ course.lesson_count }} lessons, {{ course.quiz_count }} quizzes
                          </span>
                        </td>
                        <td>
                          <div class="action-buttons">
                            <a [routerLink]="['/instructor/courses', course.id, 'analytics']" class="btn btn-sm btn-primary" title="Course Analytics & Student Reports">
                              Analytics
                            </a>
                            <a [routerLink]="['/instructor/courses', course.id, 'edit']" class="btn btn-sm btn-secondary" title="Edit details">
                              Edit
                            </a>
                            <a [routerLink]="['/instructor/courses', course.id, 'lessons']" class="btn btn-sm btn-outline" title="Manage Lessons">
                              Lessons
                            </a>
                            <a [routerLink]="['/instructor/courses', course.id, 'quizzes']" class="btn btn-sm btn-outline" title="Manage Quizzes">
                              Quizzes
                            </a>
                            <a [routerLink]="['/instructor/courses', course.id, 'assignments']" class="btn btn-sm btn-outline" title="Manage Assignments & Grading">
                              Assignments
                            </a>
                            <a [routerLink]="['/instructor/courses', course.id, 'materials']" class="btn btn-sm btn-outline" title="Manage Learning Materials">
                              Materials
                            </a>
                            <button (click)="togglePublish(course)" class="btn btn-sm" [ngClass]="course.is_published ? 'btn-secondary' : 'btn-outline'">
                              {{ course.is_published ? 'Unpublish' : 'Publish' }}
                            </button>
                          </div>
                        </td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            }
          </div>

          <div class="section-block">
            <div class="section-header">
              <h2>Student Enrollments</h2>
              <span class="badge badge-neutral">{{ enrollments.length }} Students</span>
            </div>

            @if (enrollments.length === 0) {
              <div class="empty-block card">
                <h3>No student enrollments yet</h3>
                <p>Student enrollments in your courses will appear here.</p>
              </div>
            } @else {
              <div class="table-container card">
                <table>
                  <thead>
                    <tr>
                      <th>Student Name</th>
                      <th>Email</th>
                      <th>Course</th>
                      <th>Enrollment Date</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (enr of enrollments; track enr.enrollment_id) {
                      <tr>
                        <td><strong>{{ enr.student_name }}</strong></td>
                        <td>{{ enr.student_email }}</td>
                        <td>{{ enr.course_name }}</td>
                        <td>{{ enr.enrolled_at | date:'short' }}</td>
                        <td>
                          <span class="badge" [ngClass]="enr.status === 'completed' ? 'badge-success' : 'badge-primary'">
                            {{ enr.status === 'completed' ? 'Completed' : 'Active' }}
                          </span>
                        </td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            }
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .instructor-page {
      padding: 2.5rem 0 4rem 0;
      min-height: calc(100vh - 120px);
    }
    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      flex-wrap: wrap;
      gap: 1.25rem;
    }
    .page-header h1 {
      font-size: 2.25rem;
      color: #0f172a;
      font-weight: 800;
      letter-spacing: -0.02em;
    }
    .subtitle {
      color: var(--text-muted);
      margin-top: 0.35rem;
      font-size: 1.05rem;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 1.35rem;
      margin-bottom: 2.5rem;
    }
    .stat-card {
      padding: 1.5rem;
      display: flex;
      align-items: center;
      gap: 1.25rem;
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 6px 20px -3px rgba(99, 102, 241, 0.06);
    }
    .stat-icon {
      width: 52px;
      height: 52px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.6rem;
      flex-shrink: 0;
    }
    .icon-blue { background-color: #ede9fe; }
    .icon-amber { background-color: #fef3c7; }
    .icon-indigo { background-color: #e0e7ff; }
    .icon-green { background-color: #ecfdf5; }
    .icon-purple { background-color: #f5f3ff; }
    .stat-info {
      display: flex;
      flex-direction: column;
      gap: 0.15rem;
    }
    .stat-val {
      font-size: 1.85rem;
      font-weight: 800;
      color: #0f172a;
    }
    .stat-label {
      font-size: 0.85rem;
      color: var(--text-muted);
      font-weight: 600;
    }
    .stat-sub {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .pending-warn {
      color: #b45309;
      font-weight: 700;
    }
    .section-block {
      margin-bottom: 2.5rem;
    }
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
    }
    .table-container {
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }
    th {
      padding: 0.85rem 1rem;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border-light);
    }
    td {
      padding: 0.85rem 1rem;
      border-bottom: 1px solid var(--border-light);
      font-size: 0.9rem;
      vertical-align: middle;
    }
    .action-buttons {
      display: flex;
      gap: 0.4rem;
      flex-wrap: wrap;
    }
    .table-progress {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      min-width: 110px;
    }
    .mini-bar {
      flex: 1;
      height: 6px;
      background-color: var(--border-light);
      border-radius: var(--radius-full);
      overflow: hidden;
    }
    .mini-fill {
      height: 100%;
      background: linear-gradient(90deg, var(--primary) 0%, #3b82f6 100%);
      border-radius: var(--radius-full);
    }
    .curriculum-summary {
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .empty-block {
      padding: 4rem 2rem;
      text-align: center;
      max-width: 580px;
      margin: 2rem auto;
    }
    .empty-block h3 {
      margin-bottom: 0.5rem;
    }
    .empty-block p {
      color: var(--text-muted);
      margin-bottom: 1.5rem;
    }
    .error-card {
      padding: 3rem 2rem;
      text-align: center;
      max-width: 500px;
      margin: 3rem auto;
    }
    .error-card h3 {
      color: var(--danger);
      margin-bottom: 0.5rem;
    }
    .error-card p {
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
export class InstructorDashboardComponent implements OnInit {
  stats: EnhancedInstructorDashboardStats | null = null;
  myCourses: Course[] = [];
  enrollments: InstructorEnrollment[] = [];
  isLoading = true;
  errorMessage = '';

  constructor(private instructorService: InstructorService) {}

  ngOnInit(): void {
    this.fetchData();
  }

  fetchData(): void {
    this.isLoading = true;
    this.errorMessage = '';

    this.instructorService.getDashboard().subscribe({
      next: (statsData) => {
        this.stats = statsData;
        this.instructorService.getMyCourses().subscribe({
          next: (courses) => {
            this.myCourses = courses;
            this.instructorService.getStudentEnrollments().subscribe({
              next: (enrollments) => {
                this.enrollments = enrollments;
                this.isLoading = false;
              },
              error: (err) => {
                this.isLoading = false;
                this.errorMessage = err.error?.detail || 'Failed to load student enrollments.';
              }
            });
          },
          error: (err) => {
            this.isLoading = false;
            this.errorMessage = err.error?.detail || 'Failed to load managed courses.';
          }
        });
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || 'Failed to load faculty metrics.';
      }
    });
  }

  togglePublish(course: Course): void {
    this.instructorService.togglePublish(course.id).subscribe({
      next: (updated) => {
        course.is_published = updated.is_published;
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
