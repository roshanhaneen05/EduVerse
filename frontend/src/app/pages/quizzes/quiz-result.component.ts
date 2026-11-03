import { Component, OnInit, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { QuizService } from '../../core/services/quiz.service';
import { QuizAttemptResult } from '../../core/models/quiz.model';

@Component({
  selector: 'app-quiz-result',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="result-page">
      @if (isLoading) {
        <div class="loading-state">
          <div class="spinner"></div>
          <span>Retrieving assessment results...</span>
        </div>
      } @else if (!attempt) {
        <div class="container not-found card">
          <h2>Attempt Not Found</h2>
          <p>Could not load the requested quiz attempt.</p>
          <a routerLink="/student/dashboard" class="btn btn-primary">Return to Dashboard</a>
        </div>
      } @else {
        <div class="container result-container">
          <!-- Result Summary Banner Card -->
          <div class="summary-card card" [class.passed]="attempt.passed" [class.failed]="!attempt.passed">
            <div class="result-header">
              <span class="badge" [ngClass]="attempt.passed ? 'badge-success' : 'badge-danger'">
                {{ attempt.passed ? 'PASSED' : 'NEEDS IMPROVEMENT' }}
              </span>
              <span class="submission-time">{{ attempt.submitted_at | date:'medium' }}</span>
            </div>

            <div class="score-display">
              <div class="score-circle" [class.passed]="attempt.passed" [class.failed]="!attempt.passed">
                <span class="score-pct">{{ attempt.score }}%</span>
              </div>
              <div class="score-details">
                <h1 class="result-title">{{ attempt.quiz_title }}</h1>
                <p class="score-narrative">
                  @if (attempt.passed) {
                    Congratulations! You scored <strong>{{ attempt.score }}%</strong>, exceeding the passing threshold of <strong>{{ attempt.passing_score }}%</strong>.
                  } @else {
                    You scored <strong>{{ attempt.score }}%</strong>. The passing threshold is <strong>{{ attempt.passing_score }}%</strong>. Review the questions below and try again.
                  }
                </p>
                <div class="score-stats">
                  <span>Awarded Points: <strong>{{ getAwardedPoints() }} / {{ attempt.total_points }}</strong></span>
                </div>
              </div>
            </div>

            <div class="action-buttons-row">
              <a routerLink="/student/dashboard" class="btn btn-secondary">
                ← Go to Dashboard
              </a>
              <a [routerLink]="['/courses']" class="btn btn-outline">
                Browse More Courses
              </a>
            </div>
          </div>

          <!-- Question-by-Question Review -->
          <div class="review-section">
            <div class="review-header">
              <h2>Detailed Question Review</h2>
              <span class="badge badge-neutral">{{ (attempt.answers || []).length }} Questions</span>
            </div>

            <div class="answers-list">
              @for (ans of (attempt.answers || []); track ans.question_id; let i = $index) {
                <div class="answer-card card" [class.correct]="ans.is_correct" [class.incorrect]="!ans.is_correct">
                  <div class="answer-header">
                    <div class="status-indicator">
                      @if (ans.is_correct) {
                        <span class="badge-icon correct">✓ Correct</span>
                      } @else {
                        <span class="badge-icon incorrect">✕ Incorrect</span>
                      }
                      <span class="question-number">Question {{ i + 1 }}</span>
                    </div>

                    <span class="awarded-pill">
                      {{ ans.awarded_points }} / {{ ans.points }} pts
                    </span>
                  </div>

                  <h3 class="question-text">{{ ans.question_text }}</h3>

                  <div class="response-breakdown">
                    <div class="breakdown-item your-answer" [class.wrong]="!ans.is_correct">
                      <span class="breakdown-label">Your Answer:</span>
                      <span class="breakdown-text">{{ ans.selected_option_text || 'No answer selected' }}</span>
                    </div>

                    @if (!ans.is_correct) {
                      <div class="breakdown-item correct-answer">
                        <span class="breakdown-label">Correct Answer:</span>
                        <span class="breakdown-text">{{ ans.correct_option_text }}</span>
                      </div>
                    }
                  </div>
                </div>
              }
            </div>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .result-page {
      padding: 2.5rem 0 4rem 0;
      background-color: var(--bg-app);
      min-height: calc(100vh - 120px);
    }
    .result-container {
      max-width: 860px;
    }
    .summary-card {
      padding: 2.25rem;
      margin-bottom: 2.5rem;
      border-top: 6px solid var(--border-color);
    }
    .summary-card.passed {
      border-top-color: var(--success);
      background: linear-gradient(180deg, #ffffff 0%, #f0fdf4 100%);
    }
    .summary-card.failed {
      border-top-color: var(--danger);
      background: linear-gradient(180deg, #ffffff 0%, #fef2f2 100%);
    }
    .result-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.5rem;
    }
    .submission-time {
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .score-display {
      display: flex;
      align-items: center;
      gap: 2rem;
      margin-bottom: 2rem;
    }
    @media (max-width: 600px) {
      .score-display {
        flex-direction: column;
        text-align: center;
      }
    }
    .score-circle {
      width: 100px;
      height: 100px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      flex-shrink: 0;
      border: 4px solid var(--border-color);
    }
    .score-circle.passed {
      border-color: var(--success);
      background-color: var(--success-light);
      color: var(--success-text);
    }
    .score-circle.failed {
      border-color: var(--danger);
      background-color: var(--danger-light);
      color: var(--danger-text);
    }
    .score-pct {
      font-size: 1.85rem;
    }
    .result-title {
      font-size: 1.65rem;
      margin-bottom: 0.4rem;
    }
    .score-narrative {
      font-size: 1rem;
      color: var(--text-muted);
      margin-bottom: 0.75rem;
      line-height: 1.5;
    }
    .score-stats {
      font-size: 0.9rem;
      color: var(--text-main);
    }
    .action-buttons-row {
      display: flex;
      gap: 1rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--border-color);
      flex-wrap: wrap;
    }
    .review-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.5rem;
    }
    .answers-list {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }
    .answer-card {
      padding: 1.75rem;
    }
    .answer-card.correct {
      border-left: 4px solid var(--success);
    }
    .answer-card.incorrect {
      border-left: 4px solid var(--danger);
    }
    .answer-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }
    .status-indicator {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .badge-icon {
      font-size: 0.75rem;
      font-weight: 700;
      padding: 0.2rem 0.6rem;
      border-radius: var(--radius-full);
      text-transform: uppercase;
    }
    .badge-icon.correct {
      background-color: var(--success-light);
      color: var(--success-text);
    }
    .badge-icon.incorrect {
      background-color: var(--danger-light);
      color: var(--danger-text);
    }
    .question-number {
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--text-muted);
    }
    .awarded-pill {
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--text-muted);
      background-color: var(--bg-subtle);
      padding: 0.2rem 0.6rem;
      border-radius: var(--radius-sm);
    }
    .question-text {
      font-size: 1.15rem;
      font-weight: 600;
      margin-bottom: 1.25rem;
    }
    .response-breakdown {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }
    .breakdown-item {
      display: flex;
      gap: 0.5rem;
      font-size: 0.95rem;
      padding: 0.75rem 1rem;
      border-radius: var(--radius-md);
    }
    .your-answer {
      background-color: var(--bg-subtle);
      color: var(--text-main);
    }
    .your-answer.wrong {
      background-color: var(--danger-light);
      color: var(--danger-text);
    }
    .correct-answer {
      background-color: var(--success-light);
      color: var(--success-text);
    }
    .breakdown-label {
      font-weight: 700;
      min-width: 110px;
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
export class QuizResultComponent implements OnInit {
  @Input() attemptId!: string;
  attempt: QuizAttemptResult | null = null;
  isLoading = true;

  constructor(private quizService: QuizService) {}

  ngOnInit(): void {
    if (this.attemptId) {
      this.loadAttempt(Number(this.attemptId));
    }
  }

  loadAttempt(id: number): void {
    this.isLoading = true;
    this.quizService.getAttempt(id).subscribe({
      next: (data) => {
        this.attempt = data;
        this.isLoading = false;
      },
      error: () => {
        this.attempt = null;
        this.isLoading = false;
      }
    });
  }

  getAwardedPoints(): number {
    if (!this.attempt || !this.attempt.answers) return 0;
    return this.attempt.answers.reduce((sum, a) => sum + (a.awarded_points || 0), 0);
  }
}

