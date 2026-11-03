import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { StudentService } from '../../core/services/student.service';
import { StudentAssignmentOverviewItem } from '../../core/models/student.model';

@Component({
  selector: 'app-student-assignments',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="assignments-page">
      <div class="container">
        <!-- Sub-Navigation Bar -->
        <div class="student-nav-bar">
          <a routerLink="/student/dashboard" class="nav-pill">Overview</a>
          <a routerLink="/student/my-learning" class="nav-pill">My Learning</a>
          <a routerLink="/student/assignments" class="nav-pill active">Assignments & Tasks</a>
          <a routerLink="/student/quiz-history" class="nav-pill">Assessment History</a>
        </div>

        <!-- Header -->
        <div class="page-header">
          <div>
            <h1>Assignments & Practical Tasks</h1>
            <p class="subtitle">Review assigned practical coursework, deadlines, submission statuses, and faculty grades.</p>
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
              All Tasks ({{ assignments.length }})
            </button>
            <button
              (click)="setFilter('pending')"
              class="filter-btn"
              [class.active]="currentFilter === 'pending'"
            >
              To Do / Pending ({{ pendingCount }})
            </button>
            <button
              (click)="setFilter('submitted')"
              class="filter-btn"
              [class.active]="currentFilter === 'submitted'"
            >
              Submitted ({{ submittedCount }})
            </button>
            <button
              (click)="setFilter('graded')"
              class="filter-btn"
              [class.active]="currentFilter === 'graded'"
            >
              Graded ({{ gradedCount }})
            </button>
            <button
              (click)="setFilter('past_due')"
              class="filter-btn"
              [class.active]="currentFilter === 'past_due'"
            >
              Past Due ({{ pastDueCount }})
            </button>
          </div>
        </div>

        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading course assignments...</span>
          </div>
        } @else if (filteredAssignments.length === 0) {
          <div class="empty-block card">
            <div class="empty-icon">📝</div>
            <h3>No assignments found</h3>
            <p>
              @if (currentFilter === 'pending') {
                Great job! You have no pending assignments to submit.
              } @else if (currentFilter === 'graded') {
                No assignments have received grades yet.
              } @else if (currentFilter === 'submitted') {
                You have not submitted any assignments awaiting review.
              } @else {
                There are no published assignments in your enrolled courses yet.
              }
            </p>
          </div>
        } @else {
          <div class="table-container card">
            <table>
              <thead>
                <tr>
                  <th>Assignment Title</th>
                  <th>Course</th>
                  <th>Deadline</th>
                  <th>Max Marks</th>
                  <th>Status</th>
                  <th>Grade & Feedback</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                @for (a of filteredAssignments; track a.assignment_id) {
                  <tr>
                    <td>
                      <div class="title-cell">
                        <strong>{{ a.assignment_title }}</strong>
                        @if (a.is_closed) {
                          <span class="closed-tag">Closed</span>
                        }
                      </div>
                    </td>
                    <td>
                      <span class="course-text">{{ a.course_title }}</span>
                    </td>
                    <td>
                      @if (a.due_date) {
                        <span class="due-text">{{ a.due_date | date:'mediumDate' }}</span>
                      } @else {
                        <span class="text-muted">No deadline</span>
                      }
                    </td>
                    <td>{{ a.max_marks }} pts</td>
                    <td>
                      <span class="badge" [ngClass]="getStatusBadge(a.submission_status)">
                        {{ formatStatus(a.submission_status) }}
                      </span>
                      @if (a.is_late) {
                        <span class="badge badge-warning">Late</span>
                      }
                    </td>
                    <td>
                      @if (a.grade !== null && a.grade !== undefined) {
                        <div class="grade-cell">
                          <strong class="grade-num">{{ a.grade }} / {{ a.max_marks }}</strong>
                          @if (a.feedback) {
                            <span class="feedback-sub" [title]="a.feedback">"{{ a.feedback | slice:0:35 }}..."</span>
                          }
                        </div>
                      } @else if (a.submission_status === 'submitted') {
                        <span class="text-muted awaiting-text">Awaiting instructor evaluation</span>
                      } @else {
                        <span class="text-muted">—</span>
                      }
                    </td>
                    <td>
                      <a
                        [routerLink]="['/courses', a.course_id, 'assignments', a.assignment_id]"
                        class="btn btn-sm"
                        [ngClass]="a.submission_status === 'not_submitted' ? 'btn-primary' : 'btn-outline'"
                      >
                        {{ a.submission_status === 'not_submitted' ? 'Submit Work' : 'View Submission' }} →
                      </a>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .assignments-page {
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
      margin-bottom: 1.75rem;
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
    .title-cell {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .closed-tag {
      font-size: 0.7rem;
      background: #fee2e2;
      color: #991b1b;
      padding: 0.1rem 0.4rem;
      border-radius: var(--radius-sm);
    }
    .course-text {
      font-size: 0.9rem;
    }
    .due-text {
      font-size: 0.85rem;
      color: var(--text-muted);
      white-space: nowrap;
    }
    .grade-cell {
      display: flex;
      flex-direction: column;
    }
    .grade-num {
      font-size: 0.95rem;
      color: var(--primary);
    }
    .feedback-sub {
      font-size: 0.75rem;
      color: var(--text-muted);
      font-style: italic;
    }
    .awaiting-text {
      font-size: 0.8rem;
    }
    .empty-block {
      text-align: center;
      padding: 4rem 2rem;
    }
    .empty-icon {
      font-size: 3rem;
      margin-bottom: 1rem;
    }
    .empty-block h3 {
      font-size: 1.4rem;
      margin-bottom: 0.5rem;
    }
    .empty-block p {
      color: var(--text-muted);
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
export class StudentAssignmentsComponent implements OnInit {
  assignments: StudentAssignmentOverviewItem[] = [];
  currentFilter: 'all' | 'pending' | 'submitted' | 'graded' | 'past_due' = 'all';
  isLoading = true;
  feedbackMessage = '';

  constructor(private studentService: StudentService) {}

  ngOnInit(): void {
    this.loadAssignments();
  }

  loadAssignments(): void {
    this.isLoading = true;
    this.studentService.getAssignments('all').subscribe({
      next: (list) => {
        this.assignments = list;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.feedbackMessage = err.error?.detail || 'Failed to load assignments.';
      }
    });
  }

  setFilter(filter: 'all' | 'pending' | 'submitted' | 'graded' | 'past_due'): void {
    this.currentFilter = filter;
  }

  get filteredAssignments(): StudentAssignmentOverviewItem[] {
    if (this.currentFilter === 'pending') {
      return this.assignments.filter(a => a.submission_status === 'not_submitted');
    }
    if (this.currentFilter === 'submitted') {
      return this.assignments.filter(a => a.submission_status === 'submitted');
    }
    if (this.currentFilter === 'graded') {
      return this.assignments.filter(a => a.submission_status === 'graded');
    }
    if (this.currentFilter === 'past_due') {
      return this.assignments.filter(a => a.submission_status === 'past_due');
    }
    return this.assignments;
  }

  get pendingCount(): number {
    return this.assignments.filter(a => a.submission_status === 'not_submitted').length;
  }

  get submittedCount(): number {
    return this.assignments.filter(a => a.submission_status === 'submitted').length;
  }

  get gradedCount(): number {
    return this.assignments.filter(a => a.submission_status === 'graded').length;
  }

  get pastDueCount(): number {
    return this.assignments.filter(a => a.submission_status === 'past_due').length;
  }

  getStatusBadge(status: string): string {
    switch (status) {
      case 'graded': return 'badge-success';
      case 'submitted': return 'badge-primary';
      case 'past_due': return 'badge-danger';
      case 'not_submitted': return 'badge-warning';
      default: return 'badge-neutral';
    }
  }

  formatStatus(status: string): string {
    switch (status) {
      case 'graded': return 'Graded';
      case 'submitted': return 'Submitted';
      case 'past_due': return 'Past Due';
      case 'not_submitted': return 'To Do';
      default: return status;
    }
  }
}

