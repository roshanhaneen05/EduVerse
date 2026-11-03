import { Component, OnInit, signal, effect } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { UserNotification } from '../../core/models/notification.model';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  template: `
    <header class="navbar">
      <div class="nav-container">
        <div class="nav-left">
          <a routerLink="/" class="brand">
            <div class="logo-icon">
              <svg width="22" height="22" viewBox="0 0 32 32" fill="none">
                <path d="M16 4L2 11L16 18L30 11L16 4Z" fill="#ffffff"/>
                <path d="M6 14.5V21C6 24.5 10.5 27.5 16 27.5C21.5 27.5 26 24.5 26 21V14.5" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round"/>
                <path d="M30 11V21M30 21L28 19M30 21L32 19" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <span class="brand-name">Edu<span class="brand-accent">Verse</span></span>
          </a>

          <nav class="nav-links">
            @if (auth.isAuthenticated()) {
              <a routerLink="/courses" routerLinkActive="active" class="nav-link">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                </svg>
                Courses
              </a>
              <a routerLink="/student/my-learning" routerLinkActive="active" class="nav-link">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="3" width="7" height="9"/>
                  <rect x="14" y="3" width="7" height="5"/>
                  <rect x="14" y="12" width="7" height="9"/>
                  <rect x="3" y="16" width="7" height="5"/>
                </svg>
                My Learning
              </a>
              @if (auth.isInstructor()) {
                <a routerLink="/instructor/dashboard" routerLinkActive="active" class="nav-link">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <line x1="19" y1="8" x2="19" y2="14"/>
                    <line x1="22" y1="11" x2="16" y2="11"/>
                  </svg>
                  Instructor Hub
                </a>
              }
              @if (auth.isAdmin()) {
                <a routerLink="/admin/dashboard" routerLinkActive="active" class="nav-link admin-nav">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                    <line x1="8" y1="21" x2="16" y2="21"/>
                    <line x1="12" y1="17" x2="12" y2="21"/>
                  </svg>
                  Admin Panel
                </a>
              }
            }
          </nav>
        </div>

        <div class="nav-right">
          @if (auth.isAuthenticated()) {
            <!-- Notifications Bell Dropdown -->
            <div class="notification-wrapper">
              <button
                (click)="toggleNotifications()"
                class="notification-bell-btn"
                [class.has-unread]="notificationService.unreadCount() > 0"
                title="Notifications"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
                </svg>
                @if (notificationService.unreadCount() > 0) {
                  <span class="unread-pill">{{ notificationService.unreadCount() }}</span>
                }
              </button>

              @if (showNotifications()) {
                <div class="notification-dropdown card" (click)="$event.stopPropagation()">
                  <div class="dropdown-header">
                    <div class="header-title-box">
                      <h4>Notifications</h4>
                      @if (notificationService.unreadCount() > 0) {
                        <span class="badge badge-primary">{{ notificationService.unreadCount() }} unread</span>
                      }
                    </div>
                    @if (notificationService.unreadCount() > 0) {
                      <button (click)="markAllAsRead()" class="mark-all-btn">
                        Mark all read
                      </button>
                    }
                  </div>

                  <div class="dropdown-body">
                    @if (isLoadingNotifications()) {
                      <div class="dropdown-loading">
                        <div class="spinner-sm"></div>
                        <span>Loading notifications...</span>
                      </div>
                    } @else if (notifications().length === 0) {
                      <div class="dropdown-empty">
                        <span class="bell-empty-icon">🔔</span>
                        <p>You're all caught up!</p>
                        <small>No announcements or discussion alerts at this time.</small>
                      </div>
                    } @else {
                      <div class="notification-items-list">
                        @for (n of notifications(); track n.id) {
                          <div
                            class="notification-item"
                            [class.unread]="!n.is_read"
                            (click)="markAsReadAndNavigate(n)"
                          >
                            <div class="notif-icon-col">
                              <span class="notif-type-icon">
                                {{ n.notification_type === 'announcement' ? '📢' : '💬' }}
                              </span>
                            </div>
                            <div class="notif-content-col">
                              <div class="notif-title-row">
                                <span class="notif-title">{{ n.title }}</span>
                                @if (!n.is_read) {
                                  <span class="unread-dot" title="Unread"></span>
                                }
                              </div>
                              <p class="notif-message">{{ n.message }}</p>
                              <span class="notif-time">{{ n.created_at | date:'short' }}</span>
                            </div>
                          </div>
                        }
                      </div>
                    }
                  </div>
                </div>
              }
            </div>

            <div class="user-menu">
              <a routerLink="/profile" class="user-pill" title="View Profile">
                <div class="user-avatar">{{ getInitials(auth.currentUser()?.full_name) }}</div>
                <div class="user-info">
                  <span class="user-name">{{ auth.currentUser()?.full_name }}</span>
                  <span class="badge" [ngClass]="getRoleBadgeClass(auth.currentUser()?.role)">
                    {{ auth.currentUser()?.role }}
                  </span>
                </div>
              </a>
              <button (click)="logout()" class="btn btn-sm btn-secondary logout-btn" title="Sign Out">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                  <polyline points="16 17 21 12 16 7"/>
                  <line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
                <span>Logout</span>
              </button>
            </div>
          } @else {
            <div class="auth-buttons">
              <a routerLink="/login" class="btn btn-sm btn-secondary">Sign In</a>
              <a routerLink="/register" class="btn btn-sm btn-primary">Get Started</a>
            </div>
          }
        </div>
      </div>
    </header>
  `,
  styles: [`
    .navbar {
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-bottom: 1px solid rgba(221, 214, 254, 0.7);
      position: sticky;
      top: 0;
      z-index: 1000;
      box-shadow: 0 4px 20px -2px rgba(99, 102, 241, 0.07);
    }
    .nav-container {
      max-width: 1300px;
      margin: 0 auto;
      padding: 0.85rem 1.75rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .nav-left {
      display: flex;
      align-items: center;
      gap: 2rem;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.65rem;
      text-decoration: none;
    }
    .logo-icon {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
      color: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);
    }
    .brand-name {
      font-size: 1.4rem;
      font-weight: 800;
      color: #1e1b4b;
      letter-spacing: -0.02em;
    }
    .brand-accent {
      color: #4f46e5;
    }
    .nav-links {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .nav-link {
      display: flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0.5rem 0.95rem;
      font-size: 0.925rem;
      font-weight: 600;
      color: #475569;
      border-radius: 10px;
      transition: var(--transition);
      text-decoration: none;
    }
    .nav-link:hover {
      color: #4f46e5;
      background-color: #ede9fe;
    }
    .nav-link.active {
      color: #4f46e5;
      background-color: #ede9fe;
      font-weight: 700;
    }
    .admin-nav.active {
      color: #b45309;
      background-color: #fef3c7;
    }
    .nav-right {
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    .auth-buttons {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    /* Notifications */
    .notification-wrapper {
      position: relative;
    }
    .notification-bell-btn {
      position: relative;
      background: none;
      border: 1px solid var(--border-color);
      width: 38px;
      height: 38px;
      border-radius: var(--radius-full);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      color: var(--text-muted);
      transition: all 0.2s;
    }
    .notification-bell-btn:hover {
      background-color: var(--bg-subtle);
      color: var(--primary);
      border-color: var(--primary);
    }
    .unread-pill {
      position: absolute;
      top: -4px;
      right: -4px;
      background-color: var(--danger, #ef4444);
      color: #ffffff;
      font-size: 0.65rem;
      font-weight: 800;
      min-width: 18px;
      height: 18px;
      border-radius: 9999px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 4px;
      border: 2px solid #ffffff;
    }
    .notification-dropdown {
      position: absolute;
      top: calc(100% + 10px);
      right: 0;
      width: 360px;
      max-width: 90vw;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
      z-index: 1050;
      overflow: hidden;
      padding: 0;
    }
    .dropdown-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.85rem 1rem;
      border-bottom: 1px solid var(--border-color);
      background-color: var(--bg-surface);
    }
    .header-title-box {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .dropdown-header h4 {
      margin: 0;
      font-size: 0.95rem;
      font-weight: 700;
    }
    .mark-all-btn {
      background: none;
      border: none;
      color: var(--primary);
      font-size: 0.75rem;
      font-weight: 600;
      cursor: pointer;
      padding: 0;
    }
    .mark-all-btn:hover {
      text-decoration: underline;
    }
    .dropdown-body {
      max-height: 380px;
      overflow-y: auto;
    }
    .dropdown-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      padding: 2rem;
      color: var(--text-muted);
      font-size: 0.85rem;
    }
    .spinner-sm {
      width: 18px;
      height: 18px;
      border: 2px solid var(--border-color);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .dropdown-empty {
      padding: 2.5rem 1rem;
      text-align: center;
      color: var(--text-muted);
    }
    .bell-empty-icon {
      font-size: 2rem;
      display: block;
      margin-bottom: 0.5rem;
      opacity: 0.5;
    }
    .dropdown-empty p {
      margin: 0 0 0.25rem;
      font-weight: 600;
      color: var(--text-primary);
      font-size: 0.9rem;
    }
    .dropdown-empty small {
      font-size: 0.75rem;
    }
    .notification-items-list {
      display: flex;
      flex-direction: column;
    }
    .notification-item {
      display: flex;
      gap: 0.75rem;
      padding: 0.85rem 1rem;
      border-bottom: 1px solid var(--border-color);
      cursor: pointer;
      transition: background-color 0.15s;
    }
    .notification-item:hover {
      background-color: var(--bg-subtle);
    }
    .notification-item.unread {
      background-color: rgba(99, 102, 241, 0.05);
    }
    .notif-type-icon {
      font-size: 1.15rem;
    }
    .notif-content-col {
      flex: 1;
      min-width: 0;
    }
    .notif-title-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 0.2rem;
    }
    .notif-title {
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--text-primary);
      line-height: 1.25;
    }
    .unread-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background-color: var(--primary);
      margin-left: 0.35rem;
      flex-shrink: 0;
      margin-top: 4px;
    }
    .notif-message {
      font-size: 0.8rem;
      color: var(--text-secondary);
      margin: 0 0 0.35rem;
      line-height: 1.35;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .notif-time {
      font-size: 0.7rem;
      color: var(--text-muted);
    }
    /* User Menu */
    .user-menu {
      display: flex;
      align-items: center;
      gap: 0.875rem;
    }
    .user-pill {
      display: flex;
      align-items: center;
      gap: 0.65rem;
      padding: 0.35rem 0.75rem;
      background-color: var(--bg-subtle);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-full);
      text-decoration: none;
      transition: var(--transition);
    }
    .user-pill:hover {
      background-color: #e2e8f0;
      border-color: #cbd5e1;
    }
    .user-avatar {
      width: 32px;
      height: 32px;
      border-radius: var(--radius-full);
      background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
      color: #ffffff;
      font-weight: 700;
      font-size: 0.8rem;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .user-info {
      display: flex;
      flex-direction: column;
    }
    .user-name {
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--text-main);
      line-height: 1.1;
    }
    .user-pill .badge {
      font-size: 0.65rem;
      padding: 0.1rem 0.4rem;
      align-self: flex-start;
      margin-top: 0.15rem;
    }
    .logout-btn {
      padding: 0.4rem 0.75rem;
    }
  `],
})
export class NavbarComponent implements OnInit {
  showNotifications = signal<boolean>(false);
  notifications = signal<UserNotification[]>([]);
  isLoadingNotifications = signal<boolean>(false);

