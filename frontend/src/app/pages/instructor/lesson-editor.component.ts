import { Component, OnInit, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { CourseService } from '../../core/services/course.service';
import { InstructorService } from '../../core/services/instructor.service';
import { CourseDetail, CourseSection, LessonSummary } from '../../core/models/course.model';
import { LessonService } from '../../core/services/lesson.service';

@Component({
  selector: 'app-lesson-editor',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink],
  template: `
    <div class="lesson-mgr-page">
      <div class="container">
        <div class="page-header">
          <div>
            <a routerLink="/instructor/dashboard" class="back-link">← Back to Instructor Hub</a>
            <h1>Curriculum & Lessons Manager</h1>
            <p class="subtitle" *ngIf="course">
              Course: <strong>{{ course.title }}</strong>
            </p>
          </div>
          <div class="header-actions">
            <button (click)="openAddSectionForm()" class="btn btn-outline" *ngIf="!showSectionForm">
              + Add Section / Module
            </button>
            <button (click)="openAddForm()" class="btn btn-primary" *ngIf="!showForm">
              + Add New Lesson
            </button>
          </div>
        </div>

        @if (feedbackMessage) {
          <div class="alert" [ngClass]="isError ? 'alert-danger' : 'alert-success'">
            {{ feedbackMessage }}
          </div>
        }

        <!-- Add / Edit Section Form -->
        @if (showSectionForm) {
          <div class="card form-card section-card">
            <div class="form-header">
              <h3>{{ editingSectionId ? 'Edit Section / Module' : 'Create New Section / Module' }}</h3>
              <button (click)="closeSectionForm()" class="btn btn-sm btn-secondary">Close</button>
            </div>

            <form [formGroup]="sectionForm" (ngSubmit)="onSaveSection()">
              <div class="form-row">
                <div class="form-group flex-3">
                  <label class="form-label" for="sec_title">Section Title</label>
                  <input
                    id="sec_title"
                    type="text"
                    class="form-input"
                    formControlName="title"
                    placeholder="e.g. Module 1: Foundational Architecture"
                  />
                </div>

                <div class="form-group flex-1">
                  <label class="form-label" for="sec_order">Order Index</label>
                  <input
                    id="sec_order"
                    type="number"
                    min="1"
                    class="form-input"
                    formControlName="order_index"
                  />
                </div>
              </div>

              <div class="form-group">
                <label class="form-label" for="sec_desc">Description (Optional)</label>
                <textarea
                  id="sec_desc"
                  rows="3"
                  class="form-textarea"
                  formControlName="description"
                  placeholder="Summary of topics covered in this module..."
                ></textarea>
              </div>

              <div class="form-actions">
                <button type="button" (click)="closeSectionForm()" class="btn btn-secondary">Cancel</button>
                <button type="submit" class="btn btn-primary" [disabled]="sectionForm.invalid || isSavingSection">
                  @if (isSavingSection) {
                    <span>Saving...</span>
                  } @else {
                    <span>{{ editingSectionId ? 'Update Section' : 'Create Section' }}</span>
                  }
                </button>
              </div>
            </form>
          </div>
        }

        <!-- Add / Edit Lesson Inline Form -->
        @if (showForm) {
          <div class="card form-card">
            <div class="form-header">
              <h3>{{ editingLessonId ? 'Edit Lesson' : 'Create New Lesson' }}</h3>
              <button (click)="closeForm()" class="btn btn-sm btn-secondary">Close Form</button>
            </div>

            <form [formGroup]="lessonForm" (ngSubmit)="onSaveLesson()">
              <div class="form-row">
                <div class="form-group flex-3">
                  <label class="form-label" for="title">Lesson Title</label>
                  <input
                    id="title"
                    type="text"
                    class="form-input"
                    formControlName="title"
                    placeholder="e.g. Asynchronous Routing & Concurrency Models"
                  />
                </div>

                <div class="form-group flex-1">
                  <label class="form-label" for="order_index">Order Index</label>
                  <input
                    id="order_index"
                    type="number"
                    min="1"
                    class="form-input"
                    formControlName="order_index"
                  />
                </div>
              </div>

              <div class="form-group">
                <label class="form-label" for="section_id">Section / Module (Optional)</label>
                <select id="section_id" class="form-input" formControlName="section_id">
                  <option [ngValue]="null">General / No Section</option>
                  @for (sec of sections; track sec.id) {
                    <option [ngValue]="sec.id">{{ sec.order_index }}. {{ sec.title }}</option>
                  }
                </select>
              </div>

              <div class="form-group">
                <label class="form-label" for="content">Lesson Content (Markdown / Code)</label>
                <textarea
                  id="content"
                  rows="8"
                  class="form-textarea font-mono"
                  formControlName="content"
                  placeholder="### Overview&#10;&#10;Enter the lesson instructions, markdown headings, bullet points, and code blocks..."
                ></textarea>
              </div>

              <div class="form-actions">
                <button type="button" (click)="closeForm()" class="btn btn-secondary">Cancel</button>
                <button type="submit" class="btn btn-primary" [disabled]="lessonForm.invalid || isSaving">
                  @if (isSaving) {
                    <span>Saving...</span>
                  } @else {
                    <span>{{ editingLessonId ? 'Update Lesson' : 'Add Lesson' }}</span>
                  }
                </button>
              </div>
            </form>
          </div>
        }

        <!-- Section Safe Delete Dialog -->
        @if (sectionToDelete) {
          <div class="modal-backdrop">
            <div class="card modal-card">
              <h3>Delete Section: {{ sectionToDelete.title }}</h3>
              @if (sectionToDelete.lesson_count > 0) {
                <p class="warning-text">
                  This section currently contains <strong>{{ sectionToDelete.lesson_count }}</strong> lesson(s).
                  EduVerse safeguards curriculum integrity by preventing orphaned lessons.
                </p>
                <div class="form-group">
                  <label class="form-label">Reassign lessons to:</label>
                  <select class="form-input" [(ngModel)]="reassignTargetId" [ngModelOptions]="{standalone: true}">
                    @for (sec of getOtherSections(sectionToDelete.id); track sec.id) {
                      <option [ngValue]="sec.id">{{ sec.order_index }}. {{ sec.title }}</option>
                    }
                  </select>
                </div>
              } @else {
                <p>Are you sure you want to delete this empty section?</p>
              }

              <div class="form-actions">
                <button (click)="sectionToDelete = null" class="btn btn-secondary">Cancel</button>
                <button (click)="confirmDeleteSection()" class="btn btn-danger" [disabled]="sectionToDelete.lesson_count > 0 && !reassignTargetId">
                  Confirm Deletion
                </button>
              </div>
            </div>
          </div>
        }

        <!-- Sections & Lessons List -->
        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading curriculum...</span>
          </div>
        } @else if (!course || (course.lessons.length === 0 && sections.length === 0)) {
          <div class="empty-block card">
            <h3>No curriculum content in this course yet</h3>
            <p>Author your first module section or lesson to provide structured content for students.</p>
            <div class="empty-actions">
              <button (click)="openAddSectionForm()" class="btn btn-outline">+ Create First Section</button>
              <button (click)="openAddForm()" class="btn btn-primary">+ Create First Lesson</button>
            </div>
          </div>
        } @else {
          <!-- Display Sections with Nested Lessons -->
          <div class="sections-container">
            @for (sec of sections; track sec.id) {
              <div class="section-group card">
                <div class="section-header-bar">
                  <div class="section-meta">
                    <span class="order-badge section-badge">Sec {{ sec.order_index }}</span>
                    <div>
                      <h3 class="section-heading">{{ sec.title }}</h3>
                      @if (sec.description) {
                        <p class="section-subtext">{{ sec.description }}</p>
                      }
                    </div>
                  </div>
                  <div class="section-actions">
                    <button (click)="editSection(sec)" class="btn btn-sm btn-secondary">Edit Section</button>
                    <button (click)="promptDeleteSection(sec)" class="btn btn-sm btn-danger">Delete Section</button>
                  </div>
                </div>

                @if (getLessonsForSection(sec.id).length === 0) {
                  <div class="empty-section-notice">
                    <span>No lessons assigned to this section yet.</span>
                  </div>
                } @else {
                  <table class="nested-table">
                    <thead>
                      <tr>
                        <th style="width: 70px;">Order</th>
                        <th>Lesson Title</th>
                        <th style="width: 220px;">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      @for (l of getLessonsForSection(sec.id); track l.id) {
                        <tr>
                          <td><span class="order-badge">{{ l.order_index }}</span></td>
                          <td><strong>{{ l.title }}</strong></td>
                          <td>
                            <div class="action-buttons">
                              <button (click)="editLesson(l)" class="btn btn-sm btn-secondary">Edit</button>
                              <a [routerLink]="['/courses', course.id, 'learn', l.id]" class="btn btn-sm btn-outline">Preview</a>
                              <button (click)="deleteLesson(l.id)" class="btn btn-sm btn-danger">Delete</button>
                            </div>
                          </td>
                        </tr>
                      }
                    </tbody>
                  </table>
                }
              </div>
            }

            <!-- Uncategorized Lessons (section_id == null) -->
            @if (getUncategorizedLessons().length > 0) {
              <div class="section-group card uncategorized-group">
                <div class="section-header-bar">
                  <div class="section-meta">
                    <span class="order-badge">📌</span>
                    <div>
                      <h3 class="section-heading">General / Ungrouped Lessons</h3>
                      <p class="section-subtext">Lessons not assigned to a specific module</p>
                    </div>
                  </div>
                </div>

                <table class="nested-table">
                  <thead>
                    <tr>
                      <th style="width: 70px;">Order</th>
                      <th>Lesson Title</th>
                      <th style="width: 220px;">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (l of getUncategorizedLessons(); track l.id) {
                      <tr>
                        <td><span class="order-badge">{{ l.order_index }}</span></td>
                        <td><strong>{{ l.title }}</strong></td>
                        <td>
                          <div class="action-buttons">
                            <button (click)="editLesson(l)" class="btn btn-sm btn-secondary">Edit</button>
                            <a [routerLink]="['/courses', course.id, 'learn', l.id]" class="btn btn-sm btn-outline">Preview</a>
                            <button (click)="deleteLesson(l.id)" class="btn btn-sm btn-danger">Delete</button>
                          </div>
                        </td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            }
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .lesson-mgr-page {
      padding: 2.5rem 0 4rem 0;
      background-color: var(--bg-app);
    }
    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      flex-wrap: wrap;
      gap: 1rem;
    }
    .header-actions {
      display: flex;
      gap: 0.75rem;
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
    .section-card {
      border-color: #3b82f6;
      background-color: #f8fafc;
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
    .flex-1 { flex: 1; }
    .font-mono {
      font-family: var(--font-mono);
      font-size: 0.9rem;
    }
    .form-actions {
      display: flex;
      justify-content: flex-end;
      gap: 1rem;
      margin-top: 1.5rem;
    }
    .order-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 28px;
      height: 28px;
      padding: 0 6px;
      border-radius: var(--radius-sm);
      background-color: var(--bg-subtle);
      font-weight: 700;
      color: var(--text-main);
    }
    .section-badge {
      background-color: #e0e7ff;
      color: #3730a3;
    }
    .action-buttons {
      display: flex;
      gap: 0.5rem;
    }
    .empty-block {
      text-align: center;
      padding: 3rem;
    }
    .empty-block h3 {
      font-size: 1.25rem;
      margin-bottom: 0.5rem;
    }
    .empty-block p {
      color: var(--text-muted);
      margin-bottom: 1.5rem;
    }
    .empty-actions {
      display: flex;
      justify-content: center;
      gap: 1rem;
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

    /* Sections Container */
    .sections-container {
      display: flex;
      flex-direction: column;
      gap: 1.75rem;
    }
    .section-group {
      padding: 1.5rem;
      border-left: 4px solid var(--primary);
    }
    .uncategorized-group {
      border-left-color: var(--border-color);
    }
    .section-header-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 1rem;
      margin-bottom: 1rem;
      border-bottom: 1px solid var(--border-light);
      flex-wrap: wrap;
      gap: 1rem;
    }
    .section-meta {
      display: flex;
      align-items: center;
      gap: 0.85rem;
    }
    .section-heading {
      font-size: 1.2rem;
      margin-bottom: 0.2rem;
    }
    .section-subtext {
      color: var(--text-muted);
      font-size: 0.85rem;
      margin: 0;
    }
    .section-actions {
      display: flex;
      gap: 0.5rem;
    }
    .empty-section-notice {
      padding: 1.5rem;
      text-align: center;
      color: var(--text-muted);
      font-style: italic;
    }
    .nested-table {
      width: 100%;
      border-collapse: collapse;
    }
    .nested-table th, .nested-table td {
      padding: 0.75rem 1rem;
      text-align: left;
      border-bottom: 1px solid var(--border-light);
    }
    .nested-table th {
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }

    /* Modal */
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
    .modal-card {
      max-width: 500px;
      width: 90%;
      padding: 2rem;
      background: #fff;
    }
    .warning-text {
      color: #b91c1c;
      font-size: 0.95rem;
      line-height: 1.5;
      margin: 1rem 0;
    }
  `]
})
export class LessonEditorComponent implements OnInit {
  @Input() id!: string; // course id
  course: CourseDetail | null = null;
  sections: CourseSection[] = [];
  isLoading = true;

