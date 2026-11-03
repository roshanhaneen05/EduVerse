import { Component, OnInit, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AssignmentService } from '../../core/services/assignment.service';
import { Assignment, AssignmentSubmission } from '../../core/models/assignment.model';

@Component({
  selector: 'app-assignment-detail',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="assignment-page">
      <div class="container">
        <!-- Back Navigation -->
        <a [routerLink]="['/courses', courseId]" class="back-link">
          ← Back to Course Syllabus
        </a>

        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading assignment details...</span>
          </div>
        } @else if (!assignment) {
          <div class="empty-block card">
            <h3>Assignment Not Found</h3>
            <p>The requested assignment is unavailable, unpublished, or you may not be enrolled in this course.</p>
            <a [routerLink]="['/courses', courseId]" class="btn btn-primary">Return to Course</a>
          </div>
        } @else {
          <!-- Assignment Header Card -->
          <div class="assignment-header-card card">
            <div class="header-top-row">
              <div class="badge-group">
                @if (assignment.section_title) {
                  <span class="badge badge-primary">{{ assignment.section_title }}</span>
                }
                <span class="badge max-marks-badge">Max Marks: {{ assignment.max_marks }}</span>
                @if (assignment.is_closed) {
                  <span class="badge badge-danger">Closed</span>
                }
              </div>

              @if (assignment.due_date) {
                <div class="due-date-pill" [class.past-due]="isPastDue()">
                  <span class="due-label">{{ isPastDue() ? 'Deadline Passed:' : 'Due Date:' }}</span>
                  <span class="due-time">{{ assignment.due_date | date:'medium' }}</span>
                </div>
              }
            </div>

            <h1 class="assignment-main-title">{{ assignment.title }}</h1>
            @if (assignment.description) {
              <p class="assignment-subtitle">{{ assignment.description }}</p>
            }
          </div>

          <div class="assignment-body-layout">
            <!-- Left Column: Instructions & Guidelines -->
            <div class="instructions-column">
              <div class="card instructions-card">
                <h2>Assignment Prompt & Deliverables</h2>
                <div class="instructions-content" [innerHTML]="formatInstructions(assignment.instructions)"></div>
              </div>
            </div>

            <!-- Right Column: Submission & Grading Status -->
            <div class="submission-column">
              <!-- Grading Result Card (if graded) -->
              @if (mySubmission && mySubmission.grade !== null && mySubmission.grade !== undefined) {
                <div class="card grade-result-card">
                  <div class="grade-badge-header">
                    <span class="grade-status-title">Assessed Grade</span>
                    <span class="badge badge-success">Evaluated</span>
                  </div>
                  <div class="score-display">
                    <span class="score-number">{{ mySubmission.grade }}</span>
                    <span class="score-total">/ {{ assignment.max_marks }} Marks</span>
                    <span class="score-percent">({{ getPercentage(mySubmission.grade, assignment.max_marks) }}%)</span>
                  </div>

                  @if (mySubmission.feedback) {
                    <div class="feedback-section">
                      <span class="feedback-heading">Instructor Feedback:</span>
                      <blockquote class="feedback-quote">{{ mySubmission.feedback }}</blockquote>
                    </div>
                  }
                  @if (mySubmission.graded_at) {
                    <div class="graded-timestamp">
                      Graded on {{ mySubmission.graded_at | date:'medium' }}
                    </div>
                  }
                </div>
              }

              <!-- Active Submission / Submission Form Card -->
              <div class="card submission-card">
                <div class="submission-card-header">
                  <h3>Your Work</h3>
                  @if (mySubmission) {
                    <span class="badge" [ngClass]="getSubmissionBadge(mySubmission.status)">
                      {{ mySubmission.status | titlecase }}
                    </span>
                  }
                </div>

                @if (feedbackMessage) {
                  <div class="alert" [ngClass]="isError ? 'alert-danger' : 'alert-success'">
                    {{ feedbackMessage }}
                  </div>
                }

                <!-- Submitted State (Read Mode) -->
                @if (mySubmission && !isEditingSubmission) {
                  <div class="submitted-view">
                    <div class="meta-status-row">
                      <span class="meta-item">
                        Submitted: <strong>{{ mySubmission.submitted_at | date:'medium' }}</strong>
                      </span>
                      @if (mySubmission.is_late) {
                        <span class="badge badge-danger">Late Submission</span>
                      }
                    </div>

                    <div class="submitted-text-display">
                      {{ mySubmission.submission_text }}
                    </div>

                    @if (assignment.allow_resubmission && !assignment.is_closed) {
                      <div class="submission-actions">
                        <button (click)="enableEditMode()" class="btn btn-outline btn-block">
                          Edit / Resubmit Work
                        </button>
                      </div>
                    } @else if (assignment.is_closed) {
                      <div class="closed-notice">
                        Submissions for this assignment are closed.
                      </div>
                    }
                  </div>
                }

                <!-- Edit / Submission Form Mode -->
                @if (!mySubmission || isEditingSubmission) {
                  @if (assignment.is_closed) {
                    <div class="closed-notice alert alert-danger">
                      This assignment has been closed for submissions by the instructor.
                    </div>
                  } @else {
                    <form [formGroup]="submissionForm" (ngSubmit)="onSubmitWork()" class="submission-form">
                      <div class="form-group">
                        <label class="form-label" for="submission_text">
                          Written Response & Solutions (Markdown supported):
                        </label>
                        <textarea
                          id="submission_text"
                          rows="10"
                          class="form-textarea font-mono"
                          formControlName="submission_text"
                          placeholder="Type or paste your complete solution, architecture explanation, code samples, or analysis here..."
                        ></textarea>
                        @if (submissionForm.get('submission_text')?.invalid && submissionForm.get('submission_text')?.touched) {
                          <div class="form-error">Response must be at least 5 characters long.</div>
                        }
                      </div>

                      <div class="file-storage-note">
                        <span class="storage-icon">ℹ️</span>
                        <span>Written responses & markdown formatting supported. Cloud file uploads will be available in an upcoming release.</span>
                      </div>

                      <div class="form-actions">
                        @if (isEditingSubmission) {
                          <button type="button" (click)="isEditingSubmission = false" class="btn btn-secondary">
                            Cancel
                          </button>
                        }
                        <button
                          type="submit"
                          class="btn btn-primary"
                          [class.btn-block]="!isEditingSubmission"
                          [disabled]="submissionForm.invalid || isSubmitting"
                        >
                          @if (isSubmitting) {
                            <span>Submitting Work...</span>
                          } @else {
                            <span>{{ isEditingSubmission ? 'Update Submission' : 'Submit Assignment' }}</span>
                          }
                        </button>
                      </div>
                    </form>
                  }
                }
              </div>
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .assignment-page {
      padding: 2.5rem 0 4rem 0;
      background-color: var(--bg-app);
      min-height: calc(100vh - 140px);
    }
    .back-link {
      font-size: 0.9rem;
      color: var(--text-muted);
      font-weight: 600;
      margin-bottom: 1.25rem;
      display: inline-block;
    }
    .assignment-header-card {
      padding: 2rem;
      margin-bottom: 2rem;
      border-left: 4px solid var(--primary);
    }
    .header-top-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      flex-wrap: wrap;
      gap: 0.75rem;
    }
    .badge-group {
      display: flex;
      gap: 0.5rem;
      align-items: center;
    }
    .max-marks-badge {
      background-color: #eef2ff;
      color: var(--primary);
      font-weight: 700;
    }
    .due-date-pill {
      font-size: 0.85rem;
      background: var(--bg-subtle);
      padding: 0.35rem 0.75rem;
      border-radius: var(--radius-sm);
      display: flex;
      gap: 0.4rem;
    }
    .due-date-pill.past-due {
      background: #fee2e2;
      color: #991b1b;
    }
    .due-label {
      font-weight: 600;
    }
    .assignment-main-title {
      font-size: 2rem;
      margin-bottom: 0.4rem;
    }
    .assignment-subtitle {
      color: var(--text-muted);
      font-size: 1.05rem;
      margin: 0;
    }
    .assignment-body-layout {
      display: grid;
      grid-template-columns: 1.2fr 1fr;
      gap: 2rem;
      align-items: start;
    }
    @media (max-width: 900px) {
      .assignment-body-layout {
        grid-template-columns: 1fr;
      }
    }
    .instructions-card {
      padding: 2rem;
    }
    .instructions-card h2 {
      font-size: 1.3rem;
      margin-bottom: 1.25rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--border-light);
    }
    .instructions-content {
      font-size: 0.95rem;
      line-height: 1.7;
      color: var(--text-main);
    }
    .submission-column {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }
    .grade-result-card {
      padding: 1.75rem;
      background: linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%);
      border: 1px solid #bbf7d0;
    }
    .grade-badge-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.75rem;
    }
    .grade-status-title {
      font-size: 0.85rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #166534;
    }
    .score-display {
      display: flex;
      align-items: baseline;
      gap: 0.5rem;
      margin-bottom: 1rem;
    }
    .score-number {
      font-size: 2.5rem;
      font-weight: 900;
      color: #15803d;
    }
    .score-total {
      font-size: 1.1rem;
      color: var(--text-muted);
    }
    .score-percent {
      font-size: 1rem;
      font-weight: 700;
      color: #166534;
    }
    .feedback-section {
      padding-top: 1rem;
      border-top: 1px solid #dcfce7;
      margin-bottom: 0.5rem;
    }
    .feedback-heading {
      font-size: 0.85rem;
      font-weight: 700;
      color: #166534;
      display: block;
      margin-bottom: 0.4rem;
    }
    .feedback-quote {
      font-style: italic;
      color: #1f2937;
      margin: 0;
      padding-left: 0.75rem;
      border-left: 3px solid #86efac;
      font-size: 0.95rem;
      line-height: 1.6;
    }
    .graded-timestamp {
      font-size: 0.75rem;
      color: #166534;
      margin-top: 0.75rem;
    }
    .submission-card {
      padding: 1.75rem;
    }
    .submission-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--border-light);
    }
    .meta-status-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      font-size: 0.85rem;
    }
    .submitted-text-display {
      background: #f8fafc;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      padding: 1.25rem;
      font-family: var(--font-mono);
      font-size: 0.9rem;
      white-space: pre-wrap;
      line-height: 1.6;
      margin-bottom: 1.25rem;
      max-height: 350px;
      overflow-y: auto;
    }
    .submission-actions {
      margin-top: 1rem;
    }
    .btn-block {
      width: 100%;
    }
    .font-mono {
      font-family: var(--font-mono);
      font-size: 0.9rem;
    }
    .file-storage-note {
      display: flex;
      gap: 0.5rem;
      font-size: 0.8rem;
      color: var(--text-muted);
      background: var(--bg-subtle);
      padding: 0.75rem;
      border-radius: var(--radius-md);
      margin-bottom: 1.25rem;
      line-height: 1.4;
    }
    .storage-icon {
      font-size: 1rem;
    }
    .form-actions {
      display: flex;
      gap: 0.75rem;
      justify-content: flex-end;
    }
    .closed-notice {
      padding: 1rem;
      text-align: center;
      color: var(--text-muted);
      font-style: italic;
    }
    .loading-state, .empty-block {
      text-align: center;
      padding: 4rem 2rem;
    }
    .spinner {
      width: 28px;
      height: 28px;
      border: 3px solid var(--border-color);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 1rem auto;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  `]
})
export class AssignmentDetailComponent implements OnInit {
  @Input() courseId!: string;
  @Input() assignmentId!: string;

  assignment: Assignment | null = null;
  mySubmission: AssignmentSubmission | null = null;
  isLoading = true;

  submissionForm: FormGroup;
  isSubmitting = false;
  isEditingSubmission = false;
  feedbackMessage = '';
  isError = false;

  constructor(
    private assignmentService: AssignmentService,
    private fb: FormBuilder
  ) {
    this.submissionForm = this.fb.group({
      submission_text: ['', [Validators.required, Validators.minLength(5)]]
    });
  }

  ngOnInit(): void {
    if (this.assignmentId) {
      this.loadAssignmentData(Number(this.assignmentId));
    }
  }

  loadAssignmentData(id: number): void {
    this.isLoading = true;
    this.assignmentService.getAssignment(id).subscribe({
      next: (data) => {
        this.assignment = data;
        this.loadMySubmission(id);
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  loadMySubmission(id: number): void {
    this.assignmentService.getMySubmission(id).subscribe({
      next: (sub) => {
        this.mySubmission = sub;
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  enableEditMode(): void {
    if (this.mySubmission) {
      this.submissionForm.patchValue({
        submission_text: this.mySubmission.submission_text
      });
    }
    this.isEditingSubmission = true;
  }

  onSubmitWork(): void {
    if (this.submissionForm.invalid || !this.assignment) return;

    this.isSubmitting = true;
    this.feedbackMessage = '';
    this.isError = false;

    this.assignmentService.submitAssignment(this.assignment.id, this.submissionForm.value).subscribe({
      next: (sub) => {
        this.isSubmitting = false;
        this.mySubmission = sub;
        this.isEditingSubmission = false;
        this.feedbackMessage = 'Work successfully submitted for grading!';
      },
      error: (err) => {
        this.isSubmitting = false;
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to submit work.';
      }
    });
  }

  isPastDue(): boolean {
    if (!this.assignment?.due_date) return false;
    return new Date() > new Date(this.assignment.due_date);
  }

  getPercentage(grade: number, max: number): number {
    if (!max || max <= 0) return 0;
    return Math.round((grade / max) * 100);
  }

  getSubmissionBadge(status: string): string {
    switch (status) {
      case 'graded': return 'badge-success';
      case 'resubmitted': return 'badge-warning';
      default: return 'badge-neutral';
    }
  }

  formatInstructions(raw: string): string {
    if (!raw) return '';
    return raw
      .replace(/### (.*$)/gim, '<h3>$1</h3>')
      .replace(/## (.*$)/gim, '<h2>$1</h2>')
      .replace(/# (.*$)/gim, '<h2>$1</h2>')
      .replace(/```([\s\S]*?)```/gim, '<pre><code>$1</code></pre>')
      .replace(/`([^`]+)`/gim, '<code>$1</code>')
      .replace(/\n\n/gim, '</p><p>')
      .replace(/\n/gim, '<br/>');
  }
}

