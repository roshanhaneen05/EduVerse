import { Component, OnInit, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpEventType } from '@angular/common/http';
import { CourseService } from '../../core/services/course.service';
import { InstructorService } from '../../core/services/instructor.service';
import { MaterialService } from '../../core/services/material.service';
import { CourseDetail, CourseSection, LessonSummary } from '../../core/models/course.model';
import { LearningMaterial } from '../../core/models/material.model';

@Component({
  selector: 'app-material-manager',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink],
  template: `
    <div class="material-mgr-page">
      <div class="container">
        <!-- Navigation Header -->
        <div class="page-header">
          <div>
            <a routerLink="/instructor/dashboard" class="back-link">← Back to Instructor Hub</a>
            <h1>Learning Materials & Resources</h1>
            <p class="subtitle" *ngIf="course">
              Course: <strong>{{ course.title }}</strong>
            </p>
          </div>
          <button (click)="openUploadModal()" class="btn btn-primary" *ngIf="!showUploadForm">
            + Upload New Material
          </button>
        </div>

        <!-- Global Alert Message -->
        @if (feedbackMessage) {
          <div class="alert" [ngClass]="isError ? 'alert-danger' : 'alert-success'">
            {{ feedbackMessage }}
          </div>
        }

        <!-- Upload / Edit Material Card -->
        @if (showUploadForm) {
          <div class="card form-card">
            <div class="form-header">
              <h3>{{ editingMaterialId ? 'Edit Material Details' : 'Upload Secure Learning Material' }}</h3>
              <button (click)="closeForm()" class="btn btn-sm btn-secondary">Close Form</button>
            </div>

            <form [formGroup]="materialForm" (ngSubmit)="onSaveMaterial()">
              @if (!editingMaterialId) {
                <!-- File Input Selector -->
                <div class="form-group">
                  <label class="form-label" for="file_input">
                    Select File (PDF, DOCX, PPTX, TXT, PNG, JPG/JPEG — Max 25 MB)
                  </label>
                  <div class="file-drop-area" (click)="fileInput.click()">
                    <input
                      #fileInput
                      id="file_input"
                      type="file"
                      (change)="onFileSelected($event)"
                      style="display: none;"
                      accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg"
                    />
                    <div class="drop-content">
                      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                      </svg>
                      @if (selectedFile) {
                        <div class="selected-file-info">
                          <strong>{{ selectedFile.name }}</strong>
                          <span>({{ formatBytes(selectedFile.size) }})</span>
                        </div>
                      } @else {
                        <p>Click or drag a supported document or image here to upload</p>
                        <span class="file-types-hint">Supported: PDF, DOCX, PPTX, TXT, PNG, JPG/JPEG</span>
                      }
                    </div>
                  </div>
                  @if (fileError) {
                    <div class="form-error">{{ fileError }}</div>
                  }
                </div>
              }

              <div class="form-group">
                <label class="form-label" for="title">Material Title</label>
                <input
                  id="title"
                  type="text"
                  class="form-input"
                  formControlName="title"
                  placeholder="e.g. Distributed Architecture Blueprint Reference Guide"
                />
              </div>

              <div class="form-group">
                <label class="form-label" for="description">Summary / Overview (Optional)</label>
                <textarea
                  id="description"
                  rows="3"
                  class="form-textarea"
                  formControlName="description"
                  placeholder="Brief summary of topics, chapters, or deliverables covered by this resource..."
                ></textarea>
              </div>

              <div class="form-row">
                <div class="form-group flex-1">
                  <label class="form-label" for="section_id">Curriculum Section / Module (Optional)</label>
                  <select id="section_id" class="form-input" formControlName="section_id">
                    <option [ngValue]="null">No Section (General Course Resource)</option>
                    @for (sec of sections; track sec.id) {
                      <option [ngValue]="sec.id">{{ sec.order_index }}. {{ sec.title }}</option>
                    }
                  </select>
                </div>

                <div class="form-group flex-1">
                  <label class="form-label" for="lesson_id">Specific Lesson Link (Optional)</label>
                  <select id="lesson_id" class="form-input" formControlName="lesson_id">
                    <option [ngValue]="null">No Specific Lesson</option>
                    @for (les of lessons; track les.id) {
                      <option [ngValue]="les.id">{{ les.order_index }}. {{ les.title }}</option>
                    }
                  </select>
                </div>
              </div>

              @if (uploadProgress > 0 && uploadProgress < 100) {
                <div class="progress-bar-container">
                  <div class="progress-bar" [style.width.%]="uploadProgress"></div>
                  <span class="progress-text">Uploading: {{ uploadProgress }}%</span>
                </div>
              }

              <div class="form-actions">
                <button type="button" (click)="closeForm()" class="btn btn-secondary">Cancel</button>
                <button
                  type="submit"
                  class="btn btn-primary"
                  [disabled]="materialForm.invalid || isSaving || (!editingMaterialId && !selectedFile)"
                >
                  @if (isSaving) {
                    <span>Saving...</span>
                  } @else {
                    <span>{{ editingMaterialId ? 'Update Material' : 'Upload Material' }}</span>
                  }
                </button>
              </div>
            </form>
          </div>
        }

        <!-- Materials List View -->
        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading course learning materials...</span>
          </div>
        } @else if (materials.length === 0) {
          <div class="empty-block card">
            <h3>No learning materials uploaded yet</h3>
            <p>Upload lecture notes, architectural whitepapers, slides, or diagrams for your students to download.</p>
            <button (click)="openUploadModal()" class="btn btn-primary">+ Upload First Material</button>
          </div>
        } @else {
          <div class="materials-table-card card">
            <div class="table-header">
              <h3>Uploaded Materials ({{ materials.length }})</h3>
            </div>
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Document Details</th>
                    <th>Module / Lesson</th>
                    <th>Size</th>
                    <th>Uploaded</th>
                    <th style="width: 190px;">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  @for (m of materials; track m.id) {
                    <tr>
                      <td>
                        <span class="ext-badge" [ngClass]="getExtBadgeClass(m.file_extension)">
                          {{ m.file_extension }}
                        </span>
                      </td>
                      <td>
                        <div class="material-title-row">
                          <strong>{{ m.title }}</strong>
                        </div>
                        <div class="filename-subtext">{{ m.original_filename }}</div>
                        @if (m.description) {
                          <div class="material-desc-subtext">{{ m.description }}</div>
                        }
                      </td>
                      <td>
                        @if (m.section_title) {
                          <span class="badge badge-primary badge-sm">{{ m.section_title }}</span>
                        } @else {
                          <span class="text-muted">General</span>
                        }
                        @if (m.lesson_title) {
                          <div class="lesson-tag">↳ {{ m.lesson_title }}</div>
                        }
                      </td>
                      <td>
                        <span class="size-pill">{{ m.file_size_formatted }}</span>
                      </td>
                      <td>
                        {{ m.created_at | date:'mediumDate' }}
                      </td>
                      <td>
                        <div class="action-btn-group">
                          <button (click)="downloadMaterial(m)" class="btn btn-sm btn-outline" title="Download File">
                            Download
                          </button>
                          <button (click)="editMaterial(m)" class="btn btn-sm btn-secondary" title="Edit Metadata">
                            Edit
                          </button>
                          <button (click)="deleteMaterial(m)" class="btn btn-sm btn-danger" title="Delete Material">
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .material-mgr-page {
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
      margin-bottom: 2rem;
      padding: 1.75rem;
    }
    .form-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.5rem;
      border-bottom: 1px solid var(--border-light);
      padding-bottom: 0.75rem;
    }
    .file-drop-area {
      border: 2px dashed var(--border-color);
      border-radius: var(--radius-md);
      padding: 2rem;
      text-align: center;
      cursor: pointer;
      background-color: var(--bg-subtle);
      transition: var(--transition);
    }
    .file-drop-area:hover {
      border-color: var(--primary);
      background-color: #f8fafc;
    }
    .drop-content svg {
      color: var(--primary);
      margin-bottom: 0.75rem;
    }
    .selected-file-info {
      font-size: 1.05rem;
      color: var(--primary);
    }
    .file-types-hint {
      display: block;
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: 0.35rem;
    }
    .form-row {
      display: flex;
      gap: 1rem;
      flex-wrap: wrap;
    }
    .flex-1 { flex: 1; min-width: 200px; }
    .form-actions {
      display: flex;
      justify-content: flex-end;
      gap: 0.75rem;
      margin-top: 1.5rem;
    }
    .progress-bar-container {
      background-color: var(--border-light);
      border-radius: var(--radius-sm);
      height: 8px;
      overflow: hidden;
      margin-top: 1rem;
      position: relative;
    }
    .progress-bar {
      background-color: var(--primary);
      height: 100%;
      transition: width 0.3s ease;
    }
    .progress-text {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 0.25rem;
      display: block;
    }
    .materials-table-card {
      padding: 0;
      overflow: hidden;
    }
    .table-header {
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border-light);
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
      background-color: var(--bg-subtle);
      padding: 0.85rem 1.25rem;
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    td {
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border-light);
      font-size: 0.95rem;
      vertical-align: middle;
    }
    .ext-badge {
      display: inline-block;
      font-size: 0.75rem;
      font-weight: 800;
      padding: 0.25rem 0.5rem;
      border-radius: var(--radius-sm);
      letter-spacing: 0.05em;
    }
    .ext-pdf { background-color: #fee2e2; color: #b91c1c; }
    .ext-docx { background-color: #dbeafe; color: #1d4ed8; }
    .ext-pptx { background-color: #ffedd5; color: #c2410c; }
    .ext-txt { background-color: #f1f5f9; color: #475569; }
    .ext-img { background-color: #dcfce7; color: #15803d; }
    .material-title-row {
      font-size: 1rem;
      margin-bottom: 0.15rem;
    }
    .filename-subtext {
      font-size: 0.8rem;
      color: var(--text-muted);
      font-family: monospace;
    }
    .material-desc-subtext {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-top: 0.25rem;
    }
    .lesson-tag {
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: 0.25rem;
    }
    .size-pill {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-muted);
    }
    .action-btn-group {
      display: flex;
      gap: 0.4rem;
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
export class MaterialManagerComponent implements OnInit {
  @Input() id!: string; // course id
  course: CourseDetail | null = null;
  sections: CourseSection[] = [];
  lessons: LessonSummary[] = [];
  materials: LearningMaterial[] = [];
  isLoading = true;

  // Upload / Edit form state
  showUploadForm = false;
  editingMaterialId: number | null = null;
  materialForm: FormGroup;
  selectedFile: File | null = null;
  fileError = '';
  isSaving = false;
  uploadProgress = 0;

  feedbackMessage = '';
  isError = false;

  constructor(
    private courseService: CourseService,
    private instructorService: InstructorService,
    private materialService: MaterialService,
    private fb: FormBuilder
  ) {
    this.materialForm = this.fb.group({
      title: ['', [Validators.required, Validators.minLength(2)]],
      description: [''],
      section_id: [null],
      lesson_id: [null],
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
        this.lessons = data.lessons || [];
        this.loadSections(courseId);
        this.loadMaterials(courseId);
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

  loadMaterials(courseId: number): void {
    this.materialService.getCourseMaterials(courseId).subscribe({
      next: (mats) => {
        this.materials = mats;
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  openUploadModal(): void {
    this.editingMaterialId = null;
    this.selectedFile = null;
    this.fileError = '';
    this.uploadProgress = 0;
    this.materialForm.reset({
      title: '',
      description: '',
      section_id: null,
      lesson_id: null,
    });
    this.showUploadForm = true;
  }

  editMaterial(m: LearningMaterial): void {
    this.editingMaterialId = m.id;
    this.selectedFile = null;
    this.fileError = '';
    this.materialForm.patchValue({
      title: m.title,
      description: m.description || '',
      section_id: m.section_id || null,
      lesson_id: m.lesson_id || null,
    });
    this.showUploadForm = true;
  }

  closeForm(): void {
    this.showUploadForm = false;
    this.editingMaterialId = null;
    this.selectedFile = null;
    this.fileError = '';
    this.materialForm.reset();
  }

  onFileSelected(event: any): void {
    const file = event.target.files[0];
    if (!file) return;

    this.fileError = '';
    const maxBytes = 25 * 1024 * 1024; // 25 MB
    if (file.size > maxBytes) {
      this.fileError = 'Selected file exceeds maximum allowed size of 25 MB.';
      this.selectedFile = null;
      return;
    }

    this.selectedFile = file;
    // Auto-fill title if empty
    if (!this.materialForm.get('title')?.value) {
      const cleanTitle = file.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ');
      this.materialForm.patchValue({ title: cleanTitle });
    }
  }

  onSaveMaterial(): void {
    if (this.materialForm.invalid || !this.course) return;

    this.isSaving = true;
    this.feedbackMessage = '';
    this.isError = false;

    if (this.editingMaterialId) {
      // Update metadata
      this.materialService.updateMaterial(this.editingMaterialId, this.materialForm.value).subscribe({
        next: () => {
          this.isSaving = false;
          this.feedbackMessage = 'Material metadata updated successfully!';
          this.closeForm();
          this.loadMaterials(this.course!.id);
        },
        error: (err) => {
          this.isSaving = false;
          this.isError = true;
          this.feedbackMessage = err.error?.detail || 'Failed to update material.';
        }
      });
    } else {
      // Upload new file
      if (!this.selectedFile) {
        this.fileError = 'Please select a file to upload.';
        this.isSaving = false;
        return;
      }

      const formData = new FormData();
      formData.append('file', this.selectedFile);
      formData.append('title', this.materialForm.value.title);
      if (this.materialForm.value.description) {
        formData.append('description', this.materialForm.value.description);
      }
      if (this.materialForm.value.section_id) {
        formData.append('section_id', this.materialForm.value.section_id.toString());
      }
      if (this.materialForm.value.lesson_id) {
        formData.append('lesson_id', this.materialForm.value.lesson_id.toString());
      }

      this.materialService.uploadMaterialWithProgress(this.course.id, formData).subscribe({
        next: (event: any) => {
          if (event.type === HttpEventType.UploadProgress && event.total) {
            this.uploadProgress = Math.round((100 * event.loaded) / event.total);
          } else if (event.type === HttpEventType.Response) {
            this.isSaving = false;
            this.uploadProgress = 0;
            this.feedbackMessage = 'Learning material uploaded and verified successfully!';
            this.closeForm();
            this.loadMaterials(this.course!.id);
          }
        },
        error: (err) => {
          this.isSaving = false;
          this.isError = true;
          this.uploadProgress = 0;
          this.feedbackMessage = err.error?.detail || 'Failed to upload material file.';
        }
      });
    }
  }

  downloadMaterial(m: LearningMaterial): void {
    this.materialService.triggerBrowserDownload(m.id, m.original_filename);
  }

  deleteMaterial(m: LearningMaterial): void {
    if (!confirm(`Are you sure you want to delete "${m.title}"? The associated file will be permanently removed.`)) {
      return;
    }

    this.materialService.deleteMaterial(m.id).subscribe({
      next: (res) => {
        this.feedbackMessage = res.message;
        this.loadMaterials(this.course!.id);
      },
      error: (err) => {
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to delete material.';
      }
    });
  }

  getExtBadgeClass(ext: string): string {
    switch (ext?.toUpperCase()) {
      case 'PDF': return 'ext-pdf';
      case 'DOCX': return 'ext-docx';
      case 'PPTX': return 'ext-pptx';
      case 'TXT': return 'ext-txt';
      case 'PNG':
      case 'JPG':
      case 'JPEG': return 'ext-img';
      default: return 'ext-txt';
    }
  }

  formatBytes(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    else if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }
}