  constructor(
    public auth: AuthService,
    public notificationService: NotificationService,
    private router: Router
  ) {
    // When authentication status changes, load unread count
    effect(() => {
      if (this.auth.isAuthenticated()) {
        this.notificationService.fetchUnreadCount().subscribe({ error: () => {} });
      }
    });
  }

  ngOnInit(): void {
    if (this.auth.isAuthenticated()) {
      this.notificationService.fetchUnreadCount().subscribe({ error: () => {} });
    }
  }

  toggleNotifications(): void {
    if (this.showNotifications()) {
      this.showNotifications.set(false);
    } else {
      this.showNotifications.set(true);
      this.loadNotifications();
    }
  }

  loadNotifications(): void {
    this.isLoadingNotifications.set(true);
    this.notificationService.getNotifications(false, 20).subscribe({
      next: (items) => {
        this.notifications.set(items);
        this.isLoadingNotifications.set(false);
      },
      error: () => {
        this.isLoadingNotifications.set(false);
      },
    });
  }

  markAsReadAndNavigate(notif: UserNotification): void {
    if (!notif.is_read) {
      this.notificationService.markAsRead(notif.id).subscribe({
        next: () => {
          this.notifications.update((list) =>
            list.map((n) => (n.id === notif.id ? { ...n, is_read: true } : n))
          );
        },
      });
    }

    this.showNotifications.set(false);

    if (notif.link_url) {
      this.router.navigateByUrl(notif.link_url);
    }
  }

  markAllAsRead(): void {
    this.notificationService.markAllAsRead().subscribe({
      next: () => {
        this.notifications.update((list) =>
          list.map((n) => ({ ...n, is_read: true }))
        );
      },
    });
  }

  getInitials(name?: string): string {
    if (!name) return 'U';
    return name
      .split(' ')
      .map((part) => part.charAt(0).toUpperCase())
      .slice(0, 2)
      .join('');
  }

  getRoleBadgeClass(role?: string): string {
    switch (role) {
      case 'admin':
        return 'badge-danger';
      case 'instructor':
        return 'badge-warning';
      default:
        return 'badge-primary';
    }
  }

  logout(): void {
    this.auth.logout().subscribe();
  }
}
