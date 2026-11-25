import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AdminCourseItem } from '../../core/models/admin.model';
import { InstructorPayload, InstructorProfile } from '../../core/models/instructor.model';
import { AdminService } from '../../core/services/admin.service';

@Component({
  selector: 'app-instructor-management',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterLink],
  template: `
    <main class="instructors-page">
      <div class="container">
        <header class="page-header">
          <div>
            <a routerLink="/admin/dashboard" class="back-link">← Back to Admin Dashboard</a>
            <h1>Instructor Management</h1>
            <p class="subtitle">Register faculty, manage account access, and assign courses.</p>
          </div>
          <button class="btn btn-primary" type="button" (click)="startCreate()">
            + Add Instructor
          </button>
        </header>

        @if (feedbackMessage) {
          <div class="alert" [ngClass]="feedbackError ? 'alert-danger' : 'alert-success'">
            {{ feedbackMessage }}
          </div>
        }

        @if (formVisible) {
          <section class="card editor-card">
            <div class="editor-heading">
              <div>
                <h2>{{ editingInstructor ? 'Edit Instructor' : 'Register Instructor' }}</h2>
                @if (editingInstructor) {
                  <p>Instructor ID: <strong>{{ editingInstructor.instructor_id }}</strong></p>
                } @else {
                  <p>Instructor ID is generated automatically. A secure password setup link is emailed after saving.</p>
                }
              </div>
              <button type="button" class="btn btn-secondary" (click)="cancelEdit()">Close</button>
            </div>
            <form [formGroup]="instructorForm" (ngSubmit)="saveInstructor()">
              <div class="form-grid">
                <label class="field">
                  <span>Full Name *</span>
                  <input class="form-input" formControlName="full_name" autocomplete="name" />
                  @if (fieldInvalid('full_name')) { <small>Enter a name between 2 and 100 characters.</small> }
                </label>
                <label class="field">
                  <span>Email Address *</span>
                  <input class="form-input" type="email" formControlName="email" autocomplete="email" />
                  @if (fieldInvalid('email')) { <small>Enter a valid email address.</small> }
                </label>
                <label class="field">
                  <span>Phone Number *</span>
                  <input
                    class="form-input"
                    type="tel"
                    inputmode="numeric"
                    maxlength="30"
                    pattern="[0-9]*"
                    formControlName="phone_number"
                    autocomplete="tel"
                    (input)="sanitizePhoneNumber($event)"
                  />
                  @if (fieldInvalid('phone_number')) { <small>Enter a phone number containing 7 to 30 digits.</small> }
                </label>
                <label class="field">
                  <span>Qualification *</span>
                  <input class="form-input" formControlName="qualification" placeholder="e.g. MSc Computer Science" />
                  @if (fieldInvalid('qualification')) { <small>Qualification is required.</small> }
                </label>
                <label class="field">
                  <span>Department / Specialization *</span>
                  <input class="form-input" formControlName="department" placeholder="e.g. Computer Science" />
                  @if (fieldInvalid('department')) { <small>Department is required.</small> }
                </label>
                <label class="field">
                  <span>Subject Expertise *</span>
                  <input class="form-input" formControlName="subject_expertise" placeholder="e.g. Data Science, Networks" />
                  @if (fieldInvalid('subject_expertise')) { <small>Subject expertise is required.</small> }
                </label>
                <label class="field">
                  <span>Years of Experience *</span>
                  <input class="form-input" type="number" min="0" max="60" formControlName="experience_years" />
                  @if (fieldInvalid('experience_years')) { <small>Enter a value between 0 and 60.</small> }
                </label>
                <label class="field">
                  <span>Profile Photo URL <em>(optional)</em></span>
                  <input class="form-input" type="url" formControlName="profile_photo_url" placeholder="https://..." />
                </label>
              </div>
              <div class="form-actions">
                <button class="btn btn-secondary" type="button" (click)="cancelEdit()">Cancel</button>
                <button class="btn btn-primary" type="submit" [disabled]="instructorForm.invalid || saving">
                  {{ saving ? 'Saving...' : editingInstructor ? 'Save Changes' : 'Create Instructor Account' }}
                </button>
              </div>
            </form>
          </section>
        }

        <section class="toolbar card">
          <label class="search-field">
            <span>Search</span>
            <input
              class="form-input"
              [(ngModel)]="search"
              (keyup.enter)="loadInstructors()"
              placeholder="Name, instructor ID, or email"
            />
          </label>
          <label class="filter-field">
            <span>Department</span>
            <select class="form-select" [(ngModel)]="departmentFilter" (ngModelChange)="loadInstructors()">
              <option value="">All Departments</option>
              @for (department of departments; track department) {
                <option [value]="department">{{ department }}</option>
              }
            </select>
          </label>
          <label class="filter-field">
            <span>Status</span>
            <select class="form-select" [(ngModel)]="statusFilter" (ngModelChange)="loadInstructors()">
              <option value="">All Statuses</option>
              <option value="true">Active</option>
              <option value="false">Deactivated</option>
            </select>
          </label>
          <button class="btn btn-primary" type="button" (click)="loadInstructors()">Search</button>
        </section>

        @if (isLoading) {
          <div class="loading-state"><div class="spinner"></div><span>Loading instructors...</span></div>
        } @else if (instructors.length === 0) {
          <div class="empty-state card">
            <h2>No instructors found</h2>
            <p>Adjust your filters or add an instructor account.</p>
            <button type="button" class="btn btn-primary" (click)="startCreate()">Add Instructor</button>
          </div>
        } @else {
          <section class="card table-card">
            <div class="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Instructor ID</th>
                    <th>Name / Email</th>
                    <th>Department</th>
                    <th>Qualification</th>
                    <th>Experience</th>
                    <th>Status</th>
                    <th>Registered</th>
                    <th>Assign Course</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  @for (instructor of instructors; track instructor.user_id) {
                    <tr>
                      <td><strong class="instructor-id">{{ instructor.instructor_id }}</strong></td>
                      <td>
                        <div class="person-cell">
                          @if (instructor.profile_photo_url) {
                            <img [src]="instructor.profile_photo_url" [alt]="instructor.full_name" />
                          } @else {
                            <span class="avatar">{{ initials(instructor.full_name) }}</span>
                          }
                          <span><strong>{{ instructor.full_name }}</strong><small>{{ instructor.email }}</small></span>
                        </div>
                      </td>
                      <td>{{ instructor.department || '—' }}</td>
                      <td>{{ instructor.qualification || '—' }}</td>
                      <td>{{ instructor.experience_years }} years</td>
                      <td>
                        <span class="status-badge" [class.active]="instructor.is_active">
                          {{ instructor.is_active ? 'Active' : 'Deactivated' }}
                        </span>
                      </td>
                      <td>{{ instructor.registered_at | date:'mediumDate' }}</td>
                      <td>
                        <div class="assignment-cell">
                          <select class="form-select course-select" [(ngModel)]="courseSelections[instructor.user_id]">
                            <option [ngValue]="null">Select course</option>
                            @for (course of courses; track course.id) {
                              <option [ngValue]="course.id">{{ course.title }}</option>
                            }
                          </select>
                          <button
                            type="button"
                            class="btn btn-sm btn-secondary"
                            (click)="assignCourse(instructor)"
                            [disabled]="!courseSelections[instructor.user_id] || assigningUserId === instructor.user_id"
                          >Assign</button>
                        </div>
                      </td>
                      <td>
                        <div class="actions">
                          <button class="btn btn-sm btn-outline" type="button" (click)="toggleDetails(instructor)">
                            {{ selectedInstructorId === instructor.user_id ? 'Hide' : 'View' }}
                          </button>
                          <button class="btn btn-sm btn-secondary" type="button" (click)="startEdit(instructor)">Edit</button>
                          <button class="btn btn-sm btn-secondary" type="button" (click)="resetPassword(instructor)">Reset Password</button>
                          <button
                            class="btn btn-sm"
                            [ngClass]="instructor.is_active ? 'btn-danger' : 'btn-primary'"
                            type="button"
                            (click)="toggleStatus(instructor)"
                          >{{ instructor.is_active ? 'Deactivate' : 'Activate' }}</button>
                          <button class="btn btn-sm btn-danger" type="button" (click)="deleteInstructor(instructor)">Delete</button>
                        </div>
                      </td>
                    </tr>
                    @if (selectedInstructorId === instructor.user_id) {
                      <tr class="details-row">
                        <td colspan="9">
                          <strong>Phone:</strong> {{ instructor.phone_number || '—' }}
                          <span><strong>Expertise:</strong> {{ instructor.subject_expertise || '—' }}</span>
                        </td>
                      </tr>
                    }
                  }
                </tbody>
              </table>
            </div>
            @if (courseLoadError) {
              <p class="inline-error">{{ courseLoadError }}</p>
            }
          </section>
        }
      </div>
    </main>
  `,
  styles: [`
    .instructors-page { min-height: calc(100vh - 120px); padding: 2.5rem 0 4rem; background: var(--bg-app); }
    .page-header, .editor-heading { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }
    .page-header { margin-bottom: 1.5rem; }
    .back-link { display: inline-block; margin-bottom: .45rem; color: var(--text-muted); text-decoration: none; font-weight: 600; }
    .page-header h1 { margin: 0 0 .35rem; font-size: 2rem; }
    .subtitle, .editor-heading p { color: var(--text-muted); margin: 0; }
    .editor-card { padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #f1c8da; }
    .editor-heading { margin-bottom: 1.3rem; }
    .editor-heading h2 { margin: 0 0 .35rem; }
    .form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
    .field, .search-field, .filter-field { display: flex; flex-direction: column; gap: .45rem; }
    .field > span, .search-field > span, .filter-field > span { font-size: .88rem; font-weight: 700; color: #4a3440; }
    .field small { color: #b4235a; font-size: .8rem; }
    .field em { color: var(--text-muted); font-weight: 400; }
    .form-actions { display: flex; justify-content: flex-end; gap: .75rem; margin-top: 1.25rem; }
    .toolbar { display: flex; align-items: end; gap: 1rem; flex-wrap: wrap; padding: 1rem 1.25rem; margin-bottom: 1.25rem; }
    .search-field { flex: 1 1 260px; }
    .filter-field { flex: 0 1 200px; }
    .table-card { padding: .5rem; }
    .table-scroll { overflow-x: auto; }
    table { width: 100%; min-width: 1180px; border-collapse: collapse; text-align: left; }
    th { padding: .85rem .75rem; color: var(--text-muted); font-size: .74rem; letter-spacing: .04em; text-transform: uppercase; border-bottom: 1px solid var(--border-light); }
    td { padding: .85rem .75rem; font-size: .86rem; border-bottom: 1px solid var(--border-light); vertical-align: middle; }
    .instructor-id { color: #a91f61; white-space: nowrap; }
    .person-cell { display: flex; align-items: center; gap: .65rem; min-width: 190px; }
    .person-cell > span:last-child { display: flex; flex-direction: column; gap: .18rem; }
    .person-cell small { color: var(--text-muted); }
    .person-cell img, .avatar { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
    .avatar { display: grid; place-items: center; color: #fff; background: linear-gradient(135deg, #e83e8c, #9d5bd2); font-weight: 700; }
    .status-badge { padding: .3rem .6rem; border-radius: 99px; background: #fff0f2; color: #a62338; font-size: .78rem; font-weight: 700; white-space: nowrap; }
    .status-badge.active { background: #e7f7ee; color: #187445; }
    .assignment-cell, .actions { display: flex; align-items: center; gap: .4rem; }
    .course-select { min-width: 155px; }
    .actions { min-width: 260px; flex-wrap: wrap; }
    .details-row td { background: #fff7fa; color: #52404a; }
    .details-row span { margin-left: 1.2rem; }
    .inline-error { padding: .75rem; color: #a42338; }
    .empty-state { padding: 3rem; text-align: center; }
    .empty-state p { margin-bottom: 1.25rem; color: var(--text-muted); }
    .loading-state { display: flex; justify-content: center; align-items: center; gap: .75rem; padding: 4rem; color: var(--text-muted); }
    .spinner { width: 26px; height: 26px; border: 3px solid var(--border-color); border-top-color: var(--primary); border-radius: 50%; animation: spin .8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (max-width: 700px) {
      .form-grid { grid-template-columns: 1fr; }
      .form-actions { flex-direction: column-reverse; }
      .form-actions .btn { width: 100%; }
      .page-header h1 { font-size: 1.65rem; }
      .toolbar > .btn { width: 100%; }
    }
  `]
})
export class InstructorManagementComponent implements OnInit {
  instructors: InstructorProfile[] = [];
  courses: AdminCourseItem[] = [];
  departments: string[] = [];
  courseSelections: Record<number, number | null> = {};
  search = '';
  departmentFilter = '';
  statusFilter = '';
  isLoading = true;
  saving = false;
  formVisible = false;
  editingInstructor: InstructorProfile | null = null;
  selectedInstructorId: number | null = null;
  assigningUserId: number | null = null;
  courseLoadError = '';
  feedbackMessage = '';
  feedbackError = false;

