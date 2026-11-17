import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  AICourseOutline,
  AIQuizAnswerSubmission,
  AIQuizAttemptResponse,
  AIQuizGeneratedResponse,
  AIQuizHistoryItem,
  AIQuizQuestion,
} from '../../core/models/ai-learning.model';
import { AILearningService } from '../../core/services/ai-learning.service';

@Component({
  selector: 'app-ai-quiz-generator',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="ai-page">
      <div class="container">
        <nav class="student-nav-bar" aria-label="Student navigation">
          <a routerLink="/student/dashboard" class="nav-pill">Overview</a>
          <a routerLink="/student/my-learning" class="nav-pill">My Learning</a>
          <a routerLink="/student/assignments" class="nav-pill">Assignments & Tasks</a>
          <a routerLink="/student/quiz-history" class="nav-pill">Assessment History</a>
          <a routerLink="/student/ai-quiz" class="nav-pill active">AI Quiz Generator</a>
          <a routerLink="/student/study-planner" class="nav-pill">Study Planner</a>
        </nav>

        <header class="page-header">
          <div>
            <span class="eyebrow">AI Learning Tools</span>
            <h1>AI Quiz Generator</h1>
            <p>Create a practice quiz from the real lesson content in your enrolled courses.</p>
          </div>
        </header>

        @if (errorMessage) {
          <div class="alert error">{{ errorMessage }}</div>
        }
        @if (noticeMessage) {
          <div class="alert success">{{ noticeMessage }}</div>
        }

        @if (!quiz || result) {
          <section class="card generator-card">
            <h2>Build your quiz</h2>
            <p class="muted">Choose a module or lesson. Questions are generated only from its stored learning content.</p>
            @if (courses.length === 0) {
              <div class="empty-state">You need an approved course enrollment with lessons to generate a quiz.</div>
            } @else {
              <form class="quiz-form" (ngSubmit)="generateQuiz()">
                <label>
                  Enrolled course
                  <select name="course" [ngModel]="selectedCourseId" (ngModelChange)="selectCourse($event)" required>
                    <option [ngValue]="null" disabled>Select a course</option>
                    @for (course of courses; track course.id) {
                      <option [ngValue]="course.id">{{ course.title }}</option>
                    }
                  </select>
                </label>
                <label>
                  Module or lesson
                  <select name="scope" [(ngModel)]="selectedScope" required>
                    <option value="" disabled>Select a module or lesson</option>
                    @for (scope of contentScopes; track scope.value) {
                      <option [value]="scope.value">{{ scope.label }}</option>
                    }
                  </select>
                </label>
                <label>
                  Difficulty
                  <select name="difficulty" [(ngModel)]="difficulty">
                    <option value="easy">Easy</option>
                    <option value="medium">Medium</option>
                    <option value="hard">Hard</option>
                  </select>
                </label>
                <label>
                  Number of questions
                  <select name="questionCount" [(ngModel)]="questionCount">
                    <option [ngValue]="5">5</option>
                    <option [ngValue]="10">10</option>
                    <option [ngValue]="15">15</option>
                    <option [ngValue]="20">20</option>
                  </select>
                </label>
                <label>
                  Question type
                  <select name="questionType" [(ngModel)]="questionType">
                    <option value="mcq">Multiple choice</option>
                    <option value="true_false">True or false</option>
                    <option value="short_answer">Short answer</option>
                    <option value="mixed">Mixed questions</option>
                  </select>
                </label>
                <button class="btn btn-primary" type="submit" [disabled]="busy || !selectedCourseId || !selectedScope">
                  {{ busy ? 'Generating from lesson content…' : 'Generate quiz' }}
                </button>
              </form>
            }
          </section>
        }

        @if (quiz && !result) {
          <section class="card quiz-card">
            <div class="quiz-heading">
              <div>
                <span class="eyebrow">{{ quiz.quiz.course_title }} · {{ quiz.quiz.difficulty | titlecase }}</span>
                <h2>{{ quiz.quiz.title }}</h2>
              </div>
              @if (attemptId !== null) {
                <span class="progress-label">Question {{ currentQuestionIndex + 1 }} of {{ quiz.questions.length }}</span>
              }
            </div>
            @if (attemptId === null) {
              <p class="muted">Your answer key and explanations will appear after you submit.</p>
              <button class="btn btn-primary" (click)="startQuiz()" [disabled]="busy">Start quiz</button>
            } @else {
              <div class="progress-track"><span [style.width.%]="questionProgress"></span></div>
              @if (currentQuestion; as question) {
                <div class="question-panel">
                  <span class="question-number">Question {{ currentQuestionIndex + 1 }}</span>
                  <h3>{{ question.question }}</h3>
                  @if (question.question_type === 'short_answer') {
                    <label class="answer-label">
                      Your answer
                      <textarea rows="5" [ngModel]="textAnswer(question.id)" (ngModelChange)="setTextAnswer(question.id, $event)" [ngModelOptions]="{standalone: true}" placeholder="Write your answer here"></textarea>
                    </label>
                  } @else {
                    <div class="option-list">
                      @for (option of question.options; track option.id) {
                        <label class="option">
                          <input
                            type="radio"
                            [name]="'question-' + question.id"
                            [checked]="selectedOption(question.id) === option.id"
                            (change)="selectOption(question.id, option.id)"
                          />
                          <span>{{ option.text }}</span>
                        </label>
                      }
                    </div>
                  }
                </div>
              }
              <div class="quiz-controls">
                <button class="btn btn-outline" (click)="previousQuestion()" [disabled]="currentQuestionIndex === 0">Previous</button>
                <span class="muted">Progress {{ questionProgress }}%</span>
                @if (currentQuestionIndex < quiz.questions.length - 1) {
                  <button class="btn btn-primary" (click)="nextQuestion()">Next question</button>
                } @else {
                  <button class="btn btn-primary" (click)="submitQuiz()" [disabled]="busy">
                    {{ busy ? 'Evaluating…' : 'Submit quiz' }}
                  </button>
                }
              </div>
            }
          </section>
        }

        @if (result) {
          <section class="card results-card">
            <div class="result-header">
              <div>
                <span class="eyebrow">Quiz results · {{ result.course_title }}</span>
                <h2>{{ result.quiz_title }}</h2>
              </div>
              <div class="score-circle">
                <strong>{{ result.percentage }}%</strong>
                <span>{{ result.performance_level }}</span>
              </div>
            </div>
            <p class="score-line">Score: {{ result.awarded_points }} / {{ result.total_points }} · Time taken: {{ formatDuration(result.duration_seconds) }}</p>
            @for (answer of result.answers; track answer.question_id; let i = $index) {
              <article class="answer-review" [class.correct]="answer.is_correct" [class.incorrect]="!answer.is_correct">
                <div class="review-heading">
                  <strong>{{ i + 1 }}. {{ answer.question }}</strong>
                  <span class="badge" [class.badge-success]="answer.is_correct" [class.badge-danger]="!answer.is_correct">
                    {{ answer.is_correct ? 'Correct' : 'Review' }} · {{ answer.awarded_points }}/{{ answer.total_points }}
                  </span>
                </div>
                <p><b>Your answer:</b> {{ answer.submitted_answer || 'No answer provided' }}</p>
                <p><b>Expected answer:</b> {{ answer.correct_answer }}</p>
                @if (answer.automated_evaluation) {
                  <p class="automation-note">Short answer evaluated automatically. {{ answer.automated_feedback }}</p>
                }
                <p class="explanation"><b>Explanation:</b> {{ answer.explanation }}</p>
              </article>
            }
            @if (hasAutomatedAnswers) {
              <div class="review-request">
                <p>Automated short-answer grading can be imperfect. You may request an instructor review.</p>
                <button class="btn btn-outline" (click)="requestReview()" [disabled]="busy || !!result.review_requested_at">
                  {{ result.review_requested_at ? 'Instructor review requested' : 'Request instructor review' }}
                </button>
              </div>
            }
            <button class="btn btn-primary" (click)="resetQuiz()">Create another quiz</button>
          </section>
        }

        <section class="card history-card">
          <div class="section-heading">
            <div>
              <h2>AI Quiz History</h2>
              <p class="muted">Review your previous practice attempts and answers.</p>
            </div>
          </div>
          @if (history.length === 0) {
            <p class="empty-state">Your submitted AI practice quizzes will appear here.</p>
          } @else {
            <div class="table-wrap">
              <table>
                <thead><tr><th>Quiz</th><th>Course</th><th>Attempted</th><th>Score</th><th>Difficulty</th><th>Time</th><th></th></tr></thead>
                <tbody>
                  @for (item of history; track item.attempt_id) {
                    <tr>
                      <td>{{ item.quiz_name }}</td>
                      <td>{{ item.course_name }}</td>
                      <td>{{ item.attempted_at | date:'medium' }}</td>
                      <td>{{ item.awarded_marks }}/{{ item.total_marks }} ({{ item.percentage }}%)</td>
                      <td>{{ item.difficulty | titlecase }}</td>
                      <td>{{ formatDuration(item.time_taken_seconds) }}</td>
                      <td><button class="btn btn-sm btn-outline" (click)="reviewHistory(item)">Review</button></td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          }
        </section>
      </div>
    </div>
  `,
  styles: [`
    .ai-page { min-height: calc(100vh - 120px); padding: 2rem 0 4rem; }
    .student-nav-bar { display:flex; gap:.6rem; margin-bottom:2rem; padding-bottom:.85rem; border-bottom:1px solid var(--border-light); overflow-x:auto; }
    .nav-pill { white-space:nowrap; padding:.55rem 1rem; border:1px solid var(--border-color); border-radius:999px; background:#fff; color:var(--text-muted); text-decoration:none; font-weight:600; }
    .nav-pill.active { color:#fff; background:var(--primary); border-color:var(--primary); }
    .page-header,.quiz-heading,.result-header,.section-heading { display:flex; justify-content:space-between; align-items:center; gap:1rem; }
    .page-header { margin-bottom:1.5rem; }
    h1 { margin:.25rem 0; font-size:2rem; }
    h2 { margin:.25rem 0 .5rem; }
    .eyebrow { color:var(--primary); font-size:.78rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
    .muted { color:var(--text-muted); }
    .card { padding:1.5rem; margin-bottom:1.25rem; }
    .quiz-form { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:1rem; align-items:end; margin-top:1.25rem; }
    label { display:grid; gap:.45rem; font-weight:650; color:var(--text-primary); }
    select,textarea { width:100%; padding:.75rem; border:1px solid var(--border-color); border-radius:var(--radius-md); background:#fff; color:var(--text-primary); font:inherit; }
    .quiz-form button { min-height:46px; }
    .alert { padding:.9rem 1rem; border-radius:var(--radius-md); margin-bottom:1rem; }
    .alert.error { color:#9f1239; background:#fff1f2; border:1px solid #fecdd3; }
    .alert.success { color:#166534; background:#f0fdf4; border:1px solid #bbf7d0; }
    .empty-state { padding:1rem; color:var(--text-muted); text-align:center; }
    .progress-label { color:var(--text-muted); font-weight:700; white-space:nowrap; }
    .progress-track { height:8px; overflow:hidden; background:var(--bg-subtle); border-radius:10px; margin:1rem 0; }
    .progress-track span { display:block; height:100%; background:var(--primary); transition:width .2s ease; }
    .question-panel { padding:1.5rem 0; }
    .question-number { color:var(--primary); font-size:.82rem; font-weight:800; text-transform:uppercase; }
    .question-panel h3 { margin:.6rem 0 1.25rem; line-height:1.5; }
    .option-list { display:grid; gap:.75rem; }
    .option { display:flex; align-items:flex-start; gap:.75rem; border:1px solid var(--border-color); border-radius:var(--radius-md); padding:1rem; cursor:pointer; }
    .option:has(input:checked) { border-color:var(--primary); background:var(--bg-subtle); }
    .option input { margin-top:.25rem; accent-color:var(--primary); }
    .answer-label textarea { resize:vertical; }
    .quiz-controls { display:flex; justify-content:space-between; align-items:center; gap:1rem; border-top:1px solid var(--border-light); padding-top:1rem; }
    .score-circle { display:grid; place-items:center; min-width:92px; min-height:92px; border-radius:50%; background:var(--bg-subtle); color:var(--primary); }
    .score-circle strong { font-size:1.4rem; }
    .score-circle span { font-size:.7rem; font-weight:700; }
    .score-line { font-weight:700; margin:1rem 0; }
    .answer-review { border:1px solid var(--border-color); border-left:4px solid #e11d48; border-radius:var(--radius-md); padding:1rem; margin:1rem 0; }
    .answer-review.correct { border-left-color:#16a34a; }
    .review-heading { display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; }
    .answer-review p { margin:.65rem 0 0; }
    .explanation { color:var(--text-muted); }
    .automation-note { color:#9a3412; background:#fff7ed; padding:.65rem; border-radius:var(--radius-sm); }
    .review-request { display:flex; justify-content:space-between; align-items:center; gap:1rem; border-top:1px solid var(--border-light); padding:1rem 0; margin-bottom:1rem; }
    .table-wrap { overflow-x:auto; }
    table { width:100%; border-collapse:collapse; text-align:left; }
    th,td { padding:.8rem; border-bottom:1px solid var(--border-light); white-space:nowrap; }
    th { color:var(--text-muted); font-size:.8rem; }
    @media (max-width:640px) {
      .page-header,.quiz-heading,.result-header,.review-request { align-items:flex-start; flex-direction:column; }
      .quiz-controls { flex-wrap:wrap; }
      .quiz-controls .muted { order:3; width:100%; text-align:center; }
      .card { padding:1rem; }
    }
  `]
})
export class AIQuizGeneratorComponent implements OnInit {
  courses: AICourseOutline[] = [];
  selectedCourseId: number | null = null;
  selectedScope = '';
  difficulty: 'easy' | 'medium' | 'hard' = 'medium';
  questionCount: 5 | 10 | 15 | 20 = 5;
  questionType: 'mcq' | 'true_false' | 'short_answer' | 'mixed' = 'mixed';
  quiz: AIQuizGeneratedResponse | null = null;
  result: AIQuizAttemptResponse | null = null;
  attemptId: number | null = null;
  currentQuestionIndex = 0;
  history: AIQuizHistoryItem[] = [];
  answers: Record<number, { optionId?: number; text?: string }> = {};
  busy = false;
  errorMessage = '';
  noticeMessage = '';

  constructor(private aiLearning: AILearningService) {}

  ngOnInit(): void {
    this.aiLearning.getCourses().subscribe({
      next: (courses) => {
        this.courses = courses;
        this.selectedCourseId = courses[0]?.id ?? null;
      },
      error: (error: HttpErrorResponse) => this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not load enrolled course lessons.'),
    });
    this.loadHistory();
  }

  get contentScopes(): { value: string; label: string }[] {
    const course = this.courses.find((item) => item.id === this.selectedCourseId);
    if (!course) return [];
    return [
      ...course.sections.map((section) => ({ value: `section:${section.id}`, label: `Module: ${section.title}` })),
      ...course.lessons.map((lesson) => ({ value: `lesson:${lesson.id}`, label: `Lesson: ${lesson.title}` })),
    ];
  }

  get currentQuestion(): AIQuizQuestion | null {
    return this.quiz?.questions[this.currentQuestionIndex] ?? null;
  }

  get questionProgress(): number {
    return this.quiz?.questions.length
      ? Math.round(((this.currentQuestionIndex + 1) / this.quiz.questions.length) * 100)
      : 0;
  }

  get hasAutomatedAnswers(): boolean {
    return !!this.result?.answers.some((answer) => answer.automated_evaluation);
  }

  selectCourse(courseId: number | null): void {
    this.selectedCourseId = courseId;
    this.selectedScope = '';
  }

  generateQuiz(): void {
    if (!this.selectedCourseId || !this.selectedScope) return;
    const [scope, idValue] = this.selectedScope.split(':');
    const scopeId = Number(idValue);
    const payload = {
      course_id: this.selectedCourseId,
      ...(scope === 'section' ? { section_id: scopeId } : { lesson_id: scopeId }),
      difficulty: this.difficulty,
      question_count: this.questionCount,
      question_type: this.questionType,
    };
    this.busy = true;
    this.errorMessage = '';
    this.noticeMessage = '';
    this.aiLearning.generateQuiz(payload).subscribe({
      next: (quiz) => {
        this.quiz = quiz;
        this.result = null;
        this.attemptId = null;
        this.currentQuestionIndex = 0;
        this.answers = {};
        this.busy = false;
      },
      error: (error) => {
        this.errorMessage = this.aiLearning.getErrorMessage(error, 'Quiz generation failed.');
        this.busy = false;
      },
    });
  }

  startQuiz(): void {
    if (!this.quiz) return;
    this.busy = true;
    this.aiLearning.startQuiz(this.quiz.quiz.id).subscribe({
      next: (response) => {
        this.attemptId = response.attempt_id;
        this.busy = false;
      },
      error: (error) => {
        this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not start this quiz.');
        this.busy = false;
      },
    });
  }

  selectedOption(questionId: number): number | undefined {
    return this.answers[questionId]?.optionId;
  }

  selectOption(questionId: number, optionId: number): void {
    this.answers[questionId] = { optionId };
  }

  textAnswer(questionId: number): string {
    return this.answers[questionId]?.text ?? '';
  }

  setTextAnswer(questionId: number, text: string): void {
    this.answers[questionId] = { text };
  }

  previousQuestion(): void {
    this.currentQuestionIndex = Math.max(0, this.currentQuestionIndex - 1);
  }

  nextQuestion(): void {
    if (this.quiz) {
      this.currentQuestionIndex = Math.min(this.quiz.questions.length - 1, this.currentQuestionIndex + 1);
    }
  }

  submitQuiz(): void {
    if (!this.quiz || this.attemptId === null) return;
    const answers: AIQuizAnswerSubmission[] = this.quiz.questions.map((question) => {
      const answer = this.answers[question.id];
      return question.question_type === 'short_answer'
        ? { question_id: question.id, answer_text: answer?.text ?? '' }
        : { question_id: question.id, selected_option_id: answer?.optionId };
    });
    this.busy = true;
    this.errorMessage = '';
    this.aiLearning.submitQuiz(this.attemptId, answers).subscribe({
      next: (result) => {
        this.result = result;
        this.busy = false;
        this.loadHistory();
      },
      error: (error) => {
        this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not submit your quiz.');
        this.busy = false;
      },
    });
  }

  reviewHistory(item: AIQuizHistoryItem): void {
    this.busy = true;
    this.errorMessage = '';
    this.aiLearning.getQuizAttempt(item.attempt_id).subscribe({
      next: (result) => {
        this.quiz = null;
        this.result = result;
        this.attemptId = result.id;
        this.busy = false;
        window.scrollTo({ top: 0, behavior: 'smooth' });
      },
      error: (error) => {
        this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not load that quiz review.');
        this.busy = false;
      },
    });
  }

  requestReview(): void {
    if (!this.result) return;
    this.busy = true;
    this.aiLearning.requestInstructorReview(this.result.id).subscribe({
      next: (response) => {
        if (this.result) this.result.review_requested_at = response.review_requested_at;
        this.noticeMessage = response.message;
        this.busy = false;
      },
      error: (error) => {
        this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not request an instructor review.');
        this.busy = false;
      },
    });
  }

  resetQuiz(): void {
    this.quiz = null;
    this.result = null;
    this.attemptId = null;
    this.errorMessage = '';
    this.noticeMessage = '';
  }

  formatDuration(seconds?: number | null): string {
    if (seconds == null) return '—';
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    return `${minutes}m ${remainder}s`;
  }

  private loadHistory(): void {
    this.aiLearning.getQuizHistory().subscribe({
      next: (history) => this.history = history,
      error: (error: HttpErrorResponse) => this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not load AI quiz history.'),
    });
  }
}
