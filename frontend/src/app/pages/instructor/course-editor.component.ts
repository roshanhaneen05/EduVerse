import { Component, OnInit, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { InstructorService } from '../../core/services/instructor.service';
import { CourseService } from '../../core/services/course.service';

@Component({
  selector: 'app-course-editor',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="editor-page">
      <div class="container editor-container">
        <div class="page-header">
          <a routerLink="/instructor/dashboard" class="back-link">← Back to Instructor Hub</a>
          <h1>{{ isEditMode ? 'Edit Course Details' : 'Create New Course' }}</h1>
          <p class="subtitle">Set up the foundational metadata and classification for this technical course.</p>
        </div>

        @if (errorMessage) {
          <div class="alert alert-danger">{{ errorMessage }}</div>
        }

        <div class="card editor-card">
          <form [formGroup]="courseForm" (ngSubmit)="onSubmit()">
            <div class="form-group">
              <label class="form-label" for="title">Course Title</label>
              <input
                id="title"
                type="text"
                class="form-input"
                formControlName="title"
                placeholder="e.g. Production Microservices with FastAPI"
              />
              @if (isFieldInvalid('title')) {
                <div class="form-error">Title is required (min 5 characters).</div>
              }
            </div>

            <div class="form-group">
              <label class="form-label" for="description">Course Description</label>
              <textarea
                id="description"
                rows="4"
                class="form-textarea"
                formControlName="description"
                placeholder="Provide a comprehensive summary of concepts, prerequisites, and learning outcomes..."
              ></textarea>
              @if (isFieldInvalid('description')) {
                <div class="form-error">Description is required (min 20 characters).</div>
              }
            </div>

            <div class="form-row">
              <div class="form-group flex-1">
                <label class="form-label" for="category">Category</label>
                <select id="category" class="form-select" formControlName="category">
                  <option value="Backend Engineering">Backend Engineering</option>
                  <option value="Cloud & DevOps">Cloud & DevOps</option>
                  <option value="Security & Architecture">Security & Architecture</option>
                  <option value="Full-Stack Development">Full-Stack Development</option>
                  <option value="Data Engineering">Data Engineering</option>
                </select>
              </div>

              <div class="form-group flex-1">
                <label class="form-label" for="difficulty">Difficulty Level</label>
                <select id="difficulty" class="form-select" formControlName="difficulty">
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </div>
            </div>

            <div class="form-group checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" formControlName="is_published" />
                <span>Publish Course (Make visible in public catalog immediately)</span>
              </label>
            </div>

            <div class="form-actions">
              <a routerLink="/instructor/dashboard" class="btn btn-secondary">Cancel</a>
              <button type="submit" class="btn btn-primary" [disabled]="courseForm.invalid || isSubmitting">
                @if (isSubmitting) {
                  <span>Saving...</span>
                } @else {
                  <span>{{ isEditMode ? 'Update Course' : 'Create & Proceed to Lessons' }}</span>
                }
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .editor-page {
      padding: 2.5rem 0 4rem 0;
      background-color: var(--bg-app);
    }
    .editor-container {
      max-width: 780px;
    }
    .page-header {
      margin-bottom: 2rem;
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
      font-size: 1rem;
    }
    .editor-card {
      padding: 2.25rem;
    }
    .form-row {
      display: flex;
      gap: 1.5rem;
    }
    @media (max-width: 600px) {
      .form-row { flex-direction: column; }
    }
    .flex-1 { flex: 1; }
    .checkbox-group {
      margin: 1.5rem 0;
      padding: 1rem;
      background: var(--bg-subtle);
      border-radius: var(--radius-md);
    }
    .checkbox-label {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
    }
    .form-actions {
      display: flex;
      justify-content: flex-end;
      gap: 1rem;
      margin-top: 2rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--border-light);
    }
  `]
})
export class CourseEditorComponent implements OnInit {
  @Input() id?: string; // If present, edit mode
  isEditMode = false;
  courseForm: FormGroup;
  isSubmitting = false;
  errorMessage = '';

  constructor(
    private fb: FormBuilder,
    private instructorService: InstructorService,
    private courseService: CourseService,
    private router: Router
  ) {
    this.courseForm = this.fb.group({
      title: ['', [Validators.required, Validators.minLength(5), Validators.maxLength(150)]],
      description: ['', [Validators.required, Validators.minLength(20)]],
      category: ['Backend Engineering', [Validators.required]],
      difficulty: ['beginner', [Validators.required]],
      is_published: [false]
    });
  }

  ngOnInit(): void {
    if (this.id) {
      this.isEditMode = true;
      this.courseService.getCourse(Number(this.id)).subscribe({
        next: (course) => {
          this.courseForm.patchValue({
            title: course.title,
            description: course.description,
            category: course.category,
            difficulty: course.difficulty,
            is_published: course.is_published
          });
        },
        error: () => {
          this.errorMessage = 'Could not load course details for editing.';
        }
      });
    }
  }

  isFieldInvalid(field: string): boolean {
    const control = this.courseForm.get(field);
    return !!(control && control.invalid && (control.dirty || control.touched));
  }

  onSubmit(): void {
    if (this.courseForm.invalid) return;

    this.isSubmitting = true;
    this.errorMessage = '';

    if (this.isEditMode && this.id) {
      this.instructorService.updateCourse(Number(this.id), this.courseForm.value).subscribe({
        next: () => {
          this.isSubmitting = false;
          this.router.navigate(['/instructor/dashboard']);
        },
        error: (err) => {
          this.isSubmitting = false;
          this.errorMessage = err.error?.detail || 'Failed to update course.';
        }
      });
    } else {
      this.instructorService.createCourse(this.courseForm.value).subscribe({
        next: (created) => {
          this.isSubmitting = false;
          // Go to lesson manager for this new course
          this.router.navigate(['/instructor/courses', created.id, 'lessons']);
        },
        error: (err) => {
          this.isSubmitting = false;
          this.errorMessage = err.error?.detail || 'Failed to create course.';
        }
      });
    }
  }
}

