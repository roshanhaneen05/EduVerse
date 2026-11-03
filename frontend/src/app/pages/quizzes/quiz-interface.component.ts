import { Component, OnInit, OnDestroy, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { QuizService } from '../../core/services/quiz.service';
import { Quiz, QuizAnswerSubmission, QuizStartResponse } from '../../core/models/quiz.model';

@Component({
  selector: 'app-quiz-interface',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="quiz-page">
      @if (isLoading) {
        <div class="loading-state">
          <div class="spinner"></div>
          <span>Loading assessment questions...</span>
        </div>
      } @else if (!quiz) {
        <div class="container not-found card">
          <h2>Quiz Unavailable</h2>
          <p>{{ errorMessage || 'This assessment could not be found or you may need to enroll in the course first.' }}</p>
          <a [routerLink]="['/courses', courseId]" class="btn btn-primary">Return to Course</a>
        </div>
      } @else if (quiz.can_attempt === false) {
        <div class="container not-found card">
          <h2>Maximum Attempt Limit Reached</h2>
          <p>
            You have completed all <strong>{{ quiz.max_attempts }}</strong> allowed attempts for
            <em>{{ quiz.title }}</em>.
          </p>
          @if (quiz.best_score !== null && quiz.best_score !== undefined) {
            <p class="best-score-badge">Your Best Score: <strong>{{ quiz.best_score }}%</strong></p>
          }
          <div class="btn-group">
            <a [routerLink]="['/student/dashboard']" class="btn btn-secondary">Student Dashboard</a>
            <a [routerLink]="['/courses', courseId]" class="btn btn-primary">Return to Course</a>
          </div>
        </div>
      } @else {
        <div class="container quiz-container">
          <!-- Quiz Header Card -->
          <div class="quiz-header-card card">
            <div class="quiz-header-top">
              <a [routerLink]="['/courses', courseId]" class="back-link">← Return to Syllabus</a>
              <div class="header-badges">
                @if (quiz.time_limit_minutes) {
                  <div class="timer-pill" [class.urgent]="timeRemainingSeconds !== null && timeRemainingSeconds < 300" [class.critical]="timeRemainingSeconds !== null && timeRemainingSeconds < 60">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"/>
                      <polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <span>Time Left: <strong>{{ timeRemainingFormatted }}</strong></span>
                  </div>
                }
                <span class="badge badge-primary">Graded Assessment</span>
              </div>
            </div>

            <h1 class="quiz-title">{{ quiz.title }}</h1>
            @if (quiz.description) {
              <p class="quiz-description">{{ quiz.description }}</p>
            }

            <div class="quiz-meta-bar">
              <div class="meta-item">
                <span class="label">Questions:</span>
                <span class="value">{{ quiz.questions.length }}</span>
              </div>
              <div class="meta-item">
                <span class="label">Passing Score:</span>
                <span class="value">{{ quiz.passing_score }}%</span>
              </div>
              <div class="meta-item">
                <span class="label">Total Points:</span>
                <span class="value">{{ getTotalPoints() }}</span>
              </div>
              @if (quiz.max_attempts > 0) {
                <div class="meta-item">
                  <span class="label">Attempt:</span>
                  <span class="value">{{ (quiz.attempts_count || 0) + 1 }} of {{ quiz.max_attempts }}</span>
                </div>
              }
              <div class="meta-item progress-meta">
                <span class="label">Answered:</span>
                <span class="value">{{ getAnsweredCount() }} / {{ quiz.questions.length }}</span>
              </div>
            </div>

            <!-- Quick Navigation Pills -->
            <div class="nav-pills-bar">
              <span class="nav-label">Jump to question:</span>
              <div class="pills-row">
                @for (q of quiz.questions; track q.id; let i = $index) {
                  <button
                    type="button"
                    (click)="scrollToQuestion(q.id)"
                    class="nav-pill-btn"
                    [class.answered]="selectedAnswers[q.id]"
                  >
                    {{ i + 1 }}
                  </button>
                }
              </div>
            </div>
          </div>

          @if (errorMessage) {
            <div class="alert alert-danger">
              {{ errorMessage }}
            </div>
          }

          <!-- Questions List -->
          <form (ngSubmit)="confirmSubmit()" class="quiz-form">
            <div class="questions-list">
              @for (q of quiz.questions; track q.id; let i = $index) {
                <div [id]="'question-' + q.id" class="question-card card" [class.answered]="selectedAnswers[q.id]">
                  <div class="question-header">
                    <span class="question-num">Question {{ i + 1 }}</span>
                    <span class="question-pts">{{ q.points }} {{ q.points === 1 ? 'pt' : 'pts' }}</span>
                  </div>

                  <p class="question-text">{{ q.question_text }}</p>

                  <div class="options-group">
                    @for (opt of q.options; track opt.id) {
                      <label
                        class="option-label"
                        [class.selected]="selectedAnswers[q.id] === opt.id"
                      >
                        <input
                          type="radio"
                          [name]="'q_' + q.id"
                          [value]="opt.id"
                          [(ngModel)]="selectedAnswers[q.id]"
                          class="option-radio"
                        />
                        <span class="option-custom-radio"></span>
                        <span class="option-text">{{ opt.option_text }}</span>
                      </label>
                    }
                  </div>
                </div>
              }
            </div>

            <!-- Submit Section -->
            <div class="submit-card card">
              <div class="submit-info">
                <h4>Ready to submit your assessment?</h4>
                <p>
                  @if (getAnsweredCount() === quiz.questions.length) {
                    All {{ quiz.questions.length }} questions have been answered. Your submission will be evaluated instantly.
                  } @else {
                    <span class="warn-text">
                      Warning: You have answered {{ getAnsweredCount() }} of {{ quiz.questions.length }} questions. Unanswered questions will receive 0 points.
                    </span>
                  }
                </p>
              </div>

              <button
                type="submit"
                class="btn btn-primary btn-lg submit-btn"
                [disabled]="isSubmitting"
              >
                @if (isSubmitting) {
                  <div class="spinner-sm"></div>
                  <span>Evaluating answers...</span>
                } @else {
                  <span>Submit Assessment</span>
                }
              </button>
            </div>
          </form>
        </div>
      }
    </div>
  `,
  styles: [`
    .quiz-page {
      padding: 2.5rem 0 4rem 0;
      background-color: var(--bg-app);
      min-height: calc(100vh - 120px);
    }
    .quiz-container {
      max-width: 860px;
    }
    .quiz-header-card {
      padding: 2rem;
      margin-bottom: 2rem;
    }
    .quiz-header-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      flex-wrap: wrap;
      gap: 1rem;
    }
    .header-badges {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .timer-pill {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      background-color: var(--bg-subtle);
      border: 1px solid var(--border-color);
      padding: 0.35rem 0.75rem;
      border-radius: var(--radius-full);
      font-size: 0.85rem;
      color: var(--text-main);
      font-weight: 600;
    }
    .timer-pill.urgent {
      background-color: #fffbeb;
      border-color: #fde68a;
      color: #b45309;
    }
    .timer-pill.critical {
      background-color: #fef2f2;
      border-color: #fecaca;
      color: #b91c1c;
      animation: pulse 1s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.6; }
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
    .quiz-title {
      font-size: 1.85rem;
      margin-bottom: 0.5rem;
    }
    .quiz-description {
      color: var(--text-muted);
      font-size: 1rem;
      line-height: 1.5;
      margin-bottom: 1.5rem;
    }
    .quiz-meta-bar {
      display: flex;
      gap: 1.5rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border-light);
      flex-wrap: wrap;
    }
    .meta-item {
      display: flex;
      gap: 0.4rem;
      font-size: 0.9rem;
    }
    .meta-item .label {
      color: var(--text-muted);
    }
    .meta-item .value {
      font-weight: 700;
      color: var(--text-main);
    }
    .nav-pills-bar {
      margin-top: 1.25rem;
      padding-top: 1rem;
      border-top: 1px dashed var(--border-light);
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .nav-label {
      font-size: 0.8rem;
      color: var(--text-muted);
      font-weight: 600;
    }
    .pills-row {
      display: flex;
      gap: 0.4rem;
      flex-wrap: wrap;
    }
    .nav-pill-btn {
      width: 30px;
      height: 30px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-color);
      background-color: var(--bg-card);
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: var(--transition);
    }
    .nav-pill-btn.answered {
      background-color: var(--primary);
      color: #ffffff;
      border-color: var(--primary);
    }
    .questions-list {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
      margin-bottom: 2rem;
    }
    .question-card {
      padding: 1.75rem;
      transition: var(--transition);
    }
    .question-card.answered {
      border-left: 4px solid var(--primary);
    }
    .question-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }
    .question-num {
      font-size: 0.85rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--primary);
    }
    .question-pts {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-muted);
      background-color: var(--bg-subtle);
      padding: 0.2rem 0.5rem;
      border-radius: var(--radius-xs);
    }
    .question-text {
      font-size: 1.15rem;
      font-weight: 600;
      margin-bottom: 1.25rem;
      line-height: 1.45;
    }
    .options-group {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }
    .option-label {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.9rem 1.2rem;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      cursor: pointer;
      transition: var(--transition);
      background-color: var(--bg-card);
    }
    .option-label:hover {
      border-color: var(--primary);
      background-color: var(--bg-subtle);
    }
    .option-label.selected {
      border-color: var(--primary);
      background-color: rgba(79, 70, 229, 0.06);
    }
    .option-radio {
      display: none;
    }
    .option-custom-radio {
      width: 18px;
      height: 18px;
      border: 2px solid var(--border-color);
      border-radius: 50%;
      position: relative;
      flex-shrink: 0;
      transition: var(--transition);
    }
    .option-label.selected .option-custom-radio {
      border-color: var(--primary);
      background-color: var(--primary);
    }
    .option-label.selected .option-custom-radio::after {
      content: '';
      position: absolute;
      width: 6px;
      height: 6px;
      background-color: #ffffff;
      border-radius: 50%;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
    }
    .option-text {
      font-size: 0.95rem;
      line-height: 1.4;
    }
    .submit-card {
      padding: 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1.5rem;
      flex-wrap: wrap;
    }
    .submit-info h4 {
      margin-bottom: 0.35rem;
    }
    .submit-info p {
      font-size: 0.9rem;
      color: var(--text-muted);
    }
    .warn-text {
      color: #b45309;
      font-weight: 600;
    }
    .not-found {
      padding: 4rem 2rem;
      text-align: center;
      max-width: 600px;
      margin: 2rem auto;
    }
    .not-found h2 {
      margin-bottom: 0.75rem;
    }
    .not-found p {
      color: var(--text-muted);
      margin-bottom: 1.5rem;
    }
    .best-score-badge {
      display: inline-block;
      background: #eef2ff;
      color: #4338ca;
      padding: 0.5rem 1rem;
      border-radius: var(--radius-md);
      font-weight: 600;
    }
    .btn-group {
      display: flex;
      justify-content: center;
      gap: 1rem;
      margin-top: 1.5rem;
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
    .spinner-sm {
      width: 16px;
      height: 16px;
      border: 2px solid #ffffff;
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  `]
})
export class QuizInterfaceComponent implements OnInit, OnDestroy {
  @Input() courseId!: string;
  @Input() quizId!: string;

  quiz: Quiz | null = null;
  activeAttempt: QuizStartResponse | null = null;
  isLoading = true;
  isSubmitting = false;
  errorMessage = '';

  selectedAnswers: { [key: number]: number } = {};

  // Countdown timer state
  timeRemainingSeconds: number | null = null;
  timeRemainingFormatted = '';
  private timerInterval: any = null;

  constructor(
    private quizService: QuizService,
    private router: Router
  ) {}

  ngOnInit(): void {
    if (this.quizId) {
      this.loadQuiz(Number(this.quizId));
    }
  }

  ngOnDestroy(): void {
    this.clearTimer();
  }

  loadQuiz(id: number): void {
    this.isLoading = true;
    this.errorMessage = '';

    this.quizService.getQuiz(id).subscribe({
      next: (quizData) => {
        this.quiz = quizData;
        this.isLoading = false;

        // If student can attempt, start the attempt session
        if (quizData.can_attempt !== false) {
          this.startAttempt(id);
        }
      },
      error: (err) => {
        this.errorMessage = err.error?.detail || 'Failed to load assessment questions.';
        this.isLoading = false;
      }
    });
  }

  startAttempt(quizId: number): void {
    this.quizService.startQuiz(quizId).subscribe({
      next: (attempt) => {
        this.activeAttempt = attempt;
        if (attempt.expires_at) {
          this.initCountdown(attempt.expires_at);
        } else if (attempt.time_limit_minutes) {
          const expiresAt = new Date(new Date(attempt.started_at).getTime() + attempt.time_limit_minutes * 60000).toISOString();
          this.initCountdown(expiresAt);
        }
      },
      error: (err) => {
        if (err.status === 400 && err.error?.detail?.includes('maximum allowed attempts')) {
          if (this.quiz) {
            this.quiz.can_attempt = false;
          }
        }
      }
    });
  }

  initCountdown(expiresAtStr: string): void {
    this.clearTimer();
    const expiryTime = new Date(expiresAtStr).getTime();

    const updateTimer = () => {
      const now = Date.now();
      const diffMs = expiryTime - now;

      if (diffMs <= 0) {
        this.timeRemainingSeconds = 0;
        this.timeRemainingFormatted = '00:00';
        this.clearTimer();
        // Auto-submit when time expires
        this.handleTimeExpired();
        return;
      }

      this.timeRemainingSeconds = Math.floor(diffMs / 1000);
      const minutes = Math.floor(this.timeRemainingSeconds / 60);
      const seconds = this.timeRemainingSeconds % 60;
      this.timeRemainingFormatted = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    };

    updateTimer();
    this.timerInterval = setInterval(updateTimer, 1000);
  }

  clearTimer(): void {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }

  handleTimeExpired(): void {
    if (this.isSubmitting) return;
    alert('Time limit has expired! Submitting your answers automatically.');
    this.executeSubmit();
  }

  scrollToQuestion(questionId: number): void {
    const el = document.getElementById(`question-${questionId}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  getTotalPoints(): number {
    if (!this.quiz) return 0;
    return this.quiz.questions.reduce((sum, q) => sum + (q.points || 1), 0);
  }

  getAnsweredCount(): number {
    return Object.keys(this.selectedAnswers).length;
  }

  confirmSubmit(): void {
    if (!this.quiz || this.isSubmitting) return;

    const unanswered = this.quiz.questions.length - this.getAnsweredCount();
    if (unanswered > 0) {
      const proceed = confirm(`You have ${unanswered} unanswered question(s). Are you sure you want to submit?`);
      if (!proceed) return;
    }

    this.executeSubmit();
  }

  executeSubmit(): void {
    if (!this.quiz || this.isSubmitting) return;

    const answers: QuizAnswerSubmission[] = Object.keys(this.selectedAnswers).map(qId => ({
      question_id: Number(qId),
      selected_option_id: this.selectedAnswers[Number(qId)]
    }));

    this.isSubmitting = true;
    this.errorMessage = '';
    this.clearTimer();

    const payload = {
      attempt_id: this.activeAttempt?.attempt_id,
      answers
    };

    this.quizService.submitQuiz(this.quiz.id, payload).subscribe({
      next: (result) => {
        this.isSubmitting = false;
        const targetAttemptId = result.attempt_id || result.id;
        this.router.navigate(['/quizzes', 'attempts', targetAttemptId]);
      },
      error: (err) => {
        this.isSubmitting = false;
        this.errorMessage = err.error?.detail || 'Quiz evaluation failed. Please try again.';
      }
    });
  }
}
