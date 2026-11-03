import { Component, OnInit, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { CourseService } from '../../core/services/course.service';
import { InstructorService } from '../../core/services/instructor.service';
import { CourseDetail, CourseSection } from '../../core/models/course.model';
import {
  Assignment,
  AssignmentSubmission,
  SubmissionGradePayload,
} from '../../core/models/assignment.model';

@Component({
  selector: 'app-assignment-manager',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink],
  template: `
    <div class="assignment-mgr-page">
      <div class="container">
        <!-- Navigation Header -->
        <div class="page-header">
          <div>
            <a routerLink="/instructor/dashboard" class="back-link">← Back to Instructor Hub</a>
            <h1>Assignments & Grading Portal</h1>
            <p class="subtitle" *ngIf="course">
              Course: <strong>{{ course.title }}</strong>
            </p>
          </div>
          <button (click)="openAddForm()" class="btn btn-primary" *ngIf="!showForm && !activeSubmissionsAssignment">
            + Create New Assignment
          </button>
        </div>

        <!-- Global Alert Message -->
        @if (feedbackMessage) {
          <div class="alert" [ngClass]="isError ? 'alert-danger' : 'alert-success'">
            {{ feedbackMessage }}
          </div>
        }

        <!-- Add / Edit Assignment Form -->
        @if (showForm) {
          <div class="card form-card">
            <div class="form-header">
              <h3>{{ editingAssignmentId ? 'Edit Assignment' : 'Create New Practical Assignment' }}</h3>
              <button (click)="closeForm()" class="btn btn-sm btn-secondary">Close Form</button>
            </div>

            <form [formGroup]="assignmentForm" (ngSubmit)="onSaveAssignment()">
              <div class="form-row">
                <div class="form-group flex-3">
                  <label class="form-label" for="title">Assignment Title</label>
                  <input
                    id="title"
                    type="text"
                    class="form-input"
                    formControlName="title"
                    placeholder="e.g. Capstone Architecture Blueprint & Domain Models"
                  />
                </div>

                <div class="form-group flex-1">
                  <label class="form-label" for="max_marks">Maximum Marks</label>
                  <input
                    id="max_marks"
                    type="number"
                    min="1"
                    class="form-input"
                    formControlName="max_marks"
                  />
                </div>
              </div>

              <div class="form-row">
                <div class="form-group flex-2">
                  <label class="form-label" for="section_id">Curriculum Module / Section (Optional)</label>
                  <select id="section_id" class="form-input" formControlName="section_id">
                    <option [ngValue]="null">No Section (General Course Assignment)</option>
                    @for (sec of sections; track sec.id) {
                      <option [ngValue]="sec.id">{{ sec.order_index }}. {{ sec.title }}</option>
                    }
                  </select>
                </div>

                <div class="form-group flex-2">
                  <label class="form-label" for="due_date">Submission Deadline (Optional)</label>
                  <input
                    id="due_date"
                    type="datetime-local"
                    class="form-input"
                    formControlName="due_date"
                  />
                </div>
              </div>

              <div class="form-group">
                <label class="form-label" for="description">Summary / Overview</label>
                <input
                  id="description"
                  type="text"
                  class="form-input"
                  formControlName="description"
                  placeholder="Brief summary of assignment goals..."
                />
              </div>

              <div class="form-group">
                <label class="form-label" for="instructions">Detailed Instructions & Grading Rubric (Markdown)</label>
                <textarea
                  id="instructions"
                  rows="6"
                  class="form-textarea font-mono"
                  formControlName="instructions"
                  placeholder="### Prompt\n\nOutline the problem statement, required deliverables, evaluation rubric, and submission criteria..."
                ></textarea>
              </div>

              <div class="form-checkboxes">
                <label class="checkbox-label">
                  <input type="checkbox" formControlName="allow_resubmission" />
                  <span>Allow student resubmissions before deadline</span>
                </label>
                <label class="checkbox-label">
                  <input type="checkbox" formControlName="is_published" />
                  <span>Publish assignment immediately to enrolled students</span>
                </label>
              </div>

              <div class="form-actions">
                <button type="button" (click)="closeForm()" class="btn btn-secondary">Cancel</button>
                <button type="submit" class="btn btn-primary" [disabled]="assignmentForm.invalid || isSaving">
                  @if (isSaving) {
                    <span>Saving...</span>
                  } @else {
                    <span>{{ editingAssignmentId ? 'Update Assignment' : 'Create Assignment' }}</span>
                  }
                </button>
              </div>
            </form>
          </div>
        }

        <!-- Submissions & Grading Portal View -->
        @if (activeSubmissionsAssignment) {
          <div class="submissions-portal">
            <div class="card portal-card">
              <div class="portal-header">
                <div>
                  <button (click)="closeSubmissionsPortal()" class="btn btn-sm btn-outline back-sub-btn">
                    ← Back to Assignments List
                  </button>
                  <h2>Submissions: {{ activeSubmissionsAssignment.title }}</h2>
                  <p class="subtitle">
                    Maximum Marks: <strong>{{ activeSubmissionsAssignment.max_marks }}</strong>
                    &nbsp;|&nbsp;
                    Total Submissions: <strong>{{ submissions.length }}</strong>
                  </p>
                </div>
              </div>

              @if (isLoadingSubmissions) {
                <div class="loading-state">
                  <div class="spinner"></div>
                  <span>Loading student submissions...</span>
                </div>
              } @else if (submissions.length === 0) {
                <div class="empty-block card">
                  <h3>No student submissions received yet</h3>
                  <p>When enrolled students submit their written work, their submissions will appear here for evaluation.</p>
                </div>
              } @else {
                <div class="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Student</th>
                        <th>Submitted At</th>
                        <th>Status</th>
                        <th>Grade</th>
                        <th style="width: 140px;">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      @for (s of submissions; track s.id) {
                        <tr>
                          <td>
                            <strong>{{ s.student?.full_name || 'Enrolled Student' }}</strong>
                            <div class="table-subtext">{{ s.student?.email }}</div>
                          </td>
                          <td>
                            {{ s.submitted_at | date:'medium' }}
                            @if (s.is_late) {
                              <span class="badge badge-danger badge-sm">Late</span>
                            }
                          </td>
                          <td>
                            <span class="badge" [ngClass]="getStatusBadge(s.status)">
                              {{ s.status | titlecase }}
                            </span>
                          </td>
                          <td>
                            @if (s.grade !== null && s.grade !== undefined) {
                              <strong class="grade-score">{{ s.grade }} / {{ activeSubmissionsAssignment.max_marks }}</strong>
                            } @else {
                              <span class="text-muted">Not Graded</span>
                            }
                          </td>
                          <td>
                            <button (click)="openGradingModal(s)" class="btn btn-sm btn-primary">
                              {{ s.grade !== null ? 'Edit Grade' : 'Grade' }}
                            </button>
                          </td>
                        </tr>
                      }
                    </tbody>
                  </table>
                </div>
              }
            </div>
          </div>
        }

        <!-- Instructor Grading Modal -->
        @if (gradingSubmission) {
          <div class="modal-backdrop">
            <div class="card modal-card grading-modal">
              <div class="modal-header">
                <div>
                  <h3>Grade Submission</h3>
                  <p class="subtitle">
                    Student: <strong>{{ gradingSubmission.student?.full_name }}</strong>
                    ({{ gradingSubmission.student?.email }})
                  </p>
                </div>
                <button (click)="closeGradingModal()" class="close-modal-btn">✕</button>
              </div>

              <div class="submission-content-preview">
                <label class="preview-label">Student Written Response:</label>
                <div class="submission-text-box">
                  {{ gradingSubmission.submission_text }}
                </div>
              </div>

              <div class="form-group">
                <label class="form-label" for="grade_input">
                  Awarded Marks (out of {{ activeSubmissionsAssignment?.max_marks }}):
                </label>
                <input
                  id="grade_input"
                  type="number"
                  step="0.5"
                  min="0"
                  [max]="activeSubmissionsAssignment?.max_marks || 100"
                  class="form-input"
                  [(ngModel)]="awardedGrade"
                />
              </div>

              <div class="form-group">
                <label class="form-label" for="feedback_input">Instructor Feedback & Comments:</label>
                <textarea
                  id="feedback_input"
                  rows="4"
                  class="form-textarea"
                  [(ngModel)]="gradingFeedback"
                  placeholder="Provide constructive feedback, recommendations, or grading rationale..."
                ></textarea>
              </div>

              @if (gradingError) {
                <div class="alert alert-danger">{{ gradingError }}</div>
              }

              <div class="form-actions">
                <button type="button" (click)="closeGradingModal()" class="btn btn-secondary">Cancel</button>
                <button
                  type="button"
                  (click)="saveGrade()"
                  class="btn btn-primary"
                  [disabled]="isGrading || awardedGrade === null || awardedGrade < 0 || awardedGrade > (activeSubmissionsAssignment?.max_marks || 100)"
                >
                  @if (isGrading) {
                    <span>Saving Grade...</span>
                  } @else {
                    <span>Save & Release Grade</span>
                  }
                </button>
              </div>
            </div>
          </div>
        }

        <!-- Main Assignment List View (shown when not viewing submissions portal) -->
        @if (!activeSubmissionsAssignment) {
          @if (isLoading) {
            <div class="loading-state">
              <div class="spinner"></div>
              <span>Loading course assignments...</span>
            </div>
          } @else if (assignments.length === 0) {
            <div class="empty-block card">
              <h3>No assignments created for this course yet</h3>
              <p>Add practical assignments to assess real-world application of concepts beyond multiple-choice quizzes.</p>
              <button (click)="openAddForm()" class="btn btn-primary">+ Create First Assignment</button>
            </div>
          } @else {
            <div class="assignments-grid">
              @for (a of assignments; track a.id) {
                <div class="assignment-card card" [class.archived]="a.is_archived">
                  <div class="assignment-card-header">
                    <div>
                      <div class="badge-row">
                        @if (a.is_published) {
                          <span class="badge badge-success">Published</span>
                        } @else {
                          <span class="badge badge-warning">Draft</span>
                        }
                        @if (a.is_closed) {
                          <span class="badge badge-neutral">Closed</span>
                        }
                        @if (a.is_archived) {
                          <span class="badge badge-danger">Archived</span>
                        }
                        <span class="max-marks-pill">{{ a.max_marks }} Marks</span>
                      </div>
                      <h3 class="assignment-title">{{ a.title }}</h3>
                      @if (a.description) {
                        <p class="assignment-desc">{{ a.description }}</p>
                      }
                    </div>
                  </div>

                  <div class="assignment-meta-row">
                    <div class="meta-item">
                      <span class="meta-label">Deadline:</span>
                      <span class="meta-value">{{ a.due_date ? (a.due_date | date:'short') : 'No deadline' }}</span>
                    </div>
                    <div class="meta-item">
                      <span class="meta-label">Submissions:</span>
                      <span class="meta-value"><strong>{{ a.submission_count || 0 }}</strong> received ({{ a.graded_count || 0 }} graded)</span>
                    </div>
                  </div>

                  <div class="assignment-actions-bar">
                    <button (click)="openSubmissionsPortal(a)" class="btn btn-sm btn-primary">
                      View Submissions ({{ a.submission_count || 0 }})
                    </button>
                    <button (click)="editAssignment(a)" class="btn btn-sm btn-secondary">
                      Edit
                    </button>
                    <button (click)="togglePublish(a)" class="btn btn-sm btn-outline">
                      {{ a.is_published ? 'Unpublish' : 'Publish' }}
                    </button>
                    <button (click)="toggleClose(a)" class="btn btn-sm btn-outline">
                      {{ a.is_closed ? 'Reopen' : 'Close' }}
                    </button>
                    <button (click)="deleteAssignment(a)" class="btn btn-sm btn-danger">
                      Delete
                    </button>
                  </div>
                </div>
              }
            </div>
          }
        }
      </div>
    </div>
  `,
  styles: [`
    .assignment-mgr-page {
      padding: 2.5rem 0 4rem 0;
      background-color: var(--bg-app);
      min-height: calc(100vh - 140px);
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
      margin-bottom: 0.5rem;
      display: inline-block;
    }
    .page-header h1 {
      font-size: 2rem;
      margin-bottom: 0.35rem;
    }
    .subtitle {
      color: var(--text-muted);
      font-size: 1.05rem;
    }
    .form-card {
      padding: 2rem;
      margin-bottom: 2.5rem;
      border: 2px solid var(--primary-border);
    }
    .form-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.5rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--border-light);
    }
    .form-row {
      display: flex;
      gap: 1.5rem;
    }
    .flex-3 { flex: 3; }
    .flex-2 { flex: 2; }
    .flex-1 { flex: 1; }
    .font-mono {
      font-family: var(--font-mono);
      font-size: 0.9rem;
    }
    .form-checkboxes {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      margin: 1.25rem 0;
    }
    .checkbox-label {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.95rem;
      cursor: pointer;
    }
    .form-actions {
      display: flex;
      justify-content: flex-end;
      gap: 1rem;
      margin-top: 1.5rem;
    }
    .assignments-grid {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }
    .assignment-card {
      padding: 1.75rem;
      border-left: 4px solid var(--primary);
    }
    .assignment-card.archived {
      border-left-color: var(--danger);
      opacity: 0.8;
    }
    .badge-row {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 0.5rem;
      align-items: center;
    }
    .max-marks-pill {
      font-size: 0.75rem;
      font-weight: 700;
      background: var(--bg-subtle);
      color: var(--text-main);
      padding: 0.2rem 0.5rem;
      border-radius: var(--radius-sm);
    }
    .assignment-title {
      font-size: 1.25rem;
      margin-bottom: 0.35rem;
    }
    .assignment-desc {
      color: var(--text-muted);
      font-size: 0.9rem;
      margin-bottom: 1rem;
    }
    .assignment-meta-row {
      display: flex;
      gap: 2rem;
      padding: 0.75rem 0;
      border-top: 1px solid var(--border-light);
      border-bottom: 1px solid var(--border-light);
      margin-bottom: 1rem;
      font-size: 0.85rem;
    }
    .meta-label {
      color: var(--text-muted);
      margin-right: 0.4rem;
    }
    .assignment-actions-bar {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }
    .portal-card {
      padding: 2rem;
    }
    .portal-header {
      margin-bottom: 1.5rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--border-light);
    }
    .back-sub-btn {
      margin-bottom: 0.75rem;
    }
    .grade-score {
      color: var(--success);
      font-weight: 800;
    }
    .badge-sm {
      font-size: 0.7rem;
      padding: 0.15rem 0.4rem;
      margin-left: 0.35rem;
    }
    .table-subtext {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .modal-backdrop {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0,0,0,0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }
    .grading-modal {
      max-width: 650px;
      width: 90%;
      padding: 2rem;
      background: #ffffff;
      max-height: 90vh;
      overflow-y: auto;
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1.25rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--border-light);
    }
    .close-modal-btn {
      background: none;
      border: none;
      font-size: 1.25rem;
      cursor: pointer;
      color: var(--text-muted);
    }
    .submission-content-preview {
      margin-bottom: 1.5rem;
    }
    .preview-label {
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--text-muted);
      margin-bottom: 0.4rem;
      display: block;
    }
    .submission-text-box {
      background: #f8fafc;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      padding: 1rem;
      font-family: var(--font-mono);
      font-size: 0.9rem;
      white-space: pre-wrap;
      max-height: 250px;
      overflow-y: auto;
    }
    .empty-block {
      text-align: center;
      padding: 3rem;
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
export class AssignmentManagerComponent implements OnInit {
  @Input() id!: string; // course id
  course: CourseDetail | null = null;
  sections: CourseSection[] = [];
  assignments: Assignment[] = [];
  isLoading = true;

  // Assignment form state
  showForm = false;
  editingAssignmentId: number | null = null;
  assignmentForm: FormGroup;
  isSaving = false;

  // Submissions portal state
  activeSubmissionsAssignment: Assignment | null = null;
  submissions: AssignmentSubmission[] = [];
  isLoadingSubmissions = false;

  // Grading modal state
  gradingSubmission: AssignmentSubmission | null = null;
  awardedGrade: number | null = null;
  gradingFeedback = '';
  isGrading = false;
  gradingError = '';

  feedbackMessage = '';
  isError = false;

  constructor(
    private courseService: CourseService,
    private instructorService: InstructorService,
    private fb: FormBuilder
  ) {
    this.assignmentForm = this.fb.group({
      title: ['', [Validators.required, Validators.minLength(3)]],
      description: [''],
      instructions: ['', [Validators.required, Validators.minLength(10)]],
      max_marks: [100, [Validators.required, Validators.min(1)]],
      due_date: [null],
      section_id: [null],
      allow_resubmission: [true],
      is_published: [false],
    });
  }

  ngOnInit(): void {
    if (this.id) {
      this.loadCourse(Number(this.id));
    }
  }

  loadCourse(courseId: number): void {
    this.isLoading = true;
    this.courseService.getCourse(courseId).subscribe({
      next: (data) => {
        this.course = data;
        this.loadSections(courseId);
        this.loadAssignments(courseId);
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  loadSections(courseId: number): void {
    this.instructorService.getCourseSections(courseId).subscribe({
      next: (secs) => {
        this.sections = secs;
      }
    });
  }

  loadAssignments(courseId: number): void {
    this.instructorService.getCourseAssignments(courseId).subscribe({
      next: (data) => {
        this.assignments = data;
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  openAddForm(): void {
    this.editingAssignmentId = null;
    this.assignmentForm.reset({
      title: '',
      description: '',
      instructions: '',
      max_marks: 100,
      due_date: null,
      section_id: null,
      allow_resubmission: true,
      is_published: false,
    });
    this.showForm = true;
  }

  editAssignment(a: Assignment): void {
    this.editingAssignmentId = a.id;
    let formattedDate = null;
    if (a.due_date) {
      formattedDate = new Date(a.due_date).toISOString().slice(0, 16);
    }
    this.assignmentForm.patchValue({
      title: a.title,
      description: a.description || '',
      instructions: a.instructions,
      max_marks: a.max_marks,
      due_date: formattedDate,
      section_id: a.section_id || null,
      allow_resubmission: a.allow_resubmission,
      is_published: a.is_published,
    });
    this.showForm = true;
  }

  closeForm(): void {
    this.showForm = false;
    this.editingAssignmentId = null;
    this.assignmentForm.reset();
  }

  onSaveAssignment(): void {
    if (this.assignmentForm.invalid || !this.course) return;

    this.isSaving = true;
    this.feedbackMessage = '';
    this.isError = false;

    const formVal = { ...this.assignmentForm.value };
    if (formVal.due_date) {
      formVal.due_date = new Date(formVal.due_date).toISOString();
    } else {
      formVal.due_date = null;
    }

    if (this.editingAssignmentId) {
      this.instructorService.updateAssignment(this.editingAssignmentId, formVal).subscribe({
        next: () => {
          this.isSaving = false;
          this.feedbackMessage = 'Assignment updated successfully!';
          this.closeForm();
          this.loadAssignments(this.course!.id);
        },
        error: (err) => {
          this.isSaving = false;
          this.isError = true;
          this.feedbackMessage = err.error?.detail || 'Failed to update assignment.';
        }
      });
    } else {
      this.instructorService.createAssignment(this.course.id, formVal).subscribe({
        next: () => {
          this.isSaving = false;
          this.feedbackMessage = 'Assignment created successfully!';
          this.closeForm();
          this.loadAssignments(this.course!.id);
        },
        error: (err) => {
          this.isSaving = false;
          this.isError = true;
          this.feedbackMessage = err.error?.detail || 'Failed to create assignment.';
        }
      });
    }
  }

  togglePublish(a: Assignment): void {
    this.instructorService.togglePublishAssignment(a.id).subscribe({
      next: (updated) => {
        a.is_published = updated.is_published;
        this.feedbackMessage = `Assignment ${updated.is_published ? 'published' : 'unpublished'}.`;
      }
    });
  }

  toggleClose(a: Assignment): void {
    this.instructorService.toggleCloseAssignment(a.id).subscribe({
      next: (updated) => {
        a.is_closed = updated.is_closed;
        this.feedbackMessage = `Assignment submissions ${updated.is_closed ? 'closed' : 'reopened'}.`;
      }
    });
  }

  deleteAssignment(a: Assignment): void {
    if (a.submission_count && a.submission_count > 0) {
      if (confirm(`This assignment contains ${a.submission_count} student submission(s). Do you want to safely archive it instead of deleting?`)) {
        this.instructorService.deleteAssignment(a.id, true).subscribe({
          next: (res) => {
            this.feedbackMessage = res.message;
            this.loadAssignments(this.course!.id);
          },
          error: (err) => {
            this.isError = true;
            this.feedbackMessage = err.error?.detail || 'Failed to archive assignment.';
          }
        });
      }
      return;
    }

    if (!confirm(`Are you sure you want to permanently delete "${a.title}"?`)) return;

    this.instructorService.deleteAssignment(a.id, false).subscribe({
      next: (res) => {
        this.feedbackMessage = res.message;
        this.loadAssignments(this.course!.id);
      },
      error: (err) => {
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to delete assignment.';
      }
    });
  }

  // Submissions Portal Operations
  openSubmissionsPortal(a: Assignment): void {
    this.activeSubmissionsAssignment = a;
    this.isLoadingSubmissions = true;
    this.instructorService.getAssignmentSubmissions(a.id).subscribe({
      next: (subs) => {
        this.submissions = subs;
        this.isLoadingSubmissions = false;
      },
      error: () => {
        this.isLoadingSubmissions = false;
      }
    });
  }

  closeSubmissionsPortal(): void {
    this.activeSubmissionsAssignment = null;
    this.submissions = [];
    if (this.course) {
      this.loadAssignments(this.course.id);
    }
  }

  openGradingModal(s: AssignmentSubmission): void {
    this.gradingSubmission = s;
    this.awardedGrade = s.grade !== null && s.grade !== undefined ? s.grade : null;
    this.gradingFeedback = s.feedback || '';
    this.gradingError = '';
  }

  closeGradingModal(): void {
    this.gradingSubmission = null;
    this.awardedGrade = null;
    this.gradingFeedback = '';
    this.gradingError = '';
  }

  saveGrade(): void {
    if (!this.gradingSubmission || this.awardedGrade === null) return;

    this.isGrading = true;
    this.gradingError = '';

    const payload: SubmissionGradePayload = {
      grade: Number(this.awardedGrade),
      feedback: this.gradingFeedback,
    };

    this.instructorService.gradeSubmission(this.gradingSubmission.id, payload).subscribe({
      next: (updatedSub) => {
        this.isGrading = false;
        // Update local submission list
        const idx = this.submissions.findIndex(item => item.id === updatedSub.id);
        if (idx !== -1) {
          this.submissions[idx] = updatedSub;
        }
        this.feedbackMessage = `Grade successfully recorded for ${updatedSub.student?.full_name}!`;
        this.closeGradingModal();
      },
      error: (err) => {
        this.isGrading = false;
        this.gradingError = err.error?.detail || 'Failed to submit grade.';
      }
    });
  }

  getStatusBadge(status: string): string {
    switch (status) {
      case 'graded': return 'badge-success';
      case 'resubmitted': return 'badge-warning';
      default: return 'badge-neutral';
    }
  }
}

