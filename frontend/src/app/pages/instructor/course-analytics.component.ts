import { Component, OnInit, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { InstructorService } from '../../core/services/instructor.service';
import {
  CourseAnalyticsResponse,
  CourseStudentReportResponse,
  StudentDetailedProgressResponse,
  StudentPerformanceItem,
} from '../../core/models/analytics.model';

@Component({
  selector: 'app-course-analytics',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="analytics-page">
      <div class="container">
        <!-- Top Navigation & Header -->
        <div class="page-header">
          <div>
            <a routerLink="/instructor/dashboard" class="back-link">← Back to Instructor Hub</a>
            <div class="title-row">
              <h1>Course Analytics & Student Reports</h1>
              @if (analytics) {
                <span class="badge" [ngClass]="analytics.is_published ? 'badge-success' : 'badge-warning'">
                  {{ analytics.is_published ? 'Published' : 'Draft' }}
                </span>
              }
            </div>
            <p class="subtitle" *ngIf="analytics">
              Course: <strong>{{ analytics.course_title }}</strong> · {{ analytics.category }} · {{ analytics.difficulty }}
            </p>
          </div>

          <div class="header-actions" *ngIf="analytics">
            <button (click)="exportCsv()" class="btn btn-outline" [disabled]="isExporting">
              @if (isExporting) {
                <span>Exporting CSV...</span>
              } @else {
                <span>⬇ Export Student Report (CSV)</span>
              }
            </button>
            <a [routerLink]="['/instructor/courses', courseId, 'edit']" class="btn btn-secondary">
              Edit Course
            </a>
          </div>
        </div>

        @if (feedbackMessage) {
          <div class="alert" [ngClass]="isError ? 'alert-danger' : 'alert-success'">
            {{ feedbackMessage }}
          </div>
        }

        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Aggregating course analytics & student performance data...</span>
          </div>
        } @else if (errorMessage) {
          <div class="card error-card">
            <h3>Unable to load analytics</h3>
            <p>{{ errorMessage }}</p>
            <button (click)="loadAllData()" class="btn btn-primary">Try Again</button>
          </div>
        } @else if (analytics) {
          <!-- High-Level Course KPI Metrics -->
          <div class="kpi-grid">
            <div class="kpi-card card">
              <div class="kpi-icon icon-blue">👥</div>
              <div class="kpi-info">
                <span class="kpi-val">{{ analytics.total_students }}</span>
                <span class="kpi-label">Enrolled Students</span>
                <span class="kpi-sub">{{ analytics.completed_students_count }} completed ({{ analytics.course_completion_rate }}%)</span>
              </div>
            </div>

            <div class="kpi-card card">
              <div class="kpi-icon icon-indigo">📈</div>
              <div class="kpi-info">
                <span class="kpi-val">{{ analytics.average_completion_percentage }}%</span>
                <span class="kpi-label">Average Progress</span>
                <div class="mini-progress-bar">
                  <div class="mini-fill" [style.width.%]="analytics.average_completion_percentage"></div>
                </div>
              </div>
            </div>

            <div class="kpi-card card">
              <div class="kpi-icon icon-amber">📝</div>
              <div class="kpi-info">
                <span class="kpi-val">{{ analytics.total_assignment_submissions }}</span>
                <span class="kpi-label">Assignment Submissions</span>
                <span class="kpi-sub">
                  @if (analytics.pending_grading_count > 0) {
                    <strong class="pending-warn">{{ analytics.pending_grading_count }} pending grading</strong>
                  } @else {
                    All submissions graded
                  }
                </span>
              </div>
            </div>

            <div class="kpi-card card">
              <div class="kpi-icon icon-green">🎯</div>
              <div class="kpi-info">
                <span class="kpi-val">{{ analytics.average_quiz_score }}%</span>
                <span class="kpi-label">Average Quiz Score</span>
                <span class="kpi-sub">{{ analytics.quiz_pass_rate }}% attempt pass rate ({{ analytics.total_quiz_attempts }} attempts)</span>
              </div>
            </div>
          </div>

          <!-- Tabs Navigation -->
          <div class="tabs-bar">
            <button
              class="tab-btn"
              [class.active]="activeTab === 'roster'"
              (click)="activeTab = 'roster'"
            >
              Student Roster & Performance ({{ report?.students?.length || 0 }})
            </button>
            <button
              class="tab-btn"
              [class.active]="activeTab === 'curriculum'"
              (click)="activeTab = 'curriculum'"
            >
              Curriculum & Assessment Breakdown
            </button>
          </div>

          <!-- Tab 1: Student Performance Roster -->
          @if (activeTab === 'roster') {
            <div class="roster-section card">
              <div class="roster-toolbar">
                <div class="search-box">
                  <input
                    type="text"
                    class="form-input"
                    placeholder="Search by student name or email..."
                    [(ngModel)]="searchQuery"
                  />
                </div>

                <div class="filter-group">
                  <label class="filter-label">Status Filter:</label>
                  <select class="form-input filter-select" [(ngModel)]="statusFilter">
                    <option value="ALL">All Students ({{ report?.students?.length || 0 }})</option>
                    <option value="Completed">Completed</option>
                    <option value="In Progress">In Progress</option>
                    <option value="Needs Attention">Needs Attention</option>
                  </select>
                </div>
              </div>

              @if (filteredStudents.length === 0) {
                <div class="empty-roster">
                  @if (report && report.students.length === 0) {
                    <p>No students have enrolled in this course yet.</p>
                  } @else {
                    <p>No students match the selected filter criteria.</p>
                  }
                </div>
              } @else {
                <div class="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Student</th>
                        <th>Enrolled Date</th>
                        <th>Progress</th>
                        <th>Lessons</th>
                        <th>Assignments</th>
                        <th>Quizzes</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      @for (s of filteredStudents; track s.student_id) {
                        <tr>
                          <td>
                            <div class="student-cell">
                              <strong>{{ s.full_name }}</strong>
                              <span class="student-email">{{ s.email }}</span>
                            </div>
                          </td>
                          <td>{{ s.enrolled_at | date:'mediumDate' }}</td>
                          <td>
                            <div class="progress-cell">
                              <span>{{ s.completion_percentage }}%</span>
                              <div class="mini-bar">
                                <div class="mini-fill" [style.width.%]="s.completion_percentage"></div>
                              </div>
                            </div>
                          </td>
                          <td>
                            <span>{{ s.completed_lessons_count }} / {{ s.total_lessons_count }}</span>
                          </td>
                          <td>
                            <div class="sub-metric">
                              <span>{{ s.assignments_submitted_count }} / {{ s.total_assignments_count }} sub</span>
                              @if (s.average_assignment_grade !== null && s.average_assignment_grade !== undefined) {
                                <span class="badge badge-neutral badge-xs">{{ s.average_assignment_grade }}% avg</span>
                              }
                            </div>
                          </td>
                          <td>
                            <div class="sub-metric">
                              <span>{{ s.quizzes_taken_count }} / {{ s.total_quizzes_count }} taken</span>
                              @if (s.average_quiz_score !== null && s.average_quiz_score !== undefined) {
                                <span class="badge badge-neutral badge-xs">{{ s.average_quiz_score }}% score</span>
                              }
                            </div>
                          </td>
                          <td>
                            <div class="status-cell">
                              <span class="badge" [ngClass]="getStatusBadge(s.status)">
                                {{ s.status }}
                              </span>
                              @if (s.status === 'Needs Attention' && s.assistance_reasons.length > 0) {
                                <span class="reasons-tooltip" [title]="s.assistance_reasons.join(', ')">
                                  ⚠️ {{ s.assistance_reasons.length }} alert(s)
                                </span>
                              }
                            </div>
                          </td>
                          <td>
                            <button
                              (click)="inspectStudent(s.student_id)"
                              class="btn btn-sm btn-outline"
                              title="Inspect full lesson, assignment, and quiz activity"
                            >
                              Inspect Details
                            </button>
                          </td>
                        </tr>
                      }
                    </tbody>
                  </table>
                </div>
              }
            </div>
          }

          <!-- Tab 2: Curriculum & Assessment Breakdown -->
          @if (activeTab === 'curriculum') {
            <div class="curriculum-breakdown-grid">
              <!-- Assignments Analytics Card -->
              <div class="card breakdown-card">
                <div class="card-header">
                  <h3>Assignments & Practical Tasks ({{ analytics.assignments_breakdown.length }})</h3>
                  <span class="sub-note">Submission rate: {{ analytics.assignment_submission_rate }}%</span>
                </div>

                @if (analytics.assignments_breakdown.length === 0) {
                  <p class="empty-note">No assignments created for this course yet.</p>
                } @else {
                  <div class="breakdown-list">
                    @for (a of analytics.assignments_breakdown; track a.assignment_id) {
                      <div class="breakdown-item">
                        <div class="item-meta">
                          <strong>{{ a.title }}</strong>
                          <span class="sub-note">Max Marks: {{ a.max_marks }} · Due: {{ a.due_date ? (a.due_date | date:'short') : 'No deadline' }}</span>
                        </div>
                        <div class="item-stats">
                          <span class="badge badge-neutral">{{ a.total_submissions }} Submissions</span>
                          @if (a.pending_grading > 0) {
                            <span class="badge badge-warning">{{ a.pending_grading }} Pending</span>
                          }
                          @if (a.average_grade !== null && a.average_grade !== undefined) {
                            <span class="badge badge-success">Avg: {{ a.average_grade }}%</span>
                          }
                        </div>
                      </div>
                    }
                  </div>
                }
              </div>

              <!-- Quizzes Analytics Card -->
              <div class="card breakdown-card">
                <div class="card-header">
                  <h3>Assessment Quizzes ({{ analytics.quizzes_breakdown.length }})</h3>
                  <span class="sub-note">Total Attempts: {{ analytics.total_quiz_attempts }}</span>
                </div>

                @if (analytics.quizzes_breakdown.length === 0) {
                  <p class="empty-note">No quizzes created for this course yet.</p>
                } @else {
                  <div class="breakdown-list">
                    @for (q of analytics.quizzes_breakdown; track q.quiz_id) {
                      <div class="breakdown-item">
                        <div class="item-meta">
                          <strong>{{ q.quiz_title }}</strong>
                          <span class="sub-note">Passing: {{ q.passing_score }}% · {{ q.total_questions }} Questions · {{ q.time_limit_minutes ? q.time_limit_minutes + ' min' : 'Untimed' }}</span>
                        </div>
                        <div class="item-stats">
                          <span class="badge badge-neutral">{{ q.total_attempts }} Attempts ({{ q.unique_students_attempted }} learners)</span>
                          <span class="badge" [ngClass]="q.pass_rate >= 70 ? 'badge-success' : 'badge-warning'">
                            Pass: {{ q.pass_rate }}%
                          </span>
                          <span class="badge badge-primary">Avg: {{ q.average_score }}%</span>
                        </div>
                      </div>
                    }
                  </div>
                }
              </div>
            </div>
          }
        }

        <!-- Student Progress Detail Modal -->
        @if (selectedStudentProgress) {
          <div class="modal-backdrop" (click)="closeStudentModal()">
            <div class="modal-card card" (click)="$event.stopPropagation()">
              <div class="modal-header">
                <div>
                  <span class="badge badge-primary">Learner Performance Profile</span>
                  <h2>{{ selectedStudentProgress.full_name }}</h2>
                  <span class="modal-sub">{{ selectedStudentProgress.email }} · Enrolled {{ selectedStudentProgress.enrolled_at | date:'mediumDate' }}</span>
                </div>
                <button (click)="closeStudentModal()" class="close-modal-btn">✕</button>
              </div>

              <div class="modal-body">
                <!-- Summary Chips -->
                <div class="student-kpi-bar">
                  <div class="chip">
                    <span class="chip-label">Progress:</span>
                    <strong>{{ selectedStudentProgress.completion_percentage }}%</strong>
                  </div>
                  <div class="chip">
                    <span class="chip-label">Lessons:</span>
                    <strong>{{ selectedStudentProgress.completed_lessons }} / {{ selectedStudentProgress.total_lessons }}</strong>
                  </div>
                  <div class="chip">
                    <span class="chip-label">Assignments:</span>
                    <strong>{{ selectedStudentProgress.submitted_assignments }} / {{ selectedStudentProgress.total_assignments }}</strong>
                  </div>
                  <div class="chip">
                    <span class="chip-label">Avg Quiz Score:</span>
                    <strong>{{ selectedStudentProgress.average_quiz_score !== null ? selectedStudentProgress.average_quiz_score + '%' : 'N/A' }}</strong>
                  </div>
                </div>

                @if (selectedStudentProgress.assistance_reasons.length > 0) {
                  <div class="alert alert-warning">
                    <strong>Notice:</strong>
                    <ul>
                      @for (r of selectedStudentProgress.assistance_reasons; track r) {
                        <li>{{ r }}</li>
                      }
                    </ul>
                  </div>
                }

                <!-- Modal Sub-Tabs -->
                <div class="modal-section">
                  <h4>Curriculum Lessons ({{ selectedStudentProgress.lessons_progress.length }})</h4>
                  <div class="progress-items-list">
                    @for (l of selectedStudentProgress.lessons_progress; track l.lesson_id) {
                      <div class="progress-item-row">
                        <span class="status-icon" [class.done]="l.is_completed">{{ l.is_completed ? '✓' : '○' }}</span>
                        <div class="item-text">
                          <strong>{{ l.title }}</strong>
                          <span class="sub-note" *ngIf="l.section_title">Section: {{ l.section_title }}</span>
                        </div>
                        <span class="date-note" *ngIf="l.completed_at">{{ l.completed_at | date:'short' }}</span>
                      </div>
                    }
                  </div>
                </div>

                <!-- Assignment Submissions -->
                <div class="modal-section">
                  <h4>Assignments & Submissions ({{ selectedStudentProgress.assignment_submissions.length }})</h4>
                  @if (selectedStudentProgress.assignment_submissions.length === 0) {
                    <p class="empty-note">No assignments configured for this course.</p>
                  } @else {
                    <div class="progress-items-list">
                      @for (sub of selectedStudentProgress.assignment_submissions; track sub.assignment_id) {
                        <div class="progress-item-row">
                          <div class="item-text">
                            <strong>{{ sub.title }}</strong>
                            <span class="sub-note">Max Marks: {{ sub.max_marks }}</span>
                          </div>
                          <div class="sub-grade-pill">
                            @if (sub.status === 'not_submitted') {
                              <span class="badge badge-draft">Not Submitted</span>
                            } @else if (sub.status === 'submitted') {
                              <span class="badge badge-warning">Awaiting Grading</span>
                            } @else {
                              <span class="badge badge-success">{{ sub.grade }} / {{ sub.max_marks }} pts</span>
                            }
                          </div>
                        </div>
                      }
                    </div>
                  }
                </div>

                <!-- Quiz Attempts -->
                <div class="modal-section">
                  <h4>Assessment Quizzes ({{ selectedStudentProgress.quiz_attempts.length }} Attempts)</h4>
                  @if (selectedStudentProgress.quiz_attempts.length === 0) {
                    <p class="empty-note">No quiz attempts recorded for this learner.</p>
                  } @else {
                    <div class="progress-items-list">
                      @for (att of selectedStudentProgress.quiz_attempts; track att.attempt_id) {
                        <div class="progress-item-row">
                          <div class="item-text">
                            <strong>{{ att.title }}</strong>
                            <span class="sub-note">Attempt #{{ att.attempt_number }} · Submitted: {{ att.submitted_at | date:'short' }}</span>
                          </div>
                          <div class="sub-grade-pill">
                            <span class="badge" [ngClass]="att.passed ? 'badge-success' : 'badge-danger'">
                              {{ att.score }}% ({{ att.passed ? 'Passed' : 'Failed' }})
                            </span>
                          </div>
                        </div>
                      }
                    </div>
                  }
                </div>
              </div>

              <div class="modal-footer">
                <button (click)="closeStudentModal()" class="btn btn-secondary">Close</button>
              </div>
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .analytics-page {
      padding: 2.5rem 0 4rem 0;
      background-color: var(--bg-app);
      min-height: calc(100vh - 120px);
    }
    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 2rem;
      flex-wrap: wrap;
      gap: 1.5rem;
    }
    .back-link {
      font-size: 0.9rem;
      color: var(--text-muted);
      font-weight: 600;
      text-decoration: none;
    }
    .back-link:hover {
      color: var(--primary);
    }
    .title-row {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-top: 0.4rem;
    }
    .subtitle {
      color: var(--text-muted);
      font-size: 0.95rem;
      margin-top: 0.35rem;
    }
    .header-actions {
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2rem;
    }
    .kpi-card {
      padding: 1.5rem;
      display: flex;
      align-items: center;
      gap: 1.25rem;
    }
    .kpi-icon {
      width: 48px;
      height: 48px;
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.5rem;
      flex-shrink: 0;
    }
    .icon-blue { background-color: #eff6ff; }
    .icon-indigo { background-color: #eef2ff; }
    .icon-amber { background-color: #fffbeb; }
    .icon-green { background-color: #ecfdf5; }
    .kpi-info {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
      flex: 1;
    }
    .kpi-val {
      font-size: 1.65rem;
      font-weight: 800;
      color: var(--text-main);
    }
    .kpi-label {
      font-size: 0.85rem;
      color: var(--text-muted);
      font-weight: 600;
    }
    .kpi-sub {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .pending-warn {
      color: #b45309;
      font-weight: 700;
    }
    .mini-progress-bar {
      height: 6px;
      background-color: var(--border-light);
      border-radius: var(--radius-full);
      overflow: hidden;
      margin-top: 0.35rem;
    }
    .mini-fill {
      height: 100%;
      background: linear-gradient(90deg, var(--primary) 0%, #3b82f6 100%);
      border-radius: var(--radius-full);
    }
    .tabs-bar {
      display: flex;
      gap: 0.5rem;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 1.5rem;
    }
    .tab-btn {
      padding: 0.75rem 1.25rem;
      background: none;
      border: none;
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--text-muted);
      cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: var(--transition);
    }
    .tab-btn:hover {
      color: var(--primary);
    }
    .tab-btn.active {
      color: var(--primary);
      border-bottom-color: var(--primary);
    }
    .roster-section {
      padding: 1.5rem;
    }
    .roster-toolbar {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.5rem;
      flex-wrap: wrap;
    }
    .search-box {
      flex: 1;
      min-width: 260px;
    }
    .filter-group {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .filter-label {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-muted);
    }
    .filter-select {
      width: auto;
      min-width: 160px;
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
    .student-cell {
      display: flex;
      flex-direction: column;
      gap: 0.15rem;
    }
    .student-email {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .progress-cell {
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
    .sub-metric {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
      font-size: 0.85rem;
    }
    .badge-xs {
      font-size: 0.7rem;
      padding: 0.1rem 0.35rem;
      width: fit-content;
    }
    .status-cell {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }
    .reasons-tooltip {
      font-size: 0.7rem;
      color: #b45309;
      font-weight: 600;
      cursor: help;
    }
    .badge-draft {
      background-color: #f3f4f6;
      color: #6b7280;
    }
    .curriculum-breakdown-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 1.5rem;
    }
    .breakdown-card {
      padding: 1.75rem;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
      border-bottom: 1px solid var(--border-light);
      padding-bottom: 0.75rem;
    }
    .sub-note {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .empty-note {
      font-size: 0.9rem;
      color: var(--text-muted);
      padding: 1.5rem 0;
    }
    .breakdown-list {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .breakdown-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.85rem 1rem;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      background-color: var(--bg-subtle);
      gap: 1rem;
      flex-wrap: wrap;
    }
    .item-meta {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }
    .item-stats {
      display: flex;
      gap: 0.4rem;
      flex-wrap: wrap;
    }
    .modal-backdrop {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background-color: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      padding: 1.5rem;
    }
    .modal-card {
      max-width: 680px;
      width: 100%;
      max-height: 85vh;
      overflow-y: auto;
      padding: 2rem;
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1.5rem;
      border-bottom: 1px solid var(--border-light);
      padding-bottom: 1rem;
    }
    .modal-sub {
      font-size: 0.85rem;
      color: var(--text-muted);
      display: block;
      margin-top: 0.25rem;
    }
    .close-modal-btn {
      background: none;
      border: none;
      font-size: 1.25rem;
      cursor: pointer;
      color: var(--text-muted);
    }
    .student-kpi-bar {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 0.75rem;
      margin-bottom: 1.5rem;
      background-color: var(--bg-subtle);
      padding: 0.75rem 1rem;
      border-radius: var(--radius-md);
    }
    .chip {
      display: flex;
      flex-direction: column;
      gap: 0.15rem;
    }
    .chip-label {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .modal-section {
      margin-top: 1.5rem;
      border-top: 1px solid var(--border-light);
      padding-top: 1rem;
    }
    .modal-section h4 {
      margin-bottom: 0.75rem;
      font-size: 0.95rem;
    }
    .progress-items-list {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .progress-item-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      padding: 0.5rem 0.75rem;
      border-radius: var(--radius-sm);
      background-color: var(--bg-subtle);
      font-size: 0.85rem;
    }
    .status-icon {
      font-weight: 700;
      color: var(--text-muted);
    }
    .status-icon.done {
      color: var(--success);
    }
    .item-text {
      display: flex;
      flex-direction: column;
      flex: 1;
    }
    .date-note {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .modal-footer {
      display: flex;
      justify-content: flex-end;
      margin-top: 1.5rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border-light);
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
export class CourseAnalyticsComponent implements OnInit {
  @Input() id!: string; // course_id

  get courseId(): number {
    return Number(this.id);
  }

  analytics: CourseAnalyticsResponse | null = null;
  report: CourseStudentReportResponse | null = null;
  selectedStudentProgress: StudentDetailedProgressResponse | null = null;

  isLoading = true;
  isExporting = false;
  errorMessage = '';
  feedbackMessage = '';
  isError = false;

  activeTab: 'roster' | 'curriculum' = 'roster';
  searchQuery = '';
  statusFilter = 'ALL';

  constructor(
    private instructorService: InstructorService,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    if (!this.id) {
      this.id = this.route.snapshot.paramMap.get('id') || '';
    }
    if (this.id) {
      this.loadAllData();
    }
  }

  loadAllData(): void {
    this.isLoading = true;
    this.errorMessage = '';

    this.instructorService.getCourseAnalytics(this.courseId).subscribe({
      next: (analyticsData) => {
        this.analytics = analyticsData;
        this.loadRoster();
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || 'Failed to load course analytics.';
      }
    });
  }

  loadRoster(): void {
    this.instructorService.getCourseStudentReport(this.courseId).subscribe({
      next: (reportData) => {
        this.report = reportData;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || 'Failed to load student performance report.';
      }
    });
  }

  get filteredStudents(): StudentPerformanceItem[] {
    if (!this.report?.students) return [];

    return this.report.students.filter((s) => {
      const matchesSearch =
        !this.searchQuery.trim() ||
        s.full_name.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
        s.email.toLowerCase().includes(this.searchQuery.toLowerCase());

      const matchesStatus =
        this.statusFilter === 'ALL' || s.status === this.statusFilter;

      return matchesSearch && matchesStatus;
    });
  }

  getStatusBadge(status: string): string {
    switch (status) {
      case 'Completed': return 'badge-success';
      case 'In Progress': return 'badge-primary';
      case 'Needs Attention': return 'badge-warning';
      default: return 'badge-neutral';
    }
  }

  inspectStudent(studentId: number): void {
    this.instructorService.getStudentDetailedProgress(this.courseId, studentId).subscribe({
      next: (data) => {
        this.selectedStudentProgress = data;
      },
      error: (err) => {
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to load student progress.';
      }
    });
  }

  closeStudentModal(): void {
    this.selectedStudentProgress = null;
  }

  exportCsv(): void {
    this.isExporting = true;
    this.instructorService.exportCourseStudentReportCsv(this.courseId).subscribe({
      next: (blob) => {
        this.isExporting = false;
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `course_${this.courseId}_student_report.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
      },
      error: (err) => {
        this.isExporting = false;
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to export CSV report.';
      }
    });
  }
}