  instructorForm: FormGroup;

  constructor(private fb: FormBuilder, private adminService: AdminService) {
    this.instructorForm = this.fb.group({
      full_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(100)]],
      email: ['', [Validators.required, Validators.email, Validators.maxLength(255)]],
      phone_number: ['', [Validators.required, Validators.minLength(7), Validators.maxLength(30), Validators.pattern(/^\d+$/)]],
      qualification: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(150)]],
      department: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(150)]],
      subject_expertise: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(255)]],
      experience_years: [0, [Validators.required, Validators.min(0), Validators.max(60)]],
      profile_photo_url: ['', Validators.pattern(/^(https?:\/\/\S+)?$/i)]
    });
  }

  ngOnInit(): void {
    this.loadInstructors();
    this.adminService.getCourses({ page: 1, page_size: 100 }).subscribe({
      next: response => {
        this.courses = response.items;
        this.courseLoadError = '';
      },
      error: error => {
        this.courseLoadError = error.error?.detail || 'Unable to load courses for assignment.';
      }
    });
  }

  loadInstructors(): void {
    this.isLoading = true;
    const activeStatus = this.statusFilter === '' ? undefined : this.statusFilter === 'true';
    this.adminService.getInstructors({
      search: this.search.trim() || undefined,
      department: this.departmentFilter || undefined,
      is_active: activeStatus
    }).subscribe({
      next: instructors => {
        this.instructors = instructors;
        if (!this.search && !this.departmentFilter && this.statusFilter === '') {
          this.departments = [...new Set(instructors.map(item => item.department).filter(Boolean))].sort();
        }
        this.isLoading = false;
      },
      error: error => {
        this.isLoading = false;
        this.showError(error, 'Unable to load instructor accounts.');
      }
    });
  }

  startCreate(): void {
    this.editingInstructor = null;
    this.instructorForm.reset({
      full_name: '',
      email: '',
      phone_number: '',
      qualification: '',
      department: '',
      subject_expertise: '',
      experience_years: 0,
      profile_photo_url: ''
    });
    this.formVisible = true;
    this.feedbackMessage = '';
  }

  startEdit(instructor: InstructorProfile): void {
    this.editingInstructor = instructor;
    this.instructorForm.reset({
      full_name: instructor.full_name,
      email: instructor.email,
      phone_number: instructor.phone_number,
      qualification: instructor.qualification,
      department: instructor.department,
      subject_expertise: instructor.subject_expertise,
      experience_years: instructor.experience_years,
      profile_photo_url: instructor.profile_photo_url || ''
    });
    this.formVisible = true;
    this.feedbackMessage = '';
  }

  cancelEdit(): void {
    this.formVisible = false;
    this.editingInstructor = null;
  }

  fieldInvalid(fieldName: string): boolean {
    const control = this.instructorForm.get(fieldName);
    return !!control && control.invalid && (control.dirty || control.touched);
  }

  sanitizePhoneNumber(event: Event): void {
    const input = event.target as HTMLInputElement;
    const digitsOnly = input.value.replace(/[^0-9]/g, '');

    if (input.value !== digitsOnly) {
      input.value = digitsOnly;
      this.instructorForm.controls['phone_number'].setValue(digitsOnly);
    }
  }

  saveInstructor(): void {
    if (this.instructorForm.invalid || this.saving) {
      this.instructorForm.markAllAsTouched();
      return;
    }
    const raw = this.instructorForm.getRawValue();
    const payload: InstructorPayload = {
      full_name: raw.full_name!.trim(),
      email: raw.email!.trim(),
      phone_number: raw.phone_number!.trim(),
      qualification: raw.qualification!.trim(),
      department: raw.department!.trim(),
      subject_expertise: raw.subject_expertise!.trim(),
      experience_years: Number(raw.experience_years),
      profile_photo_url: raw.profile_photo_url?.trim() || null
    };
    const editing = this.editingInstructor;
    this.saving = true;
    const request = editing
      ? this.adminService.updateInstructor(editing.user_id, payload)
      : this.adminService.createInstructor(payload);
    request.subscribe({
      next: response => {
        this.saving = false;
        this.cancelEdit();
        if (editing) {
          this.showSuccess('Instructor profile updated.');
        } else {
          this.showSuccess(
            response.email_delivery_status === 'sent'
              ? `Instructor registered. A secure password setup email was sent to ${response.email}.`
              : `Instructor registered, but email delivery status is ${response.email_delivery_status}. Configure SMTP and use Reset Password to resend the setup link.`
          );
        }
        this.loadInstructors();
      },
      error: error => {
        this.saving = false;
        this.showError(error, 'Unable to save instructor details.');
      }
    });
  }

  toggleDetails(instructor: InstructorProfile): void {
    this.selectedInstructorId = this.selectedInstructorId === instructor.user_id ? null : instructor.user_id;
  }

  toggleStatus(instructor: InstructorProfile): void {
    const nextStatus = !instructor.is_active;
    const action = nextStatus ? 'activate' : 'deactivate';
    if (!window.confirm(`Are you sure you want to ${action} ${instructor.full_name}'s account?`)) return;
    this.adminService.updateInstructorStatus(instructor.user_id, nextStatus).subscribe({
      next: response => {
        this.showSuccess(
          response.email_delivery_status === 'sent'
            ? `Account ${action}d and notification email sent.`
            : `Account ${action}d. Notification email status: ${response.email_delivery_status}.`
        );
        this.loadInstructors();
      },
      error: error => this.showError(error, `Unable to ${action} instructor account.`)
    });
  }

  resetPassword(instructor: InstructorProfile): void {
    if (!window.confirm(`Send a secure password setup/reset link to ${instructor.email}?`)) return;
    this.adminService.resetInstructorPassword(instructor.user_id).subscribe({
      next: response => this.showSuccess(response.message),
      error: error => this.showError(error, 'Unable to send a password reset email.')
    });
  }

  deleteInstructor(instructor: InstructorProfile): void {
    if (!window.confirm(`Permanently delete ${instructor.full_name}'s instructor account? This cannot be undone.`)) return;
    this.adminService.deleteInstructor(instructor.user_id).subscribe({
      next: response => {
        this.showSuccess(response.message);
        this.loadInstructors();
      },
      error: error => this.showError(error, 'Unable to delete instructor account.')
    });
  }

  assignCourse(instructor: InstructorProfile): void {
    const courseId = this.courseSelections[instructor.user_id];
    if (!courseId) return;
    this.assigningUserId = instructor.user_id;
    this.adminService.assignCourse(courseId, instructor.user_id).subscribe({
      next: response => {
        this.assigningUserId = null;
        this.showSuccess(response.message);
        this.courseSelections[instructor.user_id] = null;
      },
      error: error => {
        this.assigningUserId = null;
        this.showError(error, 'Unable to assign course.');
      }
    });
  }

  initials(name: string): string {
    return name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();
  }

  private showSuccess(message: string): void {
    this.feedbackMessage = message;
    this.feedbackError = false;
  }

  private showError(error: { error?: { detail?: string } }, fallback: string): void {
    this.feedbackMessage = error.error?.detail || fallback;
    this.feedbackError = true;
  }
}
