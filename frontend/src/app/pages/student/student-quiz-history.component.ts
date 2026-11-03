import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { StudentService } from '../../core/services/student.service';
import { StudentQuizHistoryItem } from '../../core/models/student.model';

@Component({
  selector: 'app-student-quiz-history',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="history-page">
      <div class="container">
        <!-- Sub-Navigation Bar -->
        <div class="student-nav-bar">
          <a routerLink="/student/dashboard" class="nav-pill">Overview</a>
          <a routerLink="/student/my-learning" class="nav-pill">My Learning</a>
          <a routerLink="/student/assignments" class="nav-pill">Assignments & Tasks</a>
          <a routerLink="/student/quiz-history" class="nav-pill active">Assessment History</a>
        </div>

        <!-- Header -->
        <div class="page-header">
          <div>
            <h1>Assessment Examination History</h1>
            <p class="subtitle">Review your past examination attempts, scores earned, passing thresholds, and detailed answer breakdowns.</p>
          </div>
        </div>

        @if (feedbackMessage) {
          <div class="alert alert-danger">
            {{ feedbackMessage }}
          </div>
        }

        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading assessment records...</span>
          </div>
        } @else if (attempts.length === 0) {
          <div class="empty-block card">
            <div class="empty-icon">📊</div>
            <h3>No examination attempts recorded</h3>
            <p>You haven't completed any quizzes yet. Complete a lesson in your courses to unlock assessments!</p>
            <a routerLink="/student/my-learning" class="btn btn-primary">Go to My Learning</a>
          </div>
        } @else {
          <!-- Summary Bar -->
          <div class="summary-bar card">
            <div class="summary-stat">
              <span class="stat-label">Total Attempts:</span>
              <strong class="stat-val">{{ attempts.length }}</strong>
            </div>
            <div class="summary-stat">
              <span class="stat-label">Assessments Passed:</span>
              <strong class="stat-val text-success">{{ passedCount }} ({{ passRate }}%)</strong>
            </div>
            <div class="summary-stat">
              <span class="stat-label">Average Score:</span>
              <strong class="stat-val">{{ averageScore }}%</strong>
            </div>
          </div>

          <!-- History Table -->
          <div class="table-container card">
            <table>
              <thead>
                <tr>
                  <th>Assessment Title</th>
                  <th>Course</th>
                  <th>Attempt #</th>
                  <th>Score Earned</th>
                  <th>Passing Mark</th>
                  <th>Outcome</th>
                  <th>Submitted At</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                @for (a of attempts; track a.attempt_id) {
                  <tr>
                    <td>
                      <strong>{{ a.quiz_title }}</strong>
                    </td>
                    <td>
                      <span class="course-text">{{ a.course_title }}</span>
                    </td>
                    <td>
                      <span class="badge badge-neutral">Attempt #{{ a.attempt_number }}</span>
                    </td>
                    <td>
                      <strong class="score-text">{{ a.score }}%</strong>
                    </td>
                    <td>
                      <span class="pass-mark-text">{{ a.passing_score }}%</span>
                    </td>
                    <td>
                      <span class="badge" [ngClass]="a.passed ? 'badge-success' : 'badge-danger'">
                        {{ a.passed ? 'Passed ✓' : 'Failed ✕' }}
                      </span>
                    </td>
                    <td class="date-cell">
                      {{ a.submitted_at ? (a.submitted_at | date:'medium') : (a.started_at | date:'medium') }}
                    </td>
                    <td>
                      <div class="action-btn-group">
                        <a [routerLink]="['/quizzes', 'attempts', a.attempt_id]" class="btn btn-sm btn-outline">
                          Review Attempt
                        </a>
                        @if (canRetake(a)) {
                          <a [routerLink]="['/courses', a.course_id, 'quizzes', a.quiz_id]" class="btn btn-sm btn-secondary" title="Retake Quiz">
                            Retake
                          </a>
                        }
                      </div>
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
    .history-page {
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
    .summary-bar {
      display: flex;
      gap: 2.5rem;
      padding: 1.4rem 2rem;
      margin-bottom: 2rem;
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 4px 15px rgba(99, 102, 241, 0.05);
      flex-wrap: wrap;
    }
    .summary-stat {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }
    .stat-label {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .stat-val {
      font-size: 1.35rem;
      font-weight: 800;
    }
    .score-text {
      font-size: 1rem;
      color: var(--primary);
    }
    .pass-mark-text {
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .course-text {
      font-size: 0.9rem;
    }
    .date-cell {
      font-size: 0.8rem;
      color: var(--text-muted);
      white-space: nowrap;
    }
    .action-btn-group {
      display: flex;
      gap: 0.4rem;
      align-items: center;
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
export class StudentQuizHistoryComponent implements OnInit {
  attempts: StudentQuizHistoryItem[] = [];
  isLoading = true;
  feedbackMessage = '';

  constructor(private studentService: StudentService) {}

  ngOnInit(): void {
    this.loadHistory();
  }

  loadHistory(): void {
    this.isLoading = true;
    this.studentService.getQuizHistory().subscribe({
      next: (list) => {
        this.attempts = list;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.feedbackMessage = err.error?.detail || 'Failed to load examination history.';
      }
    });
  }

  get passedCount(): number {
    return this.attempts.filter(a => a.passed).length;
  }

  get passRate(): number {
    if (this.attempts.length === 0) return 0;
    return Math.round((this.passedCount / this.attempts.length) * 100);
  }

  get averageScore(): number {
    if (this.attempts.length === 0) return 0;
    const total = this.attempts.reduce((sum, a) => sum + a.score, 0);
    return Math.round((total / this.attempts.length) * 10) / 10;
  }

  canRetake(a: StudentQuizHistoryItem): boolean {
    return a.remaining_attempts == null || a.remaining_attempts > 0;
  }
}
