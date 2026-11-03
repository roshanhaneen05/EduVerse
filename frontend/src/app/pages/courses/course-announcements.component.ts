import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { CourseService } from '../../core/services/course.service';
import { AnnouncementService } from '../../core/services/announcement.service';
import { CourseAnnouncement } from '../../core/models/announcement.model';
import { Course } from '../../core/models/course.model';

@Component({
  selector: 'app-course-announcements',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="announcements-page">
      <div class="container">
        <!-- Breadcrumb & Top Bar -->
        <div class="nav-breadcrumbs">
          <a [routerLink]="['/courses', courseId()]" class="back-link">
            ← Back to {{ course()?.title || 'Course' }}
          </a>
        </div>

        <header class="page-header">
          <div class="header-left">
            <div class="title-with-badge">
              <h1>Course Announcements</h1>
              <span class="badge badge-primary">{{ announcements().length }} Total</span>
            </div>
            <p class="subtitle">
              Official faculty announcements and academic notices for <strong>{{ course()?.title || 'this course' }}</strong>.
            </p>
          </div>

          <div class="header-actions">
            @if (canManage()) {
              <button (click)="openCreateModal()" class="btn btn-primary">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
                Post Announcement
              </button>
            }
          </div>
        </header>

        <!-- Status Alerts -->
        @if (errorMessage()) {
          <div class="alert alert-danger">
            {{ errorMessage() }}
            <button (click)="loadAnnouncements()" class="btn btn-sm btn-outline retry-btn">Retry</button>
          </div>
        }

        @if (successMessage()) {
          <div class="alert alert-success">
            {{ successMessage() }}
          </div>
        }

        <!-- Filter bar (for instructors/admins) -->
        @if (canManage() && announcements().length > 0) {
          <div class="filter-bar card">
            <div class="filter-group">
              <span class="filter-label">Filter:</span>
              <button
                (click)="setFilter('all')"
                class="filter-btn"
                [class.active]="filter() === 'all'"
              >
                All ({{ announcements().length }})
              </button>
              <button
                (click)="setFilter('published')"
                class="filter-btn"
                [class.active]="filter() === 'published'"
              >
                Published ({{ getCount('published') }})
              </button>
              <button
                (click)="setFilter('draft')"
                class="filter-btn"
                [class.active]="filter() === 'draft'"
              >
                Drafts ({{ getCount('draft') }})
              </button>
            </div>
          </div>
        }

        <!-- Loading State -->
        @if (isLoading()) {
          <div class="loading-state card">
            <div class="spinner"></div>
            <p>Loading course announcements...</p>
          </div>
        } @else if (filteredAnnouncements().length === 0) {
          <!-- Empty State -->
          <div class="empty-state card">
            <div class="empty-icon">📢</div>
            <h3>No Announcements Yet</h3>
            <p>
              @if (filter() === 'draft') {
                No draft announcements found.
              } @else {
                There are no published announcements for this course at this time. Check back soon for instructor updates.
              }
            </p>
            @if (canManage()) {
              <button (click)="openCreateModal()" class="btn btn-primary">
                Create First Announcement
              </button>
            }
          </div>
        } @else {
          <!-- Announcements List -->
          <div class="announcements-feed">
            @for (ann of filteredAnnouncements(); track ann.id) {
              <article class="announcement-card card" [class.draft-card]="!ann.is_published">
                <div class="card-header">
                  <div class="author-block">
                    <div class="author-avatar">
                      {{ getInitials(ann.author?.full_name || 'Faculty') }}
                    </div>
                    <div class="author-meta">
                      <span class="author-name">{{ ann.author?.full_name || 'Course Faculty' }}</span>
                      <span class="badge" [ngClass]="ann.author?.role === 'instructor' ? 'badge-primary' : 'badge-neutral'">
                        {{ ann.author?.role === 'instructor' ? 'Course Instructor' : (ann.author?.role || 'Staff') }}
                      </span>
                      <span class="timestamp">{{ ann.created_at | date:'mediumDate' }} at {{ ann.created_at | date:'shortTime' }}</span>
                    </div>
                  </div>

                  <div class="header-right">
                    @if (!ann.is_published) {
                      <span class="badge badge-warning">Draft (Unpublished)</span>
                    } @else {
                      <span class="badge badge-success">Published</span>
                    }

                    @if (canManage()) {
                      <div class="manage-btns">
                        <button (click)="openEditModal(ann)" class="btn btn-sm btn-secondary" title="Edit Announcement">
                          Edit
                        </button>
                        <button (click)="confirmDelete(ann)" class="btn btn-sm btn-outline btn-danger" title="Delete Announcement">
                          Delete
                        </button>
                      </div>
                    }
                  </div>
                </div>

                <div class="card-body">
                  <h2 class="announcement-title">{{ ann.title }}</h2>
                  <div class="announcement-content">
                    <p>{{ ann.content }}</p>
                  </div>
                </div>
              </article>
            }
          </div>
        }
      </div>

      <!-- Create / Edit Announcement Modal -->
      @if (showModal()) {
        <div class="modal-backdrop" (click)="closeModal()">
          <div class="modal-card card" (click)="$event.stopPropagation()">
            <div class="modal-header">
              <h3>{{ isEditing() ? 'Edit Announcement' : 'Post New Announcement' }}</h3>
              <button (click)="closeModal()" class="close-btn">&times;</button>
            </div>

            <form (ngSubmit)="saveAnnouncement()">
              <div class="modal-body">
                <div class="form-group">
                  <label for="annTitle">Title <span class="required">*</span></label>
                  <input
                    id="annTitle"
                    type="text"
                    class="form-control"
                    [(ngModel)]="formTitle"
                    name="formTitle"
                    required
                    placeholder="e.g. Schedule update for Week 3 workshops"
                  />
                </div>

                <div class="form-group">
                  <label for="annContent">Message Content <span class="required">*</span></label>
                  <textarea
                    id="annContent"
                    class="form-control"
                    rows="6"
                    [(ngModel)]="formContent"
                    name="formContent"
                    required
                    placeholder="Write your announcement details clearly..."
                  ></textarea>
                </div>

                <div class="form-check-group">
                  <label class="checkbox-label">
                    <input
                      type="checkbox"
                      [(ngModel)]="formPublished"
                      name="formPublished"
                    />
                    <span>Publish immediately to enrolled students</span>
                  </label>
                  <small class="help-text">
                    When checked, enrolled students will be notified in real-time. Uncheck to save as a private draft.
                  </small>
                </div>
              </div>

              <div class="modal-footer">
                <button type="button" (click)="closeModal()" class="btn btn-secondary">
                  Cancel
                </button>
                <button
                  type="submit"
                  class="btn btn-primary"
                  [disabled]="isSaving() || !formTitle.trim() || !formContent.trim()"
                >
                  @if (isSaving()) {
                    Saving...
                  } @else {
                    {{ isEditing() ? 'Save Changes' : (formPublished ? 'Publish Announcement' : 'Save Draft') }}
                  }
                </button>
              </div>
            </form>
          </div>
        </div>
      }

      <!-- Delete Confirmation Modal -->
      @if (announcementToDelete()) {
        <div class="modal-backdrop" (click)="cancelDelete()">
          <div class="modal-card card" (click)="$event.stopPropagation()">
            <div class="modal-header">
              <h3>Confirm Deletion</h3>
              <button (click)="cancelDelete()" class="close-btn">&times;</button>
            </div>
            <div class="modal-body">
              <p>
                Are you sure you want to delete the announcement
                <strong>"{{ announcementToDelete()?.title }}"</strong>?
              </p>
              <p class="text-danger"><small>This action cannot be undone.</small></p>
            </div>
            <div class="modal-footer">
              <button (click)="cancelDelete()" class="btn btn-secondary">Cancel</button>
              <button (click)="executeDelete()" class="btn btn-danger" [disabled]="isDeleting()">
                @if (isDeleting()) { Deleting... } @else { Delete Announcement }
              </button>
            </div>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .announcements-page {
      padding: 2.5rem 0 4rem;
      min-height: calc(100vh - 70px);
      background-color: var(--bg-surface);
    }
    .nav-breadcrumbs {
      margin-bottom: 1rem;
    }
    .back-link {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      font-size: 0.9rem;
      color: var(--text-muted);
      text-decoration: none;
      transition: color 0.2s;
    }
    .back-link:hover {
      color: var(--primary);
    }
    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 2rem;
      gap: 1.5rem;
      flex-wrap: wrap;
    }
    .title-with-badge {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 0.35rem;
    }
    .title-with-badge h1 {
      margin: 0;
      font-size: 2rem;
    }
    .subtitle {
      color: var(--text-muted);
      margin: 0;
      font-size: 1rem;
    }
    .header-actions {
      display: flex;
      gap: 0.75rem;
    }
    .filter-bar {
      padding: 0.75rem 1.25rem;
      margin-bottom: 1.5rem;
    }
    .filter-group {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
    }
    .filter-label {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-muted);
      margin-right: 0.25rem;
    }
    .filter-btn {
      background: none;
      border: 1px solid transparent;
      padding: 0.4rem 0.85rem;
      border-radius: var(--radius-md);
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      color: var(--text-muted);
      transition: all 0.2s;
    }
    .filter-btn:hover {
      background-color: var(--bg-subtle);
      color: var(--text-primary);
    }
    .filter-btn.active {
      background-color: var(--primary);
      color: #ffffff;
    }
    .loading-state, .empty-state {
      padding: 3.5rem 2rem;
      text-align: center;
    }
    .spinner {
      width: 36px;
      height: 36px;
      border: 3px solid var(--border-color);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 1rem;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .empty-icon {
      font-size: 3rem;
      margin-bottom: 1rem;
    }
    .empty-state h3 {
      margin-bottom: 0.5rem;
    }
    .empty-state p {
      color: var(--text-muted);
      max-width: 500px;
      margin: 0 auto 1.5rem;
    }
    .announcements-feed {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }
    .announcement-card {
      padding: 1.75rem;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .announcement-card:hover {
      box-shadow: var(--shadow-md);
    }
    .draft-card {
      border-left: 4px solid var(--warning, #f59e0b);
      background-color: rgba(245, 158, 11, 0.02);
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1.25rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--border-color);
      gap: 1rem;
      flex-wrap: wrap;
    }
    .author-block {
      display: flex;
      align-items: center;
      gap: 0.85rem;
    }
    .author-avatar {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--primary), #6366f1);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 0.95rem;
    }
    .author-meta {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }
    .author-name {
      font-weight: 700;
      font-size: 1rem;
    }
    .timestamp {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .header-right {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .manage-btns {
      display: flex;
      gap: 0.4rem;
    }
    .announcement-title {
      font-size: 1.35rem;
      margin-bottom: 0.75rem;
      color: var(--text-primary);
    }
    .announcement-content p {
      line-height: 1.65;
      color: var(--text-secondary);
      white-space: pre-line;
      margin: 0;
    }
    /* Modal Styles */
    .modal-backdrop {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.55);
      backdrop-filter: blur(3px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1050;
      padding: 1rem;
    }
    .modal-card {
      width: 100%;
      max-width: 600px;
      padding: 1.75rem;
      max-height: 90vh;
      overflow-y: auto;
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--border-color);
    }
    .modal-header h3 {
      margin: 0;
      font-size: 1.35rem;
    }
    .close-btn {
      background: none;
      border: none;
      font-size: 1.5rem;
      line-height: 1;
      cursor: pointer;
      color: var(--text-muted);
    }
    .form-group {
      margin-bottom: 1.25rem;
    }
    .form-group label {
      display: block;
      margin-bottom: 0.35rem;
      font-weight: 600;
      font-size: 0.9rem;
    }
    .required {
      color: var(--danger, #ef4444);
    }
    .form-check-group {
      margin-top: 1rem;
      padding: 0.85rem;
      background: var(--bg-subtle);
      border-radius: var(--radius-md);
    }
    .checkbox-label {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-weight: 600;
      cursor: pointer;
    }
    .help-text {
      display: block;
      margin-top: 0.35rem;
      color: var(--text-muted);
      font-size: 0.8rem;
    }
    .modal-footer {
      display: flex;
      justify-content: flex-end;
      gap: 0.75rem;
      margin-top: 1.5rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border-color);
    }
    .btn-danger {
      background-color: var(--danger, #ef4444);
      color: #fff;
    }
    .retry-btn {
      margin-left: 0.75rem;
    }
  `],
})
export class CourseAnnouncementsComponent implements OnInit {
  courseId = signal<number>(0);
  course = signal<Course | null>(null);
  announcements = signal<CourseAnnouncement[]>([]);
  filter = signal<'all' | 'published' | 'draft'>('all');

  isLoading = signal<boolean>(true);
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);

  // Modals
  showModal = signal<boolean>(false);
  isEditing = signal<boolean>(false);
  editingId: number | null = null;
  formTitle = '';
  formContent = '';
  formPublished = true;
  isSaving = signal<boolean>(false);

  announcementToDelete = signal<CourseAnnouncement | null>(null);
  isDeleting = signal<boolean>(false);

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    public auth: AuthService,
    private courseService: CourseService,
    private announcementService: AnnouncementService
  ) {}

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      const id = Number(params.get('id'));
      if (id) {
        this.courseId.set(id);
        this.loadCourseInfo();
        this.loadAnnouncements();
      }
    });
  }

  loadCourseInfo(): void {
    this.courseService.getCourse(this.courseId()).subscribe({
      next: (c) => this.course.set(c),
      error: () => {},
    });
  }

  loadAnnouncements(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.announcementService.getCourseAnnouncements(this.courseId()).subscribe({
      next: (list) => {
        this.announcements.set(list);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(err.error?.detail || 'Failed to load announcements.');
        this.isLoading.set(false);
      },
    });
  }

  canManage(): boolean {
    const user = this.auth.currentUser();
    if (!user) return false;
    if (user.role === 'admin') return true;
    const c = this.course();
    return user.role === 'instructor' && c?.instructor_id === user.id;
  }

  setFilter(f: 'all' | 'published' | 'draft'): void {
    this.filter.set(f);
  }

  getCount(status: 'published' | 'draft'): number {
    return this.announcements().filter((a) =>
      status === 'published' ? a.is_published : !a.is_published
    ).length;
  }

  filteredAnnouncements(): CourseAnnouncement[] {
    const f = this.filter();
    const list = this.announcements();
    if (f === 'published') return list.filter((a) => a.is_published);
    if (f === 'draft') return list.filter((a) => !a.is_published);
    return list;
  }

  openCreateModal(): void {
    this.isEditing.set(false);
    this.editingId = null;
    this.formTitle = '';
    this.formContent = '';
    this.formPublished = true;
    this.showModal.set(true);
  }

  openEditModal(ann: CourseAnnouncement): void {
    this.isEditing.set(true);
    this.editingId = ann.id;
    this.formTitle = ann.title;
    this.formContent = ann.content;
    this.formPublished = ann.is_published;
    this.showModal.set(true);
  }

  closeModal(): void {
    this.showModal.set(false);
  }

  saveAnnouncement(): void {
    if (!this.formTitle.trim() || !this.formContent.trim()) return;

    this.isSaving.set(true);
    if (this.isEditing() && this.editingId) {
      this.announcementService
        .updateAnnouncement(this.editingId, {
          title: this.formTitle.trim(),
          content: this.formContent.trim(),
          is_published: this.formPublished,
        })
        .subscribe({
          next: (updated) => {
            this.announcements.update((list) =>
              list.map((a) => (a.id === updated.id ? updated : a))
            );
            this.isSaving.set(false);
            this.closeModal();
            this.showSuccess('Announcement updated successfully.');
          },
          error: (err) => {
            this.isSaving.set(false);
            alert(err.error?.detail || 'Failed to update announcement.');
          },
        });
    } else {
      this.announcementService
        .createAnnouncement(this.courseId(), {
          title: this.formTitle.trim(),
          content: this.formContent.trim(),
          is_published: this.formPublished,
        })
        .subscribe({
          next: (created) => {
            this.announcements.update((list) => [created, ...list]);
            this.isSaving.set(false);
            this.closeModal();
            this.showSuccess(
              this.formPublished
                ? 'Announcement published! Enrolled students have been notified.'
                : 'Draft announcement saved.'
            );
          },
          error: (err) => {
            this.isSaving.set(false);
            alert(err.error?.detail || 'Failed to create announcement.');
          },
        });
    }
  }

  confirmDelete(ann: CourseAnnouncement): void {
    this.announcementToDelete.set(ann);
  }

  cancelDelete(): void {
    this.announcementToDelete.set(null);
  }

  executeDelete(): void {
    const ann = this.announcementToDelete();
    if (!ann) return;

    this.isDeleting.set(true);
    this.announcementService.deleteAnnouncement(ann.id).subscribe({
      next: () => {
        this.announcements.update((list) => list.filter((a) => a.id !== ann.id));
        this.isDeleting.set(false);
        this.announcementToDelete.set(null);
        this.showSuccess('Announcement deleted.');
      },
      error: (err) => {
        this.isDeleting.set(false);
        alert(err.error?.detail || 'Failed to delete announcement.');
      },
    });
  }

  getInitials(name: string): string {
    if (!name) return 'ED';
    return name
      .split(' ')
      .map((n) => n[0])
      .slice(0, 2)
      .join('')
      .toUpperCase();
  }

  private showSuccess(msg: string): void {
    this.successMessage.set(msg);
    setTimeout(() => this.successMessage.set(null), 4000);
  }
}

