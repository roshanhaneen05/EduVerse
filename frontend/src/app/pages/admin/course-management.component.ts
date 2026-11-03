import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AdminService } from '../../core/services/admin.service';
import { AdminCourseItem } from '../../core/models/admin.model';

interface PublishModalState {
  isOpen: boolean;
  course: AdminCourseItem | null;
  title: string;
  message: string;
}

@Component({
  selector: 'app-course-management',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="courses-mgmt-page">
      <div class="container">
        <!-- Header -->
        <div class="page-header">
          <div>
            <a routerLink="/admin/dashboard" class="back-link">← Back to Admin Governance</a>
            <h1>Platform Course Governance</h1>
            <p class="subtitle">Review academic curriculum across all faculty, inspect enrollments, and govern publication states.</p>
          </div>
          <div class="header-actions">
            <a routerLink="/admin/users" class="btn btn-secondary">
              User Directory →
            </a>
          </div>
        </div>

        @if (feedbackMessage) {
          <div class="alert" [ngClass]="isError ? 'alert-danger' : 'alert-success'">
            {{ feedbackMessage }}
          </div>
        }

        <!-- Filter & Search Toolbar -->
        <div class="toolbar card">
          <div class="search-box">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              type="text"
              class="search-input"
              [(ngModel)]="searchQuery"
              (keyup.enter)="onSearch()"
              placeholder="Search course title or description..."
            />
            @if (searchQuery) {
              <button class="clear-search" (click)="clearSearch()">✕</button>
            }
          </div>

          <div class="filter-group">
            <label class="filter-label">Category:</label>
            <select class="form-select filter-select" [(ngModel)]="categoryFilter" (change)="onFilterChange()">
              <option value="">All Categories</option>
              @for (cat of categories; track cat) {
                <option [value]="cat">{{ cat }}</option>
              }
            </select>
          </div>

          <div class="filter-group">
            <label class="filter-label">Status:</label>
            <select class="form-select filter-select" [(ngModel)]="statusFilter" (change)="onFilterChange()">
              <option value="">All Statuses</option>
              <option value="true">Published & Live</option>
              <option value="false">Draft / Unpublished</option>
            </select>
          </div>

          <button (click)="loadCourses()" class="btn btn-primary">
            Filter
          </button>
        </div>

        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading academic course inventory...</span>
          </div>
        } @else if (courses.length === 0) {
          <div class="empty-block card">
            <h3>No courses matched</h3>
            <p>Try resetting the search terms or category/status filters.</p>
            <button (click)="resetFilters()" class="btn btn-secondary">Reset Filters</button>
          </div>
        } @else {
          <div class="card table-wrapper">
            <div class="table-top-bar">
              <span class="count-badge">
                Showing <strong>{{ courses.length }}</strong> of <strong>{{ totalCourses }}</strong> courses (Page {{ currentPage }} of {{ totalPages }})
              </span>
              <div class="page-size-selector">
                <label>Per page:</label>
                <select class="form-select select-sm" [(ngModel)]="pageSize" (change)="onPageSizeChange()">
                  <option [ngValue]="10">10</option>
                  <option [ngValue]="25">25</option>
                  <option [ngValue]="50">50</option>
                </select>
              </div>
            </div>

            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Course Title & Metadata</th>
                    <th>Instructor</th>
                    <th>Curriculum Structure</th>
                    <th>Enrolled</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Governance Actions</th>
                  </tr>
                </thead>
                <tbody>
                  @for (c of courses; track c.id) {
                    <tr>
                      <td>
                        <div class="course-meta-cell">
                          <strong class="course-title-text">{{ c.title }}</strong>
                          <div class="tag-row">
                            <span class="category-tag">{{ c.category }}</span>
                            <span class="badge" [ngClass]="getDifficultyBadge(c.difficulty)">
                              {{ c.difficulty }}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div class="instructor-cell">
                          <strong>{{ c.instructor_name }}</strong>
                          <span class="instructor-email-text">{{ c.instructor_email }}</span>
                        </div>
                      </td>
                      <td>
                        <div class="curriculum-badges">
                          <span class="stat-pill" title="Lessons count">📖 {{ c.lesson_count }} lessons</span>
                          <span class="stat-pill" title="Quizzes count">📝 {{ c.quiz_count }} quizzes</span>
                          <span class="stat-pill" title="Assignments count">📋 {{ c.assignment_count }} tasks</span>
                        </div>
                      </td>
                      <td>
                        <span class="enrollment-pill">
                          <strong>{{ c.enrolled_students_count }}</strong> learners
                        </span>
                      </td>
                      <td>
                        <span class="badge" [ngClass]="c.is_published ? 'badge-success' : 'badge-warning'">
                          {{ c.is_published ? 'Published' : 'Draft' }}
                        </span>
                      </td>
                      <td class="date-cell">
                        {{ c.created_at | date:'mediumDate' }}
                      </td>
                      <td>
                        <div class="action-btn-group">
                          <button
                            (click)="promptTogglePublish(c)"
                            class="btn btn-sm"
                            [ngClass]="c.is_published ? 'btn-secondary' : 'btn-success'"
                          >
                            {{ c.is_published ? 'Unpublish' : 'Publish' }}
                          </button>
                          <a [routerLink]="['/courses', c.id]" class="btn btn-sm btn-outline" target="_blank" title="Preview public view">
                            Preview ↗
                          </a>
                        </div>
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>

            <!-- Pagination Bar -->
            <div class="pagination-bar">
              <button
                class="btn btn-outline btn-sm"
                [disabled]="currentPage <= 1 || isLoading"
                (click)="goToPage(currentPage - 1)"
              >
                ← Previous
              </button>

              <span class="page-indicator">
                Page <strong>{{ currentPage }}</strong> of <strong>{{ totalPages }}</strong>
              </span>

              <button
                class="btn btn-outline btn-sm"
                [disabled]="currentPage >= totalPages || isLoading"
                (click)="goToPage(currentPage + 1)"
              >
                Next →
              </button>
            </div>
          </div>
        }

        <!-- Publish Toggle Confirmation Modal -->
        @if (modal.isOpen && modal.course) {
          <div class="modal-backdrop" (click)="cancelModal()">
            <div class="modal-card card" (click)="$event.stopPropagation()">
              <div class="modal-header">
                <h3>{{ modal.title }}</h3>
                <button (click)="cancelModal()" class="close-modal-btn">✕</button>
              </div>
              <div class="modal-body">
                <p>{{ modal.message }}</p>
                @if (modal.course.is_published) {
                  <div class="warning-box">
                    ⚠️ Unpublishing this course removes it from the public catalog. Existing enrolled students may still access previously enrolled sessions.
                  </div>
                }
              </div>
              <div class="modal-footer">
                <button (click)="cancelModal()" class="btn btn-secondary">
                  Cancel
                </button>
                <button
                  (click)="confirmTogglePublish()"
                  class="btn"
                  [ngClass]="modal.course.is_published ? 'btn-warning' : 'btn-success'"
                >
                  {{ modal.course.is_published ? 'Confirm Unpublish' : 'Confirm Publish' }}
                </button>
              </div>
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .courses-mgmt-page {
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
      margin-bottom: 0.4rem;
      display: inline-block;
      text-decoration: none;
    }
    .back-link:hover {
      color: var(--primary);
    }
    .page-header h1 {
      font-size: 2rem;
      margin-bottom: 0.35rem;
    }
    .subtitle {
      color: var(--text-muted);
      font-size: 1.05rem;
    }
    .toolbar {
      display: flex;
      align-items: center;
      gap: 1.25rem;
      padding: 1.35rem 1.6rem;
      margin-bottom: 2rem;
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 4px 18px rgba(99, 102, 241, 0.05);
      flex-wrap: wrap;
    }
    .search-box {
      flex: 1 1 280px;
      display: flex;
      align-items: center;
      gap: 0.65rem;
      background: #fbfaff;
      border: 1.5px solid #ddd6fe;
      border-radius: 12px;
      padding: 0.6rem 0.95rem;
    }
    .search-input {
      border: none;
      background: transparent;
      outline: none;
      width: 100%;
      font-size: 0.95rem;
      font-family: var(--font-sans);
    }
    .clear-search {
      background: none;
      border: none;
      cursor: pointer;
      color: var(--text-muted);
    }
    .filter-group {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .filter-label {
      font-size: 0.85rem;
      font-weight: 600;
      color: #475569;
    }
    .filter-select {
      width: auto;
      padding: 0.5rem 0.85rem;
      font-size: 0.875rem;
      border-radius: 10px;
      border: 1.5px solid #ddd6fe;
      background-color: #ffffff;
    }
    .table-wrapper {
      padding: 1rem;
      border-radius: var(--radius-lg);
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 8px 25px -4px rgba(99, 102, 241, 0.07);
    }
    .table-top-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 0.75rem;
      margin-bottom: 0.75rem;
      border-bottom: 1px solid var(--border-light);
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .page-size-selector {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .select-sm {
      width: auto;
      padding: 0.25rem 0.5rem;
      font-size: 0.8rem;
    }
    .course-meta-cell {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      max-width: 320px;
    }
    .course-title-text {
      font-size: 0.95rem;
      line-height: 1.3;
    }
    .tag-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
    }
    .category-tag {
      font-size: 0.75rem;
      background: var(--bg-subtle);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      padding: 0.15rem 0.45rem;
      color: var(--text-muted);
    }
    .instructor-cell {
      display: flex;
      flex-direction: column;
      font-size: 0.85rem;
    }
    .instructor-email-text {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .curriculum-badges {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }
    .stat-pill {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .enrollment-pill {
      font-size: 0.85rem;
      color: var(--primary);
    }
    .date-cell {
      font-size: 0.8rem;
      color: var(--text-muted);
      white-space: nowrap;
    }
    .action-btn-group {
      display: flex;
      gap: 0.4rem;
      align-items: center;
    }
    .pagination-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 1rem;
      margin-top: 0.5rem;
      border-top: 1px solid var(--border-light);
    }
    .page-indicator {
      font-size: 0.875rem;
      color: var(--text-muted);
    }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.45);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      padding: 1.5rem;
    }
    .modal-card {
      max-width: 480px;
      width: 100%;
      padding: 1.75rem;
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }
    .modal-header h3 {
      font-size: 1.25rem;
      margin: 0;
    }
    .close-modal-btn {
      background: none;
      border: none;
      font-size: 1.25rem;
      cursor: pointer;
      color: var(--text-muted);
    }
    .warning-box {
      margin-top: 1rem;
      background: #fffbeb;
      border: 1px solid #fef3c7;
      color: #92400e;
      padding: 0.75rem;
      border-radius: var(--radius-md);
      font-size: 0.85rem;
    }
    .modal-footer {
      display: flex;
      justify-content: flex-end;
      gap: 0.75rem;
      margin-top: 1.5rem;
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
export class CourseManagementComponent implements OnInit {
  courses: AdminCourseItem[] = [];
  categories: string[] = [];

  totalCourses = 0;
  currentPage = 1;
  pageSize = 10;
  totalPages = 1;

  isLoading = true;
  searchQuery = '';
  categoryFilter = '';
  statusFilter = '';

  feedbackMessage = '';
  isError = false;

  modal: PublishModalState = {
    isOpen: false,
    course: null,
    title: '',
    message: ''
  };

  constructor(private adminService: AdminService) {}

  ngOnInit(): void {
    this.loadCategories();
    this.loadCourses();
  }

  loadCategories(): void {
    this.adminService.getCourseCategories().subscribe({
      next: (cats) => {
        this.categories = cats;
      },
      error: () => {}
    });
  }

  loadCourses(): void {
    this.isLoading = true;
    let isPubParam: boolean | undefined = undefined;
    if (this.statusFilter === 'true') isPubParam = true;
    if (this.statusFilter === 'false') isPubParam = false;

    this.adminService.getCourses({
      search: this.searchQuery.trim() || undefined,
      category: this.categoryFilter || undefined,
      is_published: isPubParam,
      page: this.currentPage,
      page_size: this.pageSize
    }).subscribe({
      next: (res) => {
        this.courses = res.items;
        this.totalCourses = res.total;
        this.currentPage = res.page;
        this.pageSize = res.page_size;
        this.totalPages = res.total_pages;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to load course directory.';
      }
    });
  }

  onSearch(): void {
    this.currentPage = 1;
    this.loadCourses();
  }

  clearSearch(): void {
    this.searchQuery = '';
    this.currentPage = 1;
    this.loadCourses();
  }

  onFilterChange(): void {
    this.currentPage = 1;
    this.loadCourses();
  }

  onPageSizeChange(): void {
    this.currentPage = 1;
    this.loadCourses();
  }

  goToPage(page: number): void {
    if (page < 1 || page > this.totalPages) return;
    this.currentPage = page;
    this.loadCourses();
  }

  resetFilters(): void {
    this.searchQuery = '';
    this.categoryFilter = '';
    this.statusFilter = '';
    this.currentPage = 1;
    this.loadCourses();
  }

  promptTogglePublish(course: AdminCourseItem): void {
    const nextState = !course.is_published;
    this.modal = {
      isOpen: true,
      course,
      title: nextState ? 'Publish Course' : 'Unpublish Course',
      message: `Are you sure you want to ${nextState ? 'publish' : 'unpublish'} '${course.title}'?`
    };
  }

  confirmTogglePublish(): void {
    if (!this.modal.course) return;
    const course = this.modal.course;

    this.adminService.toggleCoursePublish(course.id).subscribe({
      next: (updated) => {
        course.is_published = updated.is_published;
        this.feedbackMessage = `Course '${course.title}' is now ${updated.is_published ? 'Published' : 'Unpublished (Draft)'}.`;
        this.isError = false;
        this.cancelModal();
      },
      error: (err) => {
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to update course publication state.';
        this.cancelModal();
      }
    });
  }

  cancelModal(): void {
    this.modal = {
      isOpen: false,
      course: null,
      title: '',
      message: ''
    };
  }

  getDifficultyBadge(difficulty: string): string {
    switch (difficulty?.toLowerCase()) {
      case 'beginner': return 'badge-success';
      case 'intermediate': return 'badge-primary';
      case 'advanced': return 'badge-warning';
      default: return 'badge-neutral';
    }
  }
}

