import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AdminService } from '../../core/services/admin.service';
import { User } from '../../core/models/user.model';
import { AuthService } from '../../core/services/auth.service';

interface ConfirmationModalState {
  isOpen: boolean;
  type: 'status' | 'role';
  user: User | null;
  targetRole?: string;
  targetStatus?: boolean;
  title: string;
  message: string;
}

@Component({
  selector: 'app-user-management',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="users-page">
      <div class="container">
        <!-- Header -->
        <div class="page-header">
          <div>
            <a routerLink="/admin/dashboard" class="back-link">← Back to Admin Governance</a>
            <h1>Platform User Directory</h1>
            <p class="subtitle">Search, inspect, promote roles, and govern access controls across all EduVerse accounts.</p>
          </div>
          <div class="header-actions">
            <a routerLink="/admin/courses" class="btn btn-secondary">
              Course Management →
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
              placeholder="Search user by name or email..."
            />
            @if (searchQuery) {
              <button class="clear-search" (click)="clearSearch()">✕</button>
            }
          </div>

          <div class="filter-group">
            <label class="filter-label">Role:</label>
            <select class="form-select filter-select" [(ngModel)]="roleFilter" (change)="onFilterChange()">
              <option value="">All Roles</option>
              <option value="student">Student</option>
              <option value="instructor">Instructor</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <div class="filter-group">
            <label class="filter-label">Status:</label>
            <select class="form-select filter-select" [(ngModel)]="statusFilter" (change)="onFilterChange()">
              <option value="">All Statuses</option>
              <option value="true">Active Only</option>
              <option value="false">Deactivated Only</option>
            </select>
          </div>

          <button (click)="loadUsers()" class="btn btn-primary">
            Filter
          </button>
        </div>

        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading user directory...</span>
          </div>
        } @else if (users.length === 0) {
          <div class="empty-block card">
            <h3>No users matched</h3>
            <p>Try resetting the search terms or role/status filters.</p>
            <button (click)="resetFilters()" class="btn btn-secondary">Reset Filters</button>
          </div>
        } @else {
          <div class="card table-wrapper">
            <div class="table-top-bar">
              <span class="user-count-badge">
                Showing <strong>{{ users.length }}</strong> of <strong>{{ totalUsers }}</strong> accounts (Page {{ currentPage }} of {{ totalPages }})
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
                    <th>User Profile</th>
                    <th>Email Address</th>
                    <th>Registered</th>
                    <th>Assigned Role</th>
                    <th>Account Status</th>
                    <th>Governance Actions</th>
                  </tr>
                </thead>
                <tbody>
                  @for (u of users; track u.id) {
                    <tr [class.self-row]="u.id === auth.currentUser()?.id">
                      <td>
                        <div class="user-cell">
                          <div class="user-avatar-sm">{{ getInitials(u.full_name) }}</div>
                          <div class="user-cell-info">
                            <strong>{{ u.full_name }}</strong>
                            @if (u.id === auth.currentUser()?.id) {
                              <span class="self-tag">(You / Current Session)</span>
                            }
                          </div>
                        </div>
                      </td>
                      <td>
                        <span class="user-email-text">{{ u.email }}</span>
                      </td>
                      <td>{{ u.created_at | date:'mediumDate' }}</td>
                      <td>
                        <select
                          class="form-select role-select"
                          [ngModel]="u.role"
                          (ngModelChange)="promptRoleChange(u, $event)"
                          [disabled]="u.id === auth.currentUser()?.id"
                          [title]="u.id === auth.currentUser()?.id ? 'Administrators cannot demote their own account' : 'Modify role'"
                        >
                          <option value="student">Student</option>
                          <option value="instructor">Instructor</option>
                          <option value="admin">Admin</option>
                        </select>
                      </td>
                      <td>
                        <span class="badge" [ngClass]="u.is_active ? 'badge-success' : 'badge-danger'">
                          {{ u.is_active ? 'Active' : 'Deactivated' }}
                        </span>
                      </td>
                      <td>
                        <button
                          (click)="promptStatusToggle(u)"
                          class="btn btn-sm"
                          [ngClass]="u.is_active ? 'btn-danger' : 'btn-secondary'"
                          [disabled]="u.id === auth.currentUser()?.id"
                          [title]="u.id === auth.currentUser()?.id ? 'Administrators cannot deactivate their own account' : 'Toggle access'"
                        >
                          {{ u.is_active ? 'Deactivate' : 'Activate' }}
                        </button>
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

        <!-- Confirmation Modal -->
        @if (modal.isOpen) {
          <div class="modal-backdrop" (click)="cancelModal()">
            <div class="modal-card card" (click)="$event.stopPropagation()">
              <div class="modal-header">
                <h3>{{ modal.title }}</h3>
                <button (click)="cancelModal()" class="close-modal-btn">✕</button>
              </div>
              <div class="modal-body">
                <p>{{ modal.message }}</p>
                @if (modal.type === 'status' && modal.targetStatus === false) {
                  <div class="warning-box">
                    ⚠️ Deactivating this account will immediately revoke all access and prevent the user from logging in.
                  </div>
                }
              </div>
              <div class="modal-footer">
                <button (click)="cancelModal()" class="btn btn-secondary">
                  Cancel
                </button>
                <button
                  (click)="confirmModalAction()"
                  class="btn"
                  [ngClass]="modal.type === 'status' && modal.targetStatus === false ? 'btn-danger' : 'btn-primary'"
                >
                  Confirm Action
                </button>
              </div>
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .users-page {
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
      flex: 1 1 260px;
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
    .user-cell {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .user-avatar-sm {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--primary) 0%, #3b82f6 100%);
      color: #ffffff;
      font-weight: 700;
      font-size: 0.8rem;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .user-cell-info {
      display: flex;
      flex-direction: column;
    }
    .self-tag {
      font-size: 0.75rem;
      color: var(--primary);
      font-weight: 700;
    }
    .self-row {
      background-color: rgba(99, 102, 241, 0.04);
    }
    .user-email-text {
      font-family: monospace;
      font-size: 0.85rem;
    }
    .role-select {
      width: 130px;
      padding: 0.35rem 0.6rem;
      font-size: 0.85rem;
      font-weight: 600;
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
      background: #fef2f2;
      border: 1px solid #fecaca;
      color: #991b1b;
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
export class UserManagementComponent implements OnInit {
  users: User[] = [];
  totalUsers = 0;
  currentPage = 1;
  pageSize = 10;
  totalPages = 1;

  isLoading = true;
  searchQuery = '';
  roleFilter = '';
  statusFilter = '';

  feedbackMessage = '';
  isError = false;

  modal: ConfirmationModalState = {
    isOpen: false,
    type: 'status',
    user: null,
    title: '',
    message: ''
  };

  constructor(
    private adminService: AdminService,
    public auth: AuthService
  ) {}

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.isLoading = true;
    let isActiveParam: boolean | undefined = undefined;
    if (this.statusFilter === 'true') isActiveParam = true;
    if (this.statusFilter === 'false') isActiveParam = false;

    this.adminService.getUsers({
      search: this.searchQuery.trim() || undefined,
      role: this.roleFilter || undefined,
      is_active: isActiveParam,
      page: this.currentPage,
      page_size: this.pageSize
    }).subscribe({
      next: (res) => {
        this.users = res.items;
        this.totalUsers = res.total;
        this.currentPage = res.page;
        this.pageSize = res.page_size;
        this.totalPages = res.total_pages;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.isError = true;
        this.feedbackMessage = err.error?.detail || 'Failed to load user directory.';
      }
    });
  }

  onSearch(): void {
    this.currentPage = 1;
    this.loadUsers();
  }

  clearSearch(): void {
    this.searchQuery = '';
    this.currentPage = 1;
    this.loadUsers();
  }

  onFilterChange(): void {
    this.currentPage = 1;
    this.loadUsers();
  }

  onPageSizeChange(): void {
    this.currentPage = 1;
    this.loadUsers();
  }

  goToPage(page: number): void {
    if (page < 1 || page > this.totalPages) return;
    this.currentPage = page;
    this.loadUsers();
  }

  resetFilters(): void {
    this.searchQuery = '';
    this.roleFilter = '';
    this.statusFilter = '';
    this.currentPage = 1;
    this.loadUsers();
  }

  promptRoleChange(user: User, newRole: string): void {
    if (user.role === newRole) return;
    if (user.id === this.auth.currentUser()?.id) {
      this.isError = true;
      this.feedbackMessage = 'Administrators cannot change their own role.';
      return;
    }

    this.modal = {
      isOpen: true,
      type: 'role',
      user,
      targetRole: newRole,
      title: 'Confirm Role Promotion / Change',
      message: `Are you sure you want to change ${user.full_name}'s role from '${user.role}' to '${newRole}'?`
    };
  }

  promptStatusToggle(user: User): void {
    if (user.id === this.auth.currentUser()?.id) {
      this.isError = true;
      this.feedbackMessage = 'Administrators cannot deactivate their own account.';
      return;
    }

    const nextStatus = !user.is_active;
    this.modal = {
      isOpen: true,
      type: 'status',
      user,
      targetStatus: nextStatus,
      title: nextStatus ? 'Reactivate User Account' : 'Deactivate User Account',
      message: `Are you sure you want to ${nextStatus ? 'reactivate' : 'deactivate'} the account of ${user.full_name} (${user.email})?`
    };
  }

  confirmModalAction(): void {
    if (!this.modal.user) return;
    const user = this.modal.user;

    if (this.modal.type === 'role' && this.modal.targetRole) {
      const role = this.modal.targetRole;
      this.adminService.updateUser(user.id, { role }).subscribe({
        next: (updated) => {
          user.role = updated.role;
          this.feedbackMessage = `User ${user.full_name} role updated to '${updated.role}'.`;
          this.isError = false;
          this.cancelModal();
        },
        error: (err) => {
          this.isError = true;
          this.feedbackMessage = err.error?.detail || 'Failed to update user role.';
          this.cancelModal();
        }
      });
    } else if (this.modal.type === 'status' && this.modal.targetStatus !== undefined) {
      const is_active = this.modal.targetStatus;
      this.adminService.updateUser(user.id, { is_active }).subscribe({
        next: (updated) => {
          user.is_active = updated.is_active;
          this.feedbackMessage = `Account for ${user.full_name} is now ${updated.is_active ? 'Active' : 'Deactivated'}.`;
          this.isError = false;
          this.cancelModal();
        },
        error: (err) => {
          this.isError = true;
          this.feedbackMessage = err.error?.detail || 'Failed to update user status.';
          this.cancelModal();
        }
      });
    }
  }

  cancelModal(): void {
    this.modal = {
      isOpen: false,
      type: 'status',
      user: null,
      title: '',
      message: ''
    };
  }

  getInitials(name: string): string {
    return name
      .split(' ')
      .map(n => n.charAt(0).toUpperCase())
      .slice(0, 2)
      .join('');
  }
}
