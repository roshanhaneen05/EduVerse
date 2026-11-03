import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AdminService } from '../../core/services/admin.service';
import { PlatformStats } from '../../core/models/admin.model';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="admin-page">
      <div class="container">
        <!-- Page Header -->
        <div class="page-header">
          <div>
            <div class="admin-tag">
              <span class="pulse-dot"></span>
              <span>Administrator Oversight</span>
            </div>
            <h1>Platform Governance & Telemetry</h1>
            <p class="subtitle">Platform-wide analytics, user directory governance, and curriculum oversight.</p>
          </div>
          <div class="header-actions">
            <a routerLink="/admin/users" class="btn btn-secondary">
              User Directory →
            </a>
            <a routerLink="/admin/courses" class="btn btn-primary">
              Course Management →
            </a>
          </div>
        </div>

        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Aggregating real-time platform telemetry...</span>
          </div>
        } @else if (errorMessage) {
          <div class="card error-card">
            <h3>Unable to load platform statistics</h3>
            <p>{{ errorMessage }}</p>
            <button (click)="loadStats()" class="btn btn-primary">Try Again</button>
          </div>
        } @else if (stats) {
          <!-- Primary Telemetry Grid -->
          <div class="stats-grid">
            <div class="stat-card card">
              <div class="stat-icon icon-indigo">👥</div>
              <div class="stat-info">
                <span class="stat-val">{{ stats.total_users }}</span>
                <span class="stat-label">Total Users</span>
                <span class="stat-sub">{{ stats.total_admins }} platform admins</span>
              </div>
            </div>

            <div class="stat-card card">
              <div class="stat-icon icon-blue">🎓</div>
              <div class="stat-info">
                <span class="stat-val">{{ stats.total_students }}</span>
                <span class="stat-label">Learners</span>
                <span class="stat-sub">{{ stats.total_enrollments }} total enrollments</span>
              </div>
            </div>

            <div class="stat-card card">
              <div class="stat-icon icon-amber">👨‍🏫</div>
              <div class="stat-info">
                <span class="stat-val">{{ stats.total_instructors }}</span>
                <span class="stat-label">Instructors</span>
                <span class="stat-sub">{{ stats.total_courses }} authored courses</span>
              </div>
            </div>

            <div class="stat-card card">
              <div class="stat-icon icon-emerald">📚</div>
              <div class="stat-info">
                <span class="stat-val">{{ stats.published_courses }}</span>
                <span class="stat-label">Live Courses</span>
                <span class="stat-sub">{{ stats.total_courses - stats.published_courses }} unpublished drafts</span>
              </div>
            </div>
          </div>

          <!-- Secondary Metrics Cards -->
          <div class="secondary-grid">
            <div class="card metric-panel">
              <div class="panel-header">
                <h3>Academic Curriculum</h3>
                <span class="badge badge-primary">Catalog</span>
              </div>
              <div class="metric-row">
                <span class="label">Total Courses:</span>
                <span class="val font-semibold">{{ stats.total_courses }}</span>
              </div>
              <div class="metric-row">
                <span class="label">Published & Live:</span>
                <span class="val text-success font-semibold">{{ stats.published_courses }}</span>
              </div>
              <div class="metric-row">
                <span class="label">Total Enrollments:</span>
                <span class="val">{{ stats.total_enrollments }}</span>
              </div>
              <div class="metric-row">
                <span class="label">Course Materials:</span>
                <span class="val">{{ stats.total_learning_materials }} files uploaded</span>
              </div>
            </div>

            <div class="card metric-panel">
              <div class="panel-header">
                <h3>Examinations & Tasks</h3>
                <span class="badge badge-success">Evaluations</span>
              </div>
              <div class="metric-row">
                <span class="label">Assessment Quizzes:</span>
                <span class="val font-semibold">{{ stats.total_quiz_attempts }} total attempts</span>
              </div>
              <div class="metric-row">
                <span class="label">Average Pass Rate:</span>
                <span class="val highlight-green font-semibold">{{ stats.average_quiz_pass_rate }}%</span>
              </div>
              <div class="metric-row">
                <span class="label">Course Assignments:</span>
                <span class="val">{{ stats.total_assignments }} active tasks</span>
              </div>
              <div class="metric-row">
                <span class="label">Total Submissions:</span>
                <span class="val">{{ stats.total_submissions }} submitted</span>
              </div>
            </div>

            <div class="card metric-panel">
              <div class="panel-header">
                <h3>Platform Infrastructure</h3>
                <span class="badge badge-neutral">Security</span>
              </div>
              <div class="metric-row">
                <span class="label">Backend Runtime:</span>
                <span class="val">FastAPI + Python 3.13</span>
              </div>
              <div class="metric-row">
                <span class="label">Cryptography:</span>
                <span class="val">Argon2id + PyJWT</span>
              </div>
              <div class="metric-row">
                <span class="label">Database:</span>
                <span class="val">SQLite (FK Enforced)</span>
              </div>
              <div class="metric-row">
                <span class="label">Authorization:</span>
                <span class="val text-success">Strict RBAC</span>
              </div>
            </div>
          </div>

          <!-- Quick Governance Action Banners -->
          <div class="banners-grid">
            <div class="action-banner card">
              <div class="banner-text">
                <h3>User Governance</h3>
                <p>Inspect registered accounts, promote students to instructors, or deactivate flagged credentials.</p>
              </div>
              <a routerLink="/admin/users" class="btn btn-primary">
                Open User Directory →
              </a>
            </div>

            <div class="action-banner card">
              <div class="banner-text">
                <h3>Curriculum Governance</h3>
                <p>Review all courses across the institution, inspect enrollment metrics, and publish/unpublish offerings.</p>
              </div>
              <a routerLink="/admin/courses" class="btn btn-primary">
                Open Course Catalog →
              </a>
            </div>
          </div>

          <!-- Real Recent Platform Activity Section -->
          <div class="section-block">
            <div class="section-header">
              <div>
                <h2>Recent Platform Activity</h2>
                <p class="section-sub">Live audit trail of platform events, registrations, course creations, and completions.</p>
              </div>
              <span class="badge badge-neutral">{{ stats.recent_activities.length }} Events</span>
            </div>

            @if (stats.recent_activities.length === 0) {
              <div class="empty-block card">
                <h3>No recent activity records</h3>
                <p>Platform events will appear here as users register, enroll, and take courses.</p>
              </div>
            } @else {
              <div class="table-container card">
                <table>
                  <thead>
                    <tr>
                      <th>Event</th>
                      <th>Description</th>
                      <th>User / Entity</th>
                      <th>Timestamp</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (act of stats.recent_activities; track act.timestamp + act.title) {
                      <tr>
                        <td>
                          <div class="activity-type-cell">
                            <span class="badge" [ngClass]="getActivityBadge(act.activity_type)">
                              {{ formatActivityType(act.activity_type) }}
                            </span>
                            <span class="activity-title">{{ act.title }}</span>
                          </div>
                        </td>
                        <td>
                          <span class="activity-desc">{{ act.description }}</span>
                        </td>
                        <td>
                          @if (act.user_name) {
                            <div class="user-meta-pill">
                              <strong>{{ act.user_name }}</strong>
                              @if (act.user_email) {
                                <span class="email-sub">{{ act.user_email }}</span>
                              }
                            </div>
                          } @else {
                            <span class="text-muted">—</span>
                          }
                        </td>
                        <td class="timestamp-cell">
                          {{ act.timestamp | date:'medium' }}
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
    .admin-page {
      padding: 2.5rem 0 4rem 0;
      min-height: calc(100vh - 120px);
    }
    .admin-tag {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background: #ede9fe;
      color: #6d28d9;
      border: 1px solid #ddd6fe;
      padding: 0.25rem 0.85rem;
      border-radius: var(--radius-full);
      font-size: 0.8rem;
      font-weight: 700;
      margin-bottom: 0.75rem;
      box-shadow: 0 2px 6px rgba(109, 40, 217, 0.08);
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      background-color: #7c3aed;
      border-radius: 50%;
    }
    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      flex-wrap: wrap;
      gap: 1.25rem;
    }
    .page-header h1 {
      font-size: 2.25rem;
      color: #0f172a;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 0.35rem;
    }
    .subtitle {
      color: var(--text-muted);
      font-size: 1.05rem;
    }
    .header-actions {
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.35rem;
      margin-bottom: 2.25rem;
    }
    .stat-card {
      display: flex;
      align-items: center;
      gap: 1.25rem;
      padding: 1.5rem;
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 6px 20px -3px rgba(99, 102, 241, 0.06);
    }
    .stat-icon {
      font-size: 1.8rem;
      width: 52px;
      height: 52px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .icon-indigo { background: #ede9fe; }
    .icon-blue { background: #e0e7ff; }
    .icon-amber { background: #fef3c7; }
    .icon-emerald { background: #dcfce7; }
    .stat-info {
      display: flex;
      flex-direction: column;
    }
    .stat-val {
      font-size: 1.85rem;
      font-weight: 800;
      color: #0f172a;
      line-height: 1.1;
    }
    .stat-label {
      color: var(--text-muted);
      font-size: 0.85rem;
      font-weight: 600;
      margin-top: 0.2rem;
    }
    .stat-sub {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 0.2rem;
    }
    .secondary-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 1.35rem;
      margin-bottom: 2.25rem;
    }
    .metric-panel {
      padding: 1.6rem;
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 6px 20px -3px rgba(99, 102, 241, 0.06);
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--border-light);
    }
    .panel-header h3 {
      font-size: 1.1rem;
      margin: 0;
    }
    .metric-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.6rem 0;
      font-size: 0.9rem;
      border-bottom: 1px dashed var(--border-light);
    }
    .metric-row:last-child {
      border-bottom: none;
    }
    .metric-row .label {
      color: var(--text-muted);
    }
    .highlight-green {
      color: var(--success);
    }
    .banners-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2.5rem;
    }
    .action-banner {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1.5rem;
      gap: 1.25rem;
      flex-wrap: wrap;
    }
    .banner-text h3 {
      font-size: 1.15rem;
      margin-bottom: 0.25rem;
    }
    .banner-text p {
      color: var(--text-muted);
      font-size: 0.875rem;
      margin: 0;
    }
    .section-block {
      margin-top: 2rem;
    }
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 1rem;
      flex-wrap: wrap;
      gap: 0.75rem;
    }
    .section-header h2 {
      font-size: 1.35rem;
      margin-bottom: 0.2rem;
    }
    .section-sub {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin: 0;
    }
    .activity-type-cell {
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }
    .activity-title {
      font-weight: 600;
      font-size: 0.9rem;
    }
    .activity-desc {
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .user-meta-pill {
      display: flex;
      flex-direction: column;
      font-size: 0.85rem;
    }
    .email-sub {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .timestamp-cell {
      font-size: 0.8rem;
      color: var(--text-muted);
      white-space: nowrap;
    }
    .empty-block {
      text-align: center;
      padding: 3rem;
    }
    .error-card {
      text-align: center;
      padding: 3rem;
      border: 1px solid #fecaca;
      background: #fef2f2;
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
export class AdminDashboardComponent implements OnInit {
  stats: PlatformStats | null = null;
  isLoading = true;
  errorMessage = '';

  constructor(private adminService: AdminService) {}

  ngOnInit(): void {
    this.loadStats();
  }

  loadStats(): void {
    this.isLoading = true;
    this.errorMessage = '';

    this.adminService.getStats().subscribe({
      next: (data) => {
        this.stats = data;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || 'Failed to aggregate platform telemetry.';
      }
    });
  }

  formatActivityType(type: string): string {
    switch (type) {
      case 'user_registered': return 'User';
      case 'course_enrolled': return 'Enrollment';
      case 'course_created': return 'Course';
      case 'quiz_attempt': return 'Assessment';
      default: return 'Event';
    }
  }

  getActivityBadge(type: string): string {
    switch (type) {
      case 'user_registered': return 'badge-primary';
      case 'course_enrolled': return 'badge-success';
      case 'course_created': return 'badge-secondary';
      case 'quiz_attempt': return 'badge-warning';
      default: return 'badge-neutral';
    }
  }
}
