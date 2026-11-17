import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Assignment } from '../../core/models/assignment.model';
import {
  AssignmentEvaluation,
  AssignmentRubric,
  InstructorTeachingCourse,
  InstructorTeachingSubmission,
  RubricCriterion,
} from '../../core/models/instructor-ai.model';
import { InstructorService } from '../../core/services/instructor.service';

@Component({
  selector: 'app-ai-assignment-evaluator',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <main class="teaching-page">
      <div class="container">
        <a routerLink="/instructor/dashboard" class="back-link">← Instructor Dashboard</a>
        <header class="page-header">
          <div>
            <span class="eyebrow">AI Teaching Tools</span>
            <h1>AI Assignment Evaluator</h1>
            <p>Review rubric-based AI suggestions. Marks remain private until you approve them.</p>
          </div>
        </header>

        @if (message) {
          <div class="alert" [class.error]="isError">{{ message }}</div>
        }

        <section class="card filters">
          <label>Course
            <select [(ngModel)]="courseId" (ngModelChange)="selectCourse($event)">
              <option [ngValue]="null">Select a course</option>
              @for (course of courses; track course.id) {
                <option [ngValue]="course.id">{{ course.title }}</option>
              }
            </select>
          </label>
          <label>Assignment
            <select [(ngModel)]="assignmentId" (ngModelChange)="selectAssignment($event)" [disabled]="!courseId">
              <option [ngValue]="null">Select an assignment</option>
              @for (assignment of assignments; track assignment.id) {
                <option [ngValue]="assignment.id">{{ assignment.title }} ({{ assignment.max_marks }} marks)</option>
              }
            </select>
          </label>
          <label>Student / email
            <input [(ngModel)]="studentFilter" placeholder="Search submissions" />
          </label>
          <label>Status
            <select [(ngModel)]="statusFilter">
              <option value="">All statuses</option>
              <option value="pending_evaluation">Pending evaluation</option>
              <option value="pending_review">AI review ready</option>
              <option value="graded">Evaluated</option>
              <option value="approved">Approved</option>
            </select>
          </label>
        </section>

        @if (assignmentId && assignment) {
          <section class="card rubric">
            <div class="section-title">
              <div>
                <h2>Grading rubric</h2>
                <p>Criteria must total {{ assignment.max_marks }} marks.</p>
              </div>
              <strong [class.invalid]="rubricTotal !== assignment.max_marks">{{ rubricTotal }} / {{ assignment.max_marks }}</strong>
            </div>
            <label>Expected answer / instructor guidance
              <textarea rows="4" [(ngModel)]="rubric.expected_answer" placeholder="Describe the expected solution and important concepts"></textarea>
            </label>
            @for (criterion of rubric.criteria; track $index; let i = $index) {
              <div class="criterion-grid">
                <label>Criterion<input [(ngModel)]="criterion.criterion_name" /></label>
                <label>Max marks<input type="number" min="0.1" step="0.1" [(ngModel)]="criterion.maximum_marks" /></label>
                <label>Description<input [(ngModel)]="criterion.description" /></label>
                <label>Guidelines<input [(ngModel)]="criterion.guidelines" /></label>
                <button class="btn btn-small danger" type="button" (click)="removeRubricCriterion(i)" [disabled]="rubric.criteria.length <= 1">Remove</button>
              </div>
            }
            <div class="actions">
              <button class="btn outline" type="button" (click)="addRubricCriterion()">Add criterion</button>
              <button class="btn primary" type="button" (click)="saveRubric()" [disabled]="busy || rubricTotal !== assignment.max_marks">Save rubric</button>
            </div>
          </section>
        }

        <section class="card">
          <div class="section-title">
            <div><h2>Student submissions</h2><p>AI suggestions are never published automatically.</p></div>
            <span class="count">{{ filteredSubmissions.length }} submissions</span>
          </div>
          @if (!courseId) {
            <p class="empty">Select a course to load its assignments and submissions.</p>
          } @else if (filteredSubmissions.length === 0) {
            <p class="empty">No submissions match the selected filters.</p>
          } @else {
            <div class="table-wrap">
              <table>
                <thead><tr><th>Student</th><th>Assignment</th><th>Submitted</th><th>Status</th><th>Marks</th><th></th></tr></thead>
                <tbody>
                  @for (submission of filteredSubmissions; track submission.id) {
                    <tr [class.selected]="selectedSubmission?.id === submission.id">
                      <td><strong>{{ submission.student_name }}</strong><small>{{ submission.student_email }}</small></td>
                      <td>{{ submission.assignment_title }}</td>
                      <td>{{ submission.submitted_at | date:'short' }}</td>
                      <td><span class="badge" [class.approved]="submission.status === 'approved'">{{ statusLabel(submission) }}</span></td>
                      <td>{{ submission.grade == null ? '—' : submission.grade + ' / ' + submission.max_marks }}</td>
                      <td><button class="btn outline" type="button" (click)="openSubmission(submission)">Review</button></td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          }
        </section>

        @if (selectedSubmission) {
          <section class="review-grid">
            <article class="card submission">
              <h2>{{ selectedSubmission.student_name }}’s work</h2>
              <p><strong>{{ selectedSubmission.assignment_title }}</strong> · submitted {{ selectedSubmission.submitted_at | date:'medium' }}</p>
              <div class="submission-text">{{ selectedSubmission.submission_text || 'No text response.' }}</div>
              @for (attachment of submissionAttachments; track attachment.storage_key; let i = $index) {
                <button class="attachment" type="button" (click)="downloadAttachment(i)" [disabled]="busy">
                  {{ attachment.name }} · Download
                </button>
              }
              <div class="actions">
                <button class="btn primary" type="button" (click)="evaluate()" [disabled]="busy || !rubric.criteria.length">
                  {{ busy ? 'Evaluating…' : 'Evaluate with AI' }}
                </button>
                @if (evaluation) {
                  <button class="btn outline" type="button" (click)="reevaluate()" [disabled]="busy">Request re-evaluation</button>
                }
              </div>
            </article>

            @if (evaluation) {
              <article class="card result">
                <div class="section-title">
                  <div><h2>AI suggestion</h2><span class="badge" [class.approved]="evaluation.evaluation_status === 'approved'">{{ evaluation.evaluation_status | titlecase }}</span></div>
                  <strong class="score">{{ evaluation.ai_suggested_marks }} / {{ selectedSubmission.max_marks }}</strong>
                </div>
                <p class="private-note">Private to instructors until approved.</p>
                @if (evaluationHistory.length > 1) {
                  <div class="history-list">
                    <strong>Evaluation history</strong>
                    @for (entry of evaluationHistory; track entry.id) {
                      <p>{{ entry.created_at | date:'short' }} · {{ entry.evaluation_status | titlecase }} · AI suggestion {{ entry.ai_suggested_marks }} / {{ selectedSubmission.max_marks }}</p>
                    }
                  </div>
                }
                @for (criterion of evaluation.criteria; track criterion.id) {
                  <div class="evaluation-criterion">
                    <div class="criterion-heading">
                      <strong>{{ criterion.criterion_name }}</strong>
                      <span>AI {{ criterion.suggested_marks }} / {{ criterion.maximum_marks }}</span>
                    </div>
                    <p>{{ criterion.feedback }}</p>
                    @if (evaluation.evaluation_status !== 'approved') {
                      <div class="review-inputs">
                        <label>Final marks
                          <input type="number" min="0" [max]="criterion.maximum_marks" step="0.1" [(ngModel)]="criterion.final_marks" (ngModelChange)="syncFinalMarks()" />
                        </label>
                        <label>Criterion feedback<input [(ngModel)]="criterion.feedback" /></label>
                      </div>
                    } @else {
                      <p><strong>Approved:</strong> {{ criterion.final_marks }} / {{ criterion.maximum_marks }}</p>
                    }
                  </div>
                }
                <label>AI feedback
                  <textarea rows="5" [value]="evaluation.ai_feedback" readonly></textarea>
                </label>
                @if (evaluation.evaluation_status !== 'approved') {
                  <label>Instructor feedback
                    <textarea rows="4" [(ngModel)]="evaluation.instructor_feedback" placeholder="Review and edit feedback before approval"></textarea>
                  </label>
                  <div class="actions">
                    <strong>Final: {{ evaluation.final_marks ?? 0 }} / {{ selectedSubmission.max_marks }}</strong>
                    <button class="btn outline" type="button" (click)="saveReview()" [disabled]="busy">Save review</button>
                    <button class="btn primary" type="button" (click)="approve()" [disabled]="busy || evaluation.final_marks == null">Approve & publish to student</button>
                  </div>
                } @else {
                  <p class="approved-note">Approved grade is visible in the student’s assignment results.</p>
                }
              </article>
            }
          </section>
        }
      </div>
    </main>
  `,
  styles: [`
    .teaching-page{min-height:100vh;padding:2rem 0 4rem;background:var(--bg-app,#faf7fb);color:var(--text-primary,#2c2430)}
    .back-link{display:inline-block;margin-bottom:1.25rem;color:var(--primary,#d9468f);font-weight:700}
    .page-header{margin-bottom:1.5rem}.eyebrow{color:#c02678;font-weight:800;text-transform:uppercase;letter-spacing:.08em;font-size:.75rem}
    h1{margin:.35rem 0;font-size:clamp(1.7rem,4vw,2.4rem)}h2{font-size:1.15rem;margin:0 0 .35rem}
    p{color:var(--text-muted,#756b79);line-height:1.55}.card{background:#fff;border:1px solid #eee4ed;border-radius:16px;padding:1.25rem;box-shadow:0 8px 26px #5b26420a;margin-bottom:1.2rem}
    .filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem}
    label{display:grid;gap:.4rem;font-size:.82rem;font-weight:700;color:#574b5b}
    input,select,textarea{width:100%;padding:.7rem .75rem;border:1px solid #ded5df;border-radius:9px;background:#fff;color:#2c2430;font:inherit}
    textarea{resize:vertical;line-height:1.5}small{display:block;color:#807582;margin-top:.2rem}
    .section-title{display:flex;align-items:center;justify-content:space-between;gap:1rem;margin-bottom:1rem}.section-title p{margin:.1rem 0}
    .criterion-grid{display:grid;grid-template-columns:1.2fr .55fr 1.4fr 1.3fr auto;gap:.65rem;align-items:end;padding:.8rem 0;border-top:1px solid #f1e9f1}
    .invalid{color:#c02626}.btn{border:0;border-radius:9px;padding:.65rem .9rem;font-weight:750;cursor:pointer}.btn:disabled{opacity:.55;cursor:not-allowed}
    .primary{background:#d9468f;color:#fff}.outline{background:#fff;border:1px solid #d9c8d7;color:#61425d}.danger{background:#fff0f2;color:#b42340}
    .actions{display:flex;align-items:center;justify-content:flex-end;gap:.6rem;flex-wrap:wrap;margin-top:1rem}.count,.badge{border-radius:100px;padding:.35rem .7rem;background:#f6edf5;color:#6b4f68;font-size:.78rem;font-weight:750}
    .badge.approved{background:#e8f7ed;color:#19763b}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:720px}th,td{text-align:left;padding:.8rem;border-bottom:1px solid #f0e9f0}th{font-size:.75rem;color:#716675;text-transform:uppercase}td small{font-size:.75rem}
    tr.selected{background:#fff8fc}.empty{padding:1rem;text-align:center}.alert{padding:.8rem 1rem;margin-bottom:1rem;background:#effaf2;color:#17693a;border-radius:10px}.alert.error{background:#fff0f2;color:#a21c3b}
    .review-grid{display:grid;grid-template-columns:minmax(260px,.85fr) minmax(360px,1.3fr);gap:1rem}.submission-text{white-space:pre-wrap;overflow-wrap:anywhere;max-height:420px;overflow:auto;background:#fbf8fb;border:1px solid #eee4ed;padding:1rem;border-radius:10px}
    .attachment{padding:.55rem 0;color:#6b4f68}.score{font-size:1.15rem;color:#bd2777}.private-note{font-size:.82rem;background:#fff7e6;padding:.55rem;border-radius:8px;color:#8a5b08}
    .evaluation-criterion{padding:.85rem 0;border-top:1px solid #f0e9f0}.criterion-heading,.review-inputs{display:flex;justify-content:space-between;gap:.75rem}.evaluation-criterion p{margin:.5rem 0}.review-inputs label{flex:1}
    .approved-note{padding:.7rem;background:#effaf2;border-radius:9px;color:#17693a}
    .history-list{padding:.7rem .85rem;margin:.75rem 0;background:#fbf8fb;border-radius:9px}.history-list p{margin:.35rem 0;font-size:.8rem}
    @media(max-width:850px){.review-grid{grid-template-columns:1fr}.criterion-grid{grid-template-columns:1fr 1fr}.criterion-grid .danger{justify-self:start}}
    @media(max-width:520px){.card{padding:1rem}.criterion-grid{grid-template-columns:1fr}.review-inputs{flex-direction:column}.section-title{align-items:flex-start}}
  `],
})
export class AIAssignmentEvaluatorComponent implements OnInit {
  courses: InstructorTeachingCourse[] = [];
  assignments: Assignment[] = [];
  submissions: InstructorTeachingSubmission[] = [];
  courseId: number | null = null;
  assignmentId: number | null = null;
  assignment: Assignment | null = null;
  selectedSubmission: InstructorTeachingSubmission | null = null;
  rubric: AssignmentRubric = { assignment_id: 0, assignment_title: '', max_marks: 0, expected_answer: '', criteria: [] };
  evaluation: AssignmentEvaluation | null = null;
  evaluationHistory: AssignmentEvaluation[] = [];
  studentFilter = '';
  statusFilter = '';
  busy = false;
  message = '';
  isError = false;

  constructor(private instructorService: InstructorService) {}

  ngOnInit(): void {
    this.instructorService.getTeachingCourses().subscribe({
      next: (courses) => this.courses = courses,
      error: (error: HttpErrorResponse) => this.showError(error, 'Could not load assigned courses.'),
    });
  }

  get rubricTotal(): number {
    return Math.round(this.rubric.criteria.reduce((total, item) => total + Number(item.maximum_marks || 0), 0) * 100) / 100;
  }

  get filteredSubmissions(): InstructorTeachingSubmission[] {
    const search = this.studentFilter.trim().toLowerCase();
    return this.submissions.filter((item) => {
      const matchesSearch = !search || `${item.student_name} ${item.student_email}`.toLowerCase().includes(search);
      const matchesStatus = !this.statusFilter || item.status === this.statusFilter || item.evaluation_status === this.statusFilter;
      return matchesSearch && matchesStatus;
    });
  }

  get submissionAttachments(): Array<{ name: string; storage_key: string }> {
    if (!this.selectedSubmission?.attachments_json) return [];
    try {
      const value = JSON.parse(this.selectedSubmission.attachments_json);
      return Array.isArray(value) ? value.filter((item) => item?.name && item?.storage_key) : [];
    } catch {
      return [];
    }
  }

  downloadAttachment(index: number): void {
    if (!this.selectedSubmission) return;
    this.busy = true;
    this.instructorService.downloadSubmissionAttachment(this.selectedSubmission.id, index).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = this.submissionAttachments[index]?.name || 'submission-document';
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        this.busy = false;
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not download this submission document.');
      },
    });
  }

  selectCourse(courseId: number | null): void {
    this.courseId = courseId;
    this.assignmentId = null;
    this.assignment = null;
    this.selectedSubmission = null;
    this.evaluation = null;
    this.evaluationHistory = [];
    this.assignments = [];
    this.submissions = [];
    if (!courseId) return;
    this.instructorService.getCourseAssignments(courseId).subscribe({
      next: (items) => this.assignments = items,
      error: (error: HttpErrorResponse) => this.showError(error, 'Could not load course assignments.'),
    });
    this.loadSubmissions(courseId);
  }

  selectAssignment(assignmentId: number | null): void {
    this.assignmentId = assignmentId;
    this.assignment = this.assignments.find((item) => item.id === assignmentId) ?? null;
    this.selectedSubmission = null;
    this.evaluation = null;
    this.evaluationHistory = [];
    if (!assignmentId || !this.assignment) return;
    this.instructorService.getAssignmentRubric(assignmentId).subscribe({
      next: (saved) => {
        this.rubric = saved.criteria.length ? saved : {
          ...saved,
          expected_answer: '',
          criteria: [{
            criterion_name: 'Accuracy and completeness',
            maximum_marks: saved.max_marks,
            description: 'Accuracy, completeness, and relevance of the response.',
            guidelines: '',
          }],
        };
      },
      error: (error: HttpErrorResponse) => this.showError(error, 'Could not load assignment rubric.'),
    });
  }

  addRubricCriterion(): void {
    this.rubric.criteria = [...this.rubric.criteria, {
      criterion_name: '',
      maximum_marks: 1,
      description: '',
      guidelines: '',
    }];
  }

  removeRubricCriterion(index: number): void {
    this.rubric.criteria = this.rubric.criteria.filter((_item, current) => current !== index);
  }

  saveRubric(): void {
    if (!this.assignmentId || !this.assignment) return;
    this.busy = true;
    this.instructorService.saveAssignmentRubric(this.assignmentId, {
      expected_answer: this.rubric.expected_answer,
      criteria: this.rubric.criteria,
    }).subscribe({
      next: (rubric) => {
        this.rubric = rubric;
        this.busy = false;
        this.showMessage('Rubric saved. The criteria total matches the assignment marks.');
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not save this rubric.');
      },
    });
  }

  openSubmission(submission: InstructorTeachingSubmission): void {
    this.selectedSubmission = submission;
    this.evaluation = null;
    this.evaluationHistory = [];
    this.instructorService.getSubmissionEvaluations(submission.id).subscribe({
      next: (history) => {
        this.evaluationHistory = history;
        this.evaluation = history[0] ?? null;
      },
      error: (error: HttpErrorResponse) => this.showError(error, 'Could not load evaluation history.'),
    });
  }

  evaluate(): void {
    if (!this.selectedSubmission || !this.assignmentId || this.rubricTotal !== this.assignment?.max_marks) {
      this.showMessage('Save a rubric whose criteria match the assignment maximum marks first.', true);
      return;
    }
    this.busy = true;
    this.instructorService.saveAssignmentRubric(this.assignmentId, {
      expected_answer: this.rubric.expected_answer,
      criteria: this.rubric.criteria,
    }).subscribe({
      next: (rubric) => {
        this.rubric = rubric;
        this.instructorService.evaluateAssignmentSubmission(this.selectedSubmission!.id).subscribe({
          next: (evaluation) => {
            this.evaluation = evaluation;
            this.updateEvaluationHistory(evaluation);
            this.syncFinalMarks();
            this.busy = false;
            this.showMessage('AI suggestion generated for instructor review. It has not been published.');
            this.loadSubmissions(this.courseId!);
          },
          error: (error: HttpErrorResponse) => {
            this.busy = false;
            this.showError(error, 'AI evaluation failed.');
          },
        });
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not save the rubric.');
      },
    });
  }

  syncFinalMarks(): void {
    if (this.evaluation) {
      this.evaluation.final_marks = Math.round(
        this.evaluation.criteria.reduce((total, item) => total + Number(item.final_marks ?? item.suggested_marks), 0) * 100
      ) / 100;
    }
  }

  saveReview(): void {
    if (!this.evaluation || !this.selectedSubmission) return;
    this.syncFinalMarks();
    this.busy = true;
    this.instructorService.saveEvaluationReview(this.evaluation.id, {
      final_marks: this.evaluation.final_marks ?? this.evaluation.ai_suggested_marks,
      instructor_feedback: this.evaluation.instructor_feedback || this.evaluation.ai_feedback,
      criteria: this.evaluation.criteria.map((item) => ({
        id: item.id,
        criterion_name: item.criterion_name,
        maximum_marks: item.maximum_marks,
        final_marks: item.final_marks ?? item.suggested_marks,
        feedback: item.feedback,
      })),
    }).subscribe({
      next: (saved) => {
        this.evaluation = saved;
        this.updateEvaluationHistory(saved);
        this.busy = false;
        this.showMessage('Instructor review saved. Approve when ready to publish the grade.');
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not save instructor review.');
      },
    });
  }

  approve(): void {
    if (!this.evaluation || this.evaluation.final_marks == null) {
      this.showMessage('Save your reviewed marks and feedback before approval.', true);
      return;
    }
    if (!window.confirm('Approve this grade and publish the instructor feedback to the student?')) return;
    this.busy = true;
    this.instructorService.approveEvaluation(this.evaluation.id).subscribe({
      next: (saved) => {
        this.evaluation = saved;
        this.updateEvaluationHistory(saved);
        this.busy = false;
        this.showMessage('Evaluation approved and published to the student.');
        if (this.courseId) this.loadSubmissions(this.courseId);
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not approve this evaluation.');
      },
    });
  }

  reevaluate(): void {
    if (!this.evaluation) return;
    this.busy = true;
    this.instructorService.reevaluateSubmission(this.evaluation.id).subscribe({
      next: (evaluation) => {
        this.evaluation = evaluation;
        this.updateEvaluationHistory(evaluation);
        this.syncFinalMarks();
        this.busy = false;
        this.showMessage('A new AI suggestion is ready for instructor review.');
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not request re-evaluation.');
      },
    });
  }

  statusLabel(submission: InstructorTeachingSubmission): string {
    if (submission.evaluation_status === 'approved' || submission.status === 'approved') return 'Approved';
    if (submission.evaluation_status === 'pending_review') return 'Pending review';
    return submission.status === 'graded' ? 'Evaluated' : 'Pending evaluation';
  }

  private updateEvaluationHistory(evaluation: AssignmentEvaluation): void {
    this.evaluationHistory = [
      evaluation,
      ...this.evaluationHistory.filter((item) => item.id !== evaluation.id),
    ];
  }

  private loadSubmissions(courseId: number): void {
    this.instructorService.getTeachingSubmissions({ course_id: courseId }).subscribe({
      next: (items) => this.submissions = items,
      error: (error: HttpErrorResponse) => this.showError(error, 'Could not load student submissions.'),
    });
  }

  private showError(error: HttpErrorResponse, fallback: string): void {
    this.isError = true;
    const detail = error.error?.detail;
    this.message = typeof detail === 'string' ? detail : fallback;
  }

  private showMessage(message: string, error = false): void {
    this.message = message;
    this.isError = error;
  }
}