  // Lesson form state
  showForm = false;
  editingLessonId: number | null = null;
  lessonForm: FormGroup;
  isSaving = false;

  // Section form state
  showSectionForm = false;
  editingSectionId: number | null = null;
  sectionForm: FormGroup;
  isSavingSection = false;

  // Section deletion safety state
  sectionToDelete: CourseSection | null = null;
  reassignTargetId: number | null = null;

  feedbackMessage = '';
  isError = false;

  constructor(
    private courseService: CourseService,
    private instructorService: InstructorService,
    private lessonService: LessonService,
    private fb: FormBuilder
  ) {
    this.lessonForm = this.fb.group({
      title: ['', [Validators.required, Validators.minLength(3)]],
      content: ['', [Validators.required, Validators.minLength(10)]],
      order_index: [1, [Validators.required, Validators.min(1)]],
      section_id: [null]
    });

    this.sectionForm = this.fb.group({
      title: ['', [Validators.required, Validators.minLength(1)]],
      description: [''],
      order_index: [1, [Validators.required, Validators.min(1)]]
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
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  // Section Handling
  openAddSectionForm(): void {
    this.editingSectionId = null;
    const nextOrder = this.sections.length > 0 ? Math.max(...this.sections.map(s => s.order_index)) + 1 : 1;
    this.sectionForm.reset({
      title: '',
      description: '',
      order_index: nextOrder
    });
    this.showSectionForm = true;
  }

  editSection(sec: CourseSection): void {
    this.editingSectionId = sec.id;
    this.sectionForm.patchValue({
      title: sec.title,
      description: sec.description || '',
      order_index: sec.order_index
    });
    this.showSectionForm = true;
  }

  closeSectionForm(): void {
    this.showSectionForm = false;
    this.editingSectionId = null;
    this.sectionForm.reset();
  }

  onSaveSection(): void {
    if (this.sectionForm.invalid || !this.course) return;

    this.isSavingSection = true;
    this.feedbackMessage = '';
    this.isError = false;

    if (this.editingSectionId) {
      this.instructorService.updateSection(this.editingSectionId, this.sectionForm.value).subscribe({
        next: () => {
          this.isSavingSection = false;
          this.feedbackMessage = 'Section successfully updated!';
          this.closeSectionForm();
          this.loadSections(this.course!.id);
        },
        error: (err) => {
          this.isSavingSection = false;
          this.isError = true;
          this.feedbackMessage = err.error?.detail || 'Failed to update section.';
        }
      });
    } else {
      this.instructorService.createSection(this.course.id, this.sectionForm.value).subscribe({
        next: () => {
          this.isSavingSection = false;
          this.feedbackMessage = 'Section created successfully!';
          this.closeSectionForm();
          this.loadSections(this.course!.id);
        },
        error: (err) => {
          this.isSavingSection = false;
          this.isError = true;
          this.feedbackMessage = err.error?.detail || 'Failed to create section.';
        }
      });
    }
  }

  promptDeleteSection(sec: CourseSection): void {
    this.sectionToDelete = sec;
    const others = this.getOtherSections(sec.id);
    this.reassignTargetId = others.length > 0 ? others[0].id : null;
  }

  getOtherSections(excludeId: number): CourseSection[] {
    return this.sections.filter(s => s.id !== excludeId);
  }

  confirmDeleteSection(): void {
    if (!this.sectionToDelete) return;

    const secId = this.sectionToDelete.id;
    const reassignId = this.sectionToDelete.lesson_count > 0 ? this.reassignTargetId || undefined : undefined;

    this.instructorService.deleteSection(secId, reassignId).subscribe({
      next: () => {
        this.feedbackMessage = 'Section successfully deleted.';
        this.sectionToDelete = null;
        this.loadCourse(this.course!.id);
      },
      error: (err) => {
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to delete section.';
        this.sectionToDelete = null;
      }
    });
  }

  // Lesson Handling
  openAddForm(): void {
    this.editingLessonId = null;
    const nextIndex = this.course ? this.course.lessons.length + 1 : 1;
    this.lessonForm.reset({
      title: '',
      content: '',
      order_index: nextIndex,
      section_id: this.sections.length > 0 ? this.sections[0].id : null
    });
    this.showForm = true;
  }

  editLesson(l: LessonSummary): void {
    this.editingLessonId = l.id;
    this.showForm = true;
    this.lessonService.getLesson(l.id).subscribe({
      next: (fullLesson) => {
        this.lessonForm.patchValue({
          title: fullLesson.title,
          content: fullLesson.content,
          order_index: fullLesson.order_index,
          section_id: fullLesson.section_id || null
        });
      }
    });
  }

  closeForm(): void {
    this.showForm = false;
    this.editingLessonId = null;
    this.lessonForm.reset();
  }

  onSaveLesson(): void {
    if (this.lessonForm.invalid || !this.course) return;

    this.isSaving = true;
    this.feedbackMessage = '';
    this.isError = false;

    if (this.editingLessonId) {
      this.instructorService.updateLesson(this.editingLessonId, this.lessonForm.value).subscribe({
        next: () => {
          this.isSaving = false;
          this.feedbackMessage = 'Lesson successfully updated!';
          this.closeForm();
          this.loadCourse(this.course!.id);
        },
        error: (err) => {
          this.isSaving = false;
          this.isError = true;
          this.feedbackMessage = err.error?.detail || 'Failed to update lesson.';
        }
      });
    } else {
      this.instructorService.addLesson(this.course.id, this.lessonForm.value).subscribe({
        next: () => {
          this.isSaving = false;
          this.feedbackMessage = 'Lesson successfully added to curriculum!';
          this.closeForm();
          this.loadCourse(this.course!.id);
        },
        error: (err) => {
          this.isSaving = false;
          this.isError = true;
          this.feedbackMessage = err.error?.detail || 'Failed to add lesson.';
        }
      });
    }
  }

  deleteLesson(lessonId: number): void {
    if (!confirm('Are you sure you want to permanently delete this lesson?')) return;

    this.instructorService.deleteLesson(lessonId).subscribe({
      next: () => {
        this.feedbackMessage = 'Lesson deleted.';
        this.loadCourse(this.course!.id);
      },
      error: (err) => {
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to delete lesson.';
      }
    });
  }

  getLessonsForSection(sectionId: number): LessonSummary[] {
    if (!this.course) return [];
    return this.course.lessons.filter(l => l.section_id === sectionId);
  }

  getUncategorizedLessons(): LessonSummary[] {
    if (!this.course) return [];
    return this.course.lessons.filter(l => !l.section_id);
  }
}
