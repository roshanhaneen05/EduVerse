import { Component, OnInit, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { CourseService } from '../../core/services/course.service';
import { InstructorService } from '../../core/services/instructor.service';
import { CourseDetail } from '../../core/models/course.model';
import { QuestionCreatePayload, Quiz, QuizCreatePayload } from '../../core/models/quiz.model';

@Component({
  selector: 'app-quiz-editor',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="quiz-mgr-page">
      <div class="container">
        <div class="page-header">
          <div>
            <a routerLink="/instructor/dashboard" class="back-link">← Back to Instructor Hub</a>
            <h1>Curriculum Assessments & Quizzes</h1>
            <p class="subtitle" *ngIf="course">
              Course: <strong>{{ course.title }}</strong>
            </p>
          </div>
          <div class="header-actions" *ngIf="!showCreateForm">
            <button (click)="openCreateQuiz()" class="btn btn-primary">
              + Author New Assessment
            </button>
          </div>
        </div>

        @if (feedbackMessage) {
          <div class="alert" [ngClass]="isError ? 'alert-danger' : 'alert-success'">
            {{ feedbackMessage }}
          </div>
        }

        <!-- Create / Edit Quiz Form -->
        @if (showCreateForm) {
          <div class="card quiz-builder-card">
            <div class="builder-header">
              <div>
                <h3>{{ editingQuizId ? 'Edit Graded Assessment' : 'Author New Graded Assessment' }}</h3>
                <p class="builder-subtitle">Design multi-question quizzes with automated server-side evaluation</p>
              </div>
              <button (click)="closeCreateQuiz()" class="btn btn-sm btn-secondary">Cancel</button>
            </div>

            <!-- Quiz Settings -->
            <div class="form-row">
              <div class="form-group flex-2">
                <label class="form-label">Quiz Title *</label>
                <input
                  type="text"
                  class="form-input"
                  [(ngModel)]="quizForm.title"
                  placeholder="e.g. Asynchronous Architecture Mastery Check"
                />
              </div>

              <div class="form-group flex-1">
                <label class="form-label">Passing Score (%) *</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  class="form-input"
                  [(ngModel)]="quizForm.passing_score"
                />
              </div>
            </div>

            <div class="form-row">
              <div class="form-group flex-1">
                <label class="form-label">Time Limit (Minutes)</label>
                <input
                  type="number"
                  min="1"
                  class="form-input"
                  [(ngModel)]="quizForm.time_limit_minutes"
                  placeholder="Optional (e.g. 30)"
                />
                <span class="field-hint">Leave blank or empty for untimed assessments</span>
              </div>

              <div class="form-group flex-1">
                <label class="form-label">Max Allowed Attempts *</label>
                <input
                  type="number"
                  min="0"
                  class="form-input"
                  [(ngModel)]="quizForm.max_attempts"
                  placeholder="Default 3 (0 for unlimited)"
                />
                <span class="field-hint">0 allows unlimited student attempts</span>
              </div>

              <div class="form-group flex-1" *ngIf="course?.sections && course!.sections!.length > 0">
                <label class="form-label">Associated Module / Section</label>
                <select class="form-input" [(ngModel)]="quizForm.section_id">
                  <option [ngValue]="null">-- Entire Course (No Module) --</option>
                  @for (sec of course!.sections!; track sec.id) {
                    <option [ngValue]="sec.id">{{ sec.title }}</option>
                  }
                </select>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Description / Student Instructions</label>
              <textarea
                rows="2"
                class="form-textarea"
                [(ngModel)]="quizForm.description"
                placeholder="Guidance, topics covered, or instructions for students..."
              ></textarea>
            </div>

            <div class="form-check-group">
              <label class="checkbox-label">
                <input type="checkbox" [(ngModel)]="quizForm.is_published" />
                <span><strong>Publish assessment immediately</strong> (visible to enrolled students)</span>
              </label>
            </div>

            <!-- Questions Builder -->
            <div class="questions-builder-section">
              <div class="builder-subhead">
                <div>
                  <h4>Questions ({{ quizForm.questions.length }})</h4>
                  <span class="total-pts-badge">Total Points: {{ calculateTotalPoints() }}</span>
                </div>
                <button type="button" (click)="addQuestion()" class="btn btn-sm btn-outline">
                  + Add Question
                </button>
              </div>

              @for (q of quizForm.questions; track $index; let qIndex = $index) {
                <div class="question-builder-item card">
                  <div class="q-header">
                    <div class="q-left-meta">
                      <span class="q-title-label">Question {{ qIndex + 1 }}</span>
                      <div class="reorder-btns">
                        <button
                          type="button"
                          class="btn-icon"
                          [disabled]="qIndex === 0"
                          (click)="moveQuestionUp(qIndex)"
                          title="Move Question Up"
                        >↑</button>
                        <button
                          type="button"
                          class="btn-icon"
                          [disabled]="qIndex === quizForm.questions.length - 1"
                          (click)="moveQuestionDown(qIndex)"
                          title="Move Question Down"
                        >↓</button>
                      </div>
                    </div>

                    <div class="q-meta-actions">
                      <div class="pts-input-box">
                        <label>Pts:</label>
                        <input type="number" min="1" [(ngModel)]="q.points" class="pts-input" />
                      </div>
                      @if (quizForm.questions.length > 1) {
                        <button type="button" (click)="removeQuestion(qIndex)" class="btn btn-sm btn-danger">
                          Remove
                        </button>
                      }
                    </div>
                  </div>

                  <div class="form-group">
                    <input
                      type="text"
                      class="form-input"
                      [(ngModel)]="q.question_text"
                      placeholder="Enter the question text here..."
                    />
                  </div>

                  <!-- Options Builder -->
                  <div class="options-builder">
                    <div class="options-subhead">
                      <span class="options-hint">Select the radio button next to the correct answer:</span>
                      @if (q.options.length < 6) {
                        <button type="button" (click)="addOption(q)" class="btn btn-xs btn-outline">
                          + Add Option
                        </button>
                      }
                    </div>

                    @for (opt of q.options; track $index; let optIndex = $index) {
                      <div class="option-builder-row">
                        <input
                          type="radio"
                          [name]="'correct_' + qIndex"
                          [checked]="opt.is_correct"
                          (change)="setCorrectOption(q, optIndex)"
                          title="Mark as correct option"
                        />
                        <input
                          type="text"
                          class="form-input opt-input"
                          [(ngModel)]="opt.option_text"
                          [placeholder]="'Option ' + (optIndex + 1)"
                        />
                        @if (opt.is_correct) {
                          <span class="badge badge-success">Correct</span>
                        }
                        @if (q.options.length > 2) {
                          <button type="button" (click)="removeOption(q, optIndex)" class="remove-opt-btn" title="Remove Option">✕</button>
                        }
                      </div>
                    }
                  </div>
                </div>
              }
            </div>

            <div class="builder-actions">
              <button type="button" (click)="closeCreateQuiz()" class="btn btn-secondary">Cancel</button>
              <button type="button" (click)="saveQuiz()" class="btn btn-primary btn-lg" [disabled]="isSubmitting">
                @if (isSubmitting) {
                  <span>Saving Assessment...</span>
                } @else {
                  <span>{{ editingQuizId ? 'Update Assessment' : 'Save Assessment' }}</span>
                }
              </button>
            </div>
          </div>
        }

        <!-- Quizzes Table -->
        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading assessments...</span>
          </div>
        } @else if (quizzes.length === 0) {
          <div class="empty-block card">
            <h3>No assessments configured yet</h3>
            <p>Assess student comprehension by creating multiple-choice quizzes with strict server-side grading, time limits, and attempt rules.</p>
            <button (click)="openCreateQuiz()" class="btn btn-primary">Create First Assessment</button>
          </div>
        } @else {
          <div class="table-container card">
            <table>
              <thead>
                <tr>
                  <th>Title & Description</th>
                  <th>Questions</th>
                  <th>Passing</th>
                  <th>Time Limit</th>
                  <th>Attempts</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                @for (quiz of quizzes; track quiz.id) {
                  <tr>
                    <td>
                      <div class="quiz-title-cell">
                        <strong>{{ quiz.title }}</strong>
                        <span class="quiz-desc-text">{{ quiz.description || 'No description provided' }}</span>
                      </div>
                    </td>
                    <td>
                      <span class="badge badge-neutral">{{ quiz.questions.length }} Qs</span>
                    </td>
                    <td>
                      <span class="badge badge-primary">{{ quiz.passing_score }}%</span>
                    </td>
                    <td>
                      <span class="time-limit-text">
                        {{ quiz.time_limit_minutes ? quiz.time_limit_minutes + ' min' : 'Untimed' }}
                      </span>
                    </td>
                    <td>
                      <span>{{ quiz.max_attempts > 0 ? quiz.max_attempts + ' max' : 'Unlimited' }}</span>
                    </td>
                    <td>
                      @if (quiz.is_published) {
                        <span class="badge badge-success">Published</span>
                      } @else {
                        <span class="badge badge-draft">Draft</span>
                      }
                    </td>
                    <td>
                      <div class="action-buttons">
                        <button
                          (click)="togglePublish(quiz.id)"
                          class="btn btn-sm"
                          [ngClass]="quiz.is_published ? 'btn-secondary' : 'btn-outline'"
                          title="Toggle draft or published state"
                        >
                          {{ quiz.is_published ? 'Unpublish' : 'Publish' }}
                        </button>
                        <button (click)="previewQuiz(quiz)" class="btn btn-sm btn-outline">
                          Preview
                        </button>
                        <button (click)="editQuiz(quiz)" class="btn btn-sm btn-secondary">
                          Edit
                        </button>
                        <button (click)="deleteQuiz(quiz.id)" class="btn btn-sm btn-danger">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }

        <!-- Preview Modal -->
        @if (previewTarget) {
          <div class="modal-backdrop" (click)="closePreview()">
            <div class="modal-card card" (click)="$event.stopPropagation()">
              <div class="modal-header">
                <div>
                  <span class="badge badge-primary">Assessment Preview</span>
                  <h2>{{ previewTarget.title }}</h2>
                </div>
                <button (click)="closePreview()" class="close-modal-btn">✕</button>
              </div>

              <div class="modal-body">
                <div class="preview-meta-row">
                  <span>Passing: <strong>{{ previewTarget.passing_score }}%</strong></span>
                  <span>Time Limit: <strong>{{ previewTarget.time_limit_minutes ? previewTarget.time_limit_minutes + ' min' : 'Untimed' }}</strong></span>
                  <span>Max Attempts: <strong>{{ previewTarget.max_attempts > 0 ? previewTarget.max_attempts : 'Unlimited' }}</strong></span>
                </div>

                @if (previewTarget.description) {
                  <p class="preview-description">{{ previewTarget.description }}</p>
                }

                <div class="preview-questions">
                  @for (q of previewTarget.questions; track q.id; let i = $index) {
                    <div class="preview-q-card">
                      <div class="preview-q-header">
                        <strong>Question {{ i + 1 }}</strong>
                        <span class="badge badge-neutral">{{ q.points }} pt(s)</span>
                      </div>
                      <p class="preview-q-text">{{ q.question_text }}</p>
                      <div class="preview-options">
                        @for (opt of q.options; track opt.id) {
                          <div class="preview-opt-item" [class.marked-correct]="opt.is_correct">
                            <span class="opt-bullet"></span>
                            <span>{{ opt.option_text }}</span>
                            @if (opt.is_correct) {
                              <span class="badge badge-success badge-sm">Answer Key</span>
                            }
                          </div>
                        }
                      </div>
                    </div>
                  }
                </div>
              </div>

              <div class="modal-footer">
                <button (click)="closePreview()" class="btn btn-secondary">Close Preview</button>
              </div>
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .quiz-mgr-page {
      padding: 2.5rem 0 4rem 0;
      background-color: var(--bg-app);
      min-height: calc(100vh - 120px);
    }
    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      flex-wrap: wrap;
      gap: 1rem;
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
    .subtitle {
      color: var(--text-muted);
      margin-top: 0.25rem;
    }
    .quiz-builder-card {
      padding: 2.25rem;
      margin-bottom: 2.5rem;
      border: 1px solid var(--border-color);
    }
    .builder-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1.5rem;
      border-bottom: 1px solid var(--border-light);
      padding-bottom: 1rem;
    }
    .builder-subtitle {
      font-size: 0.9rem;
      color: var(--text-muted);
      margin-top: 0.2rem;
    }
    .form-row {
      display: flex;
      gap: 1.25rem;
      margin-bottom: 1rem;
      flex-wrap: wrap;
    }
    .flex-1 { flex: 1; min-width: 180px; }
    .flex-2 { flex: 2; min-width: 280px; }
    .form-group {
      margin-bottom: 1.25rem;
      display: flex;
      flex-direction: column;
    }
    .form-label {
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 0.4rem;
      color: var(--text-main);
    }
    .form-input, .form-textarea {
      padding: 0.75rem 1rem;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      font-size: 0.95rem;
      background-color: var(--bg-card);
      color: var(--text-main);
      width: 100%;
    }
    .field-hint {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 0.25rem;
    }
    .form-check-group {
      margin-bottom: 1.75rem;
      padding: 0.75rem 1rem;
      background-color: var(--bg-subtle);
      border-radius: var(--radius-md);
    }
    .checkbox-label {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      cursor: pointer;
      font-size: 0.95rem;
    }
    .questions-builder-section {
      margin-top: 2rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--border-light);
    }
    .builder-subhead {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.5rem;
    }
    .total-pts-badge {
      font-size: 0.8rem;
      background-color: var(--bg-subtle);
      color: var(--text-muted);
      padding: 0.2rem 0.6rem;
      border-radius: var(--radius-full);
      font-weight: 600;
      margin-left: 0.5rem;
    }
    .question-builder-item {
      padding: 1.5rem;
      margin-bottom: 1.5rem;
      background-color: var(--bg-subtle);
      border: 1px solid var(--border-light);
    }
    .q-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }
    .q-left-meta {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .q-title-label {
      font-weight: 700;
      font-size: 0.95rem;
      color: var(--primary);
    }
    .reorder-btns {
      display: flex;
      gap: 0.25rem;
    }
    .btn-icon {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-xs);
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 0.8rem;
    }
    .btn-icon:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
    .q-meta-actions {
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    .pts-input-box {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.85rem;
    }
    .pts-input {
      width: 60px;
      padding: 0.25rem 0.5rem;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
    }
    .options-builder {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      margin-top: 1rem;
    }
    .options-subhead {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .options-hint {
      font-size: 0.8rem;
      color: var(--text-muted);
      font-weight: 600;
    }
    .option-builder-row {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .opt-input {
      flex: 1;
      padding: 0.5rem 0.75rem;
    }
    .remove-opt-btn {
      background: none;
      border: none;
      color: var(--danger);
      font-size: 0.9rem;
      cursor: pointer;
      padding: 0.25rem;
    }
    .builder-actions {
      display: flex;
      justify-content: flex-end;
      gap: 1rem;
      margin-top: 2rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--border-light);
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
      padding: 1rem 1.25rem;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border-light);
    }
    td {
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border-light);
      font-size: 0.9rem;
      vertical-align: middle;
    }
    .quiz-title-cell {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }
    .quiz-desc-text {
      font-size: 0.8rem;
      color: var(--text-muted);
      max-width: 320px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .badge-draft {
      background-color: #f3f4f6;
      color: #6b7280;
    }
    .action-buttons {
      display: flex;
      gap: 0.4rem;
      flex-wrap: wrap;
    }
    .empty-block {
      padding: 4rem 2rem;
      text-align: center;
      max-width: 600px;
      margin: 2rem auto;
    }
    .empty-block h3 {
      margin-bottom: 0.5rem;
    }
    .empty-block p {
      color: var(--text-muted);
      margin-bottom: 1.5rem;
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
      max-width: 720px;
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
    .close-modal-btn {
      background: none;
      border: none;
      font-size: 1.25rem;
      cursor: pointer;
      color: var(--text-muted);
    }
    .preview-meta-row {
      display: flex;
      gap: 1.5rem;
      margin-bottom: 1rem;
      font-size: 0.9rem;
      color: var(--text-muted);
    }
    .preview-description {
      font-size: 0.95rem;
      color: var(--text-muted);
      margin-bottom: 1.5rem;
      line-height: 1.5;
    }
    .preview-questions {
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
      margin-bottom: 1.5rem;
    }
    .preview-q-card {
      padding: 1.25rem;
      border: 1px solid var(--border-light);
      border-radius: var(--radius-md);
      background-color: var(--bg-subtle);
    }
    .preview-q-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 0.5rem;
    }
    .preview-q-text {
      font-weight: 600;
      margin-bottom: 1rem;
    }
    .preview-options {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .preview-opt-item {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      padding: 0.6rem 0.8rem;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      background: var(--bg-card);
      font-size: 0.9rem;
    }
    .preview-opt-item.marked-correct {
      border-color: var(--success);
      background-color: rgba(16, 185, 129, 0.08);
    }
    .opt-bullet {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      border: 2px solid var(--border-color);
    }
    .preview-opt-item.marked-correct .opt-bullet {
      background-color: var(--success);
      border-color: var(--success);
    }
    .badge-sm {
      font-size: 0.7rem;
      padding: 0.15rem 0.4rem;
      margin-left: auto;
    }
    .modal-footer {
      display: flex;
      justify-content: flex-end;
      padding-top: 1rem;
      border-top: 1px solid var(--border-light);
    }
    .loading-state {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
      padding: 4rem;
      color: var(--text-muted);
    }
    .spinner {
      width: 24px;
      height: 24px;
      border: 3px solid var(--border-color);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  `]
})
export class QuizEditorComponent implements OnInit {
  @Input() id!: string; // course_id

  course: CourseDetail | null = null;
  quizzes: Quiz[] = [];
  isLoading = true;
  showCreateForm = false;
  isSubmitting = false;
  editingQuizId: number | null = null;
  previewTarget: Quiz | null = null;

  feedbackMessage = '';
  isError = false;

  quizForm: QuizCreatePayload = {
    title: '',
    description: '',
    passing_score: 70,
    time_limit_minutes: undefined,
    max_attempts: 3,
    is_published: true,
    section_id: undefined,
    questions: []
  };

  constructor(
    private courseService: CourseService,
    private instructorService: InstructorService
  ) {}

  ngOnInit(): void {
    if (this.id) {
      this.loadData(Number(this.id));
    }
  }

  loadData(courseId: number): void {
    this.isLoading = true;
    this.courseService.getCourse(courseId).subscribe({
      next: (courseData) => {
        this.course = courseData;
        this.loadQuizzes(courseId);
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  loadQuizzes(courseId: number): void {
    this.instructorService.getCourseQuizzes(courseId).subscribe({
      next: (data) => {
        this.quizzes = data;
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  openCreateQuiz(): void {
    this.editingQuizId = null;
    this.quizForm = {
      title: '',
      description: '',
      passing_score: 70,
      time_limit_minutes: undefined,
      max_attempts: 3,
      is_published: true,
      section_id: undefined,
      questions: [this.createBlankQuestion(1)]
    };
    this.showCreateForm = true;
  }

  closeCreateQuiz(): void {
    this.showCreateForm = false;
    this.editingQuizId = null;
  }

  createBlankQuestion(orderIndex: number): QuestionCreatePayload {
    return {
      question_text: '',
      order_index: orderIndex,
      points: 1,
      options: [
        { option_text: '', is_correct: true },
        { option_text: '', is_correct: false },
        { option_text: '', is_correct: false },
        { option_text: '', is_correct: false }
      ]
    };
  }

  addQuestion(): void {
    this.quizForm.questions.push(this.createBlankQuestion(this.quizForm.questions.length + 1));
  }

  removeQuestion(index: number): void {
    this.quizForm.questions.splice(index, 1);
    this.quizForm.questions.forEach((q, idx) => {
      q.order_index = idx + 1;
    });
  }

  moveQuestionUp(index: number): void {
    if (index > 0) {
      const temp = this.quizForm.questions[index];
      this.quizForm.questions[index] = this.quizForm.questions[index - 1];
      this.quizForm.questions[index - 1] = temp;
      this.quizForm.questions.forEach((q, idx) => {
        q.order_index = idx + 1;
      });
    }
  }

  moveQuestionDown(index: number): void {
    if (index < this.quizForm.questions.length - 1) {
      const temp = this.quizForm.questions[index];
      this.quizForm.questions[index] = this.quizForm.questions[index + 1];
      this.quizForm.questions[index + 1] = temp;
      this.quizForm.questions.forEach((q, idx) => {
        q.order_index = idx + 1;
      });
    }
  }

  addOption(q: QuestionCreatePayload): void {
    if (q.options.length < 6) {
      q.options.push({ option_text: '', is_correct: false });
    }
  }

  removeOption(q: QuestionCreatePayload, optIndex: number): void {
    if (q.options.length > 2) {
      const wasCorrect = q.options[optIndex].is_correct;
      q.options.splice(optIndex, 1);
      if (wasCorrect && q.options.length > 0) {
        q.options[0].is_correct = true;
      }
    }
  }

  setCorrectOption(q: QuestionCreatePayload, correctIndex: number): void {
    q.options.forEach((opt, idx) => {
      opt.is_correct = idx === correctIndex;
    });
  }

  calculateTotalPoints(): number {
    return this.quizForm.questions.reduce((sum, q) => sum + (q.points || 1), 0);
  }

  editQuiz(quiz: Quiz): void {
    this.editingQuizId = quiz.id;
    this.instructorService.getQuizDetail(quiz.id).subscribe({
      next: (fullQuiz) => {
        this.quizForm = {
          title: fullQuiz.title,
          description: fullQuiz.description || '',
          passing_score: fullQuiz.passing_score,
          time_limit_minutes: fullQuiz.time_limit_minutes,
          max_attempts: fullQuiz.max_attempts,
          is_published: fullQuiz.is_published,
          section_id: fullQuiz.section_id,
          questions: fullQuiz.questions.map((q, idx) => ({
            id: q.id,
            question_text: q.question_text,
            order_index: idx + 1,
            points: q.points,
            options: q.options.map(opt => ({
              id: opt.id,
              option_text: opt.option_text,
              is_correct: !!opt.is_correct
            }))
          }))
        };
        this.showCreateForm = true;
      },
      error: (err) => {
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to load quiz details.';
      }
    });
  }

  previewQuiz(quiz: Quiz): void {
    this.instructorService.getQuizDetail(quiz.id).subscribe({
      next: (fullQuiz) => {
        this.previewTarget = fullQuiz;
      },
      error: () => {
        this.previewTarget = quiz;
      }
    });
  }

  closePreview(): void {
    this.previewTarget = null;
  }

  togglePublish(quizId: number): void {
    this.instructorService.toggleQuizPublication(quizId).subscribe({
      next: (updated) => {
        this.feedbackMessage = `Quiz '${updated.title}' is now ${updated.is_published ? 'published' : 'draft'}.`;
        this.isError = false;
        if (this.course) {
          this.loadQuizzes(this.course.id);
        }
      },
      error: (err) => {
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to update publication status.';
      }
    });
  }

  saveQuiz(): void {
    if (!this.course) return;

    if (!this.quizForm.title.trim()) {
      this.isError = true;
      this.feedbackMessage = 'Please enter a quiz title.';
      return;
    }

    if (this.quizForm.questions.length === 0) {
      this.isError = true;
      this.feedbackMessage = 'An assessment must have at least one question.';
      return;
    }

    for (let i = 0; i < this.quizForm.questions.length; i++) {
      const q = this.quizForm.questions[i];
      if (!q.question_text.trim()) {
        this.isError = true;
        this.feedbackMessage = `Question ${i + 1} text cannot be empty.`;
        return;
      }
      const hasEmptyOption = q.options.some(o => !o.option_text.trim());
      if (hasEmptyOption) {
        this.isError = true;
        this.feedbackMessage = `Question ${i + 1} has empty answer options.`;
        return;
      }
      const hasCorrect = q.options.some(o => o.is_correct);
      if (!hasCorrect) {
        this.isError = true;
        this.feedbackMessage = `Question ${i + 1} must have a marked correct option.`;
        return;
      }
    }

    this.isSubmitting = true;
    this.feedbackMessage = '';
    this.isError = false;

    if (this.editingQuizId) {
      // Update existing quiz
      this.instructorService.updateQuiz(this.editingQuizId, {
        title: this.quizForm.title,
        description: this.quizForm.description,
        passing_score: this.quizForm.passing_score,
        time_limit_minutes: this.quizForm.time_limit_minutes,
        max_attempts: this.quizForm.max_attempts,
        is_published: this.quizForm.is_published,
        section_id: this.quizForm.section_id
      }).subscribe({
        next: () => {
          this.isSubmitting = false;
          this.feedbackMessage = 'Assessment successfully updated!';
          this.closeCreateQuiz();
          this.loadQuizzes(this.course!.id);
        },
        error: (err) => {
          this.isSubmitting = false;
          this.isError = true;
          this.feedbackMessage = err.error?.detail || 'Failed to update quiz.';
        }
      });
    } else {
      // Create new quiz
      this.instructorService.createQuiz(this.course.id, this.quizForm).subscribe({
        next: () => {
          this.isSubmitting = false;
          this.feedbackMessage = 'Assessment successfully authored and saved!';
          this.closeCreateQuiz();
          this.loadQuizzes(this.course!.id);
        },
        error: (err) => {
          this.isSubmitting = false;
          this.isError = true;
          this.feedbackMessage = err.error?.detail || 'Failed to create quiz.';
        }
      });
    }
  }

  deleteQuiz(quizId: number): void {
    if (!confirm('Are you sure you want to delete this quiz? Historical attempts will be preserved.')) return;

    this.instructorService.deleteQuiz(quizId).subscribe({
      next: () => {
        this.feedbackMessage = 'Quiz assessment successfully deleted.';
        this.isError = false;
        if (this.course) {
          this.loadQuizzes(this.course.id);
        }
      },
      error: (err) => {
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to delete quiz.';
      }
    });
  }
}
