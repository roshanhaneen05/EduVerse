import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { CourseService } from '../../core/services/course.service';
import { DiscussionService } from '../../core/services/discussion.service';
import {
  DiscussionDetail,
  DiscussionListItem,
  DiscussionReply,
} from '../../core/models/discussion.model';
import { Course } from '../../core/models/course.model';

@Component({
  selector: 'app-course-discussions',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="discussions-page">
      <div class="container">
        <!-- Breadcrumb Bar -->
        <div class="nav-breadcrumbs">
          <a [routerLink]="['/courses', courseId()]" class="back-link">
            ← Back to {{ course()?.title || 'Course' }}
          </a>
          @if (activeThread()) {
            <span class="breadcrumb-separator">/</span>
            <button (click)="closeThreadDetail()" class="breadcrumb-btn">All Discussions</button>
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-current">{{ activeThread()?.title }}</span>
          }
        </div>

        @if (!activeThread()) {
          <!-- LIST VIEW -->
          <header class="page-header">
            <div class="header-left">
              <div class="title-with-badge">
                <h1>Course Discussions</h1>
                <span class="badge badge-primary">{{ totalThreads() }} Threads</span>
              </div>
              <p class="subtitle">
                Ask questions, share insights, and discuss concepts with peers and faculty in <strong>{{ course()?.title || 'this course' }}</strong>.
              </p>
            </div>

            <div class="header-actions">
              <button (click)="openCreateModal()" class="btn btn-primary">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
                Start Discussion
              </button>
            </div>
          </header>

          <!-- Search & Filter Toolbar -->
          <div class="toolbar card">
            <div class="search-box">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <input
                type="text"
                class="search-input"
                placeholder="Search topics or content..."
                [(ngModel)]="searchQuery"
                (keyup.enter)="onSearch()"
              />
              @if (searchQuery) {
                <button (click)="clearSearch()" class="clear-btn">&times;</button>
              }
              <button (click)="onSearch()" class="btn btn-sm btn-secondary">Search</button>
            </div>
          </div>

          <!-- Loading State -->
          @if (isLoadingList()) {
            <div class="loading-state card">
              <div class="spinner"></div>
              <p>Loading course discussions...</p>
            </div>
          } @else if (threads().length === 0) {
            <!-- Empty State -->
            <div class="empty-state card">
              <div class="empty-icon">💬</div>
              <h3>No Discussions Found</h3>
              <p>
                @if (searchQuery) {
                  No discussion threads matched "{{ searchQuery }}". Try clearing your search.
                } @else {
                  Be the first to start a conversation in this course! Ask a question or share a study tip.
                }
              </p>
              @if (searchQuery) {
                <button (click)="clearSearch()" class="btn btn-secondary">Clear Search</button>
              } @else {
                <button (click)="openCreateModal()" class="btn btn-primary">Start Discussion</button>
              }
            </div>
          } @else {
            <!-- Threads Feed -->
            <div class="threads-list">
              @for (thread of threads(); track thread.id) {
                <article
                  class="thread-card card"
                  [class.pinned-thread]="thread.is_pinned"
                  [class.deleted-thread]="thread.is_deleted"
                  (click)="viewThread(thread.id)"
                >
                  <div class="thread-main">
                    <div class="thread-header-row">
                      @if (thread.is_pinned) {
                        <span class="badge badge-warning pinned-badge">📌 Pinned Topic</span>
                      }
                      <h2 class="thread-title">{{ thread.title }}</h2>
                    </div>

                    <p class="thread-preview">{{ thread.content }}</p>

                    <div class="thread-meta">
                      <div class="author-info">
                        <span class="avatar-small">{{ getInitials(thread.author?.full_name || 'User') }}</span>
                        <span class="author-name">{{ thread.author?.full_name || 'Community Member' }}</span>
                        <span class="badge badge-xs" [ngClass]="getRoleBadgeClass(thread.author?.role)">
                          {{ thread.author?.role === 'instructor' ? 'Faculty' : (thread.author?.role || 'Member') }}
                        </span>
                      </div>
                      <span class="meta-dot">·</span>
                      <span class="thread-date">{{ thread.created_at | date:'mediumDate' }}</span>
                    </div>
                  </div>

                  <div class="thread-stats">
                    <div class="stat-pill" title="{{ thread.reply_count }} replies">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                      </svg>
                      <span>{{ thread.reply_count }}</span>
                    </div>
                  </div>
                </article>
              }
            </div>

            <!-- Pagination Bar -->
            @if (totalPages() > 1) {
              <div class="pagination-bar">
                <button
                  class="btn btn-sm btn-secondary"
                  [disabled]="currentPage() <= 1"
                  (click)="changePage(currentPage() - 1)"
                >
                  ← Previous
                </button>
                <span class="page-indicator">Page {{ currentPage() }} of {{ totalPages() }}</span>
                <button
                  class="btn btn-sm btn-secondary"
                  [disabled]="currentPage() >= totalPages()"
                  (click)="changePage(currentPage() + 1)"
                >
                  Next →
                </button>
              </div>
            }
          }
        } @else {
          <!-- THREAD DETAIL VIEW -->
          <div class="thread-detail-container">
            <button (click)="closeThreadDetail()" class="btn btn-sm btn-secondary back-btn">
              ← Back to all discussions
            </button>

            @if (isLoadingDetail()) {
              <div class="loading-state card">
                <div class="spinner"></div>
                <p>Loading thread...</p>
              </div>
            } @else if (activeThread()) {
              <!-- Original Post Card -->
              <article class="thread-op card" [class.pinned-thread]="activeThread()?.is_pinned">
                <div class="op-header">
                  <div class="author-block">
                    <div class="author-avatar">
                      {{ getInitials(activeThread()?.author?.full_name || 'User') }}
                    </div>
                    <div class="author-meta">
                      <div class="author-name-row">
                        <span class="author-name">{{ activeThread()?.author?.full_name || 'Community Member' }}</span>
                        <span class="badge" [ngClass]="getRoleBadgeClass(activeThread()?.author?.role)">
                          {{ activeThread()?.author?.role === 'instructor' ? 'Course Instructor' : (activeThread()?.author?.role || 'Student') }}
                        </span>
                        @if (activeThread()?.is_pinned) {
                          <span class="badge badge-warning">📌 Pinned</span>
                        }
                      </div>
                      <span class="timestamp">Posted on {{ activeThread()?.created_at | date:'mediumDate' }} at {{ activeThread()?.created_at | date:'shortTime' }}</span>
                    </div>
                  </div>

                  <!-- Thread Moderation Actions -->
                  <div class="op-actions">
                    @if (canPin()) {
                      <button (click)="togglePinThread()" class="btn btn-sm btn-outline">
                        {{ activeThread()?.is_pinned ? 'Unpin' : 'Pin to Top' }}
                      </button>
                    }
                    @if (canEditThread()) {
                      <button (click)="openEditThreadModal()" class="btn btn-sm btn-secondary">
                        Edit
                      </button>
                    }
                    @if (canDeleteThread()) {
                      <button (click)="confirmDeleteThread()" class="btn btn-sm btn-outline btn-danger">
                        Delete
                      </button>
                    }
                  </div>
                </div>

                <div class="op-body">
                  <h1 class="op-title">{{ activeThread()?.title }}</h1>
                  <div class="op-content">
                    <p>{{ activeThread()?.content }}</p>
                  </div>
                </div>
              </article>

              <!-- Replies Section -->
              <section class="replies-section">
                <div class="replies-header">
                  <h3>Replies ({{ activeThread()?.replies?.length || 0 }})</h3>
                </div>

                <!-- Post Reply Box -->
                @if (!activeThread()?.is_deleted) {
                  <div class="reply-input-box card">
                    @if (replyingToParent()) {
                      <div class="replying-to-banner">
                        <span>Replying to comment #{{ replyingToParent()?.id }} by <strong>{{ replyingToParent()?.author?.full_name }}</strong></span>
                        <button (click)="cancelParentReply()" class="cancel-reply-btn">&times;</button>
                      </div>
                    }

                    <textarea
                      class="form-control reply-textarea"
                      rows="3"
                      placeholder="Share your response or follow-up question..."
                      [(ngModel)]="newReplyContent"
                    ></textarea>

                    <div class="reply-box-actions">
                      <button
                        (click)="postReply()"
                        class="btn btn-primary btn-sm"
                        [disabled]="isPostingReply() || !newReplyContent.trim()"
                      >
                        @if (isPostingReply()) { Posting... } @else { Post Reply }
                      </button>
                    </div>
                  </div>
                }

                <!-- Replies List -->
                @if (activeThread()?.replies?.length === 0) {
                  <div class="empty-replies card">
                    <p>No replies on this topic yet. Be the first to chime in!</p>
                  </div>
                } @else {
                  <div class="replies-list">
                    @for (reply of activeThread()?.replies; track reply.id) {
                      <div
                        class="reply-card card"
                        [class.nested-reply]="reply.parent_reply_id"
                        [class.deleted-reply]="reply.is_deleted"
                      >
                        <div class="reply-header">
                          <div class="author-block">
                            <div class="author-avatar-sm">
                              {{ getInitials(reply.author?.full_name || 'User') }}
                            </div>
                            <div class="author-meta-sm">
                              <span class="author-name-sm">{{ reply.author?.full_name }}</span>
                              <span class="badge badge-xs" [ngClass]="getRoleBadgeClass(reply.author?.role)">
                                {{ reply.author?.role === 'instructor' ? 'Instructor' : (reply.author?.role || 'Member') }}
                              </span>
                              <span class="timestamp-sm">{{ reply.created_at | date:'mediumDate' }}</span>
                            </div>
                          </div>

                          <div class="reply-actions">
                            @if (!reply.is_deleted && !activeThread()?.is_deleted) {
                              <button (click)="replyTo(reply)" class="btn-action" title="Reply to this comment">
                                ↩ Reply
                              </button>
                            }
                            @if (canEditReply(reply)) {
                              <button (click)="openEditReplyModal(reply)" class="btn-action">
                                Edit
                              </button>
                            }
                            @if (canDeleteReply(reply)) {
                              <button (click)="deleteReply(reply)" class="btn-action text-danger">
                                Delete
                              </button>
                            }
                          </div>
                        </div>

                        <div class="reply-body">
                          <p>{{ reply.content }}</p>
                        </div>
                      </div>
                    }
                  </div>
                }
              </section>
            }
          </div>
        }
      </div>

      <!-- New Thread Modal -->
      @if (showCreateModal()) {
        <div class="modal-backdrop" (click)="closeCreateModal()">
          <div class="modal-card card" (click)="$event.stopPropagation()">
            <div class="modal-header">
              <h3>Start a Discussion</h3>
              <button (click)="closeCreateModal()" class="close-btn">&times;</button>
            </div>

            <form (ngSubmit)="submitNewThread()">
              <div class="modal-body">
                <div class="form-group">
                  <label for="threadTitle">Topic Title <span class="required">*</span></label>
                  <input
                    id="threadTitle"
                    type="text"
                    class="form-control"
                    [(ngModel)]="newThreadTitle"
                    name="newThreadTitle"
                    required
                    placeholder="e.g. Question on SQLite WAL mode concurrency"
                  />
                </div>

                <div class="form-group">
                  <label for="threadContent">Opening Post <span class="required">*</span></label>
                  <textarea
                    id="threadContent"
                    class="form-control"
                    rows="6"
                    [(ngModel)]="newThreadContent"
                    name="newThreadContent"
                    required
                    placeholder="Describe your question or observation with details..."
                  ></textarea>
                </div>
              </div>

              <div class="modal-footer">
                <button type="button" (click)="closeCreateModal()" class="btn btn-secondary">
                  Cancel
                </button>
                <button
                  type="submit"
                  class="btn btn-primary"
                  [disabled]="isSavingThread() || !newThreadTitle.trim() || !newThreadContent.trim()"
                >
                  @if (isSavingThread()) { Publishing... } @else { Post Discussion }
                </button>
              </div>
            </form>
          </div>
        </div>
      }

      <!-- Edit Thread Modal -->
      @if (showEditThreadModal()) {
        <div class="modal-backdrop" (click)="closeEditThreadModal()">
          <div class="modal-card card" (click)="$event.stopPropagation()">
            <div class="modal-header">
              <h3>Edit Discussion Thread</h3>
              <button (click)="closeEditThreadModal()" class="close-btn">&times;</button>
            </div>

            <form (ngSubmit)="saveThreadEdit()">
              <div class="modal-body">
                <div class="form-group">
                  <label for="editTitle">Topic Title <span class="required">*</span></label>
                  <input
                    id="editTitle"
                    type="text"
                    class="form-control"
                    [(ngModel)]="editThreadTitle"
                    name="editThreadTitle"
                    required
                  />
                </div>

                <div class="form-group">
                  <label for="editContent">Post Content <span class="required">*</span></label>
                  <textarea
                    id="editContent"
                    class="form-control"
                    rows="6"
                    [(ngModel)]="editThreadContent"
                    name="editThreadContent"
                    required
                  ></textarea>
                </div>
              </div>

              <div class="modal-footer">
                <button type="button" (click)="closeEditThreadModal()" class="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" class="btn btn-primary" [disabled]="!editThreadTitle.trim() || !editThreadContent.trim()">
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      }

      <!-- Edit Reply Modal -->
      @if (showEditReplyModal()) {
        <div class="modal-backdrop" (click)="closeEditReplyModal()">
          <div class="modal-card card" (click)="$event.stopPropagation()">
            <div class="modal-header">
              <h3>Edit Reply</h3>
              <button (click)="closeEditReplyModal()" class="close-btn">&times;</button>
            </div>

            <form (ngSubmit)="saveReplyEdit()">
              <div class="modal-body">
                <div class="form-group">
                  <label for="editReplyBody">Reply Content <span class="required">*</span></label>
                  <textarea
                    id="editReplyBody"
                    class="form-control"
                    rows="4"
                    [(ngModel)]="editReplyContent"
                    name="editReplyContent"
                    required
                  ></textarea>
                </div>
              </div>

              <div class="modal-footer">
                <button type="button" (click)="closeEditReplyModal()" class="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" class="btn btn-primary" [disabled]="!editReplyContent.trim()">
                  Save Reply
                </button>
              </div>
            </form>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .discussions-page {
      padding: 2.5rem 0 4rem;
      min-height: calc(100vh - 70px);
      background-color: var(--bg-surface);
    }
    .nav-breadcrumbs {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 1rem;
      font-size: 0.9rem;
      flex-wrap: wrap;
    }
    .back-link, .breadcrumb-btn {
      color: var(--text-muted);
      text-decoration: none;
      background: none;
      border: none;
      cursor: pointer;
      font-size: 0.9rem;
      padding: 0;
      transition: color 0.2s;
    }
    .back-link:hover, .breadcrumb-btn:hover {
      color: var(--primary);
    }
    .breadcrumb-separator {
      color: var(--border-color);
    }
    .breadcrumb-current {
      color: var(--text-primary);
      font-weight: 600;
      max-width: 300px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1.5rem;
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
    .toolbar {
      padding: 0.85rem 1.25rem;
      margin-bottom: 1.5rem;
    }
    .search-box {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .search-input {
      flex: 1;
      border: none;
      background: transparent;
      outline: none;
      font-size: 0.95rem;
      color: var(--text-primary);
    }
    .clear-btn {
      background: none;
      border: none;
      font-size: 1.2rem;
      cursor: pointer;
      color: var(--text-muted);
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
    .threads-list {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .thread-card {
      padding: 1.25rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1.5rem;
      cursor: pointer;
      transition: all 0.2s;
    }
    .thread-card:hover {
      border-color: var(--primary);
      box-shadow: var(--shadow-sm);
      transform: translateY(-1px);
    }
    .pinned-thread {
      border-left: 4px solid var(--warning, #f59e0b);
    }
    .deleted-thread {
      opacity: 0.65;
    }
    .thread-main {
      flex: 1;
      min-width: 0;
    }
    .thread-header-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.35rem;
    }
    .pinned-badge {
      font-size: 0.75rem;
      font-weight: 700;
    }
    .thread-title {
      font-size: 1.15rem;
      margin: 0;
      color: var(--text-primary);
    }
    .thread-preview {
      color: var(--text-muted);
      font-size: 0.9rem;
      margin: 0 0 0.75rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .thread-meta {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.825rem;
      color: var(--text-muted);
    }
    .author-info {
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .avatar-small {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: var(--primary);
      color: #fff;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 0.65rem;
      font-weight: 700;
    }
    .author-name {
      font-weight: 600;
      color: var(--text-primary);
    }
    .badge-xs {
      font-size: 0.65rem;
      padding: 0.1rem 0.35rem;
    }
    .thread-stats {
      flex-shrink: 0;
    }
    .stat-pill {
      display: flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.4rem 0.75rem;
      background: var(--bg-subtle);
      border-radius: var(--radius-full, 9999px);
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-secondary);
    }
    .pagination-bar {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 1rem;
      margin-top: 2rem;
    }
    .page-indicator {
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--text-muted);
    }
    /* THREAD DETAIL STYLES */
    .thread-detail-container {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }
    .back-btn {
      align-self: flex-start;
    }
    .thread-op {
      padding: 2rem;
    }
    .op-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1.5rem;
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
      width: 46px;
      height: 46px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--primary), #818cf8);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 1rem;
    }
    .author-meta {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }
    .author-name-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .op-actions {
      display: flex;
      gap: 0.4rem;
    }
    .op-title {
      font-size: 1.6rem;
      margin-bottom: 1rem;
      color: var(--text-primary);
    }
    .op-content p {
      line-height: 1.7;
      color: var(--text-secondary);
      font-size: 1.025rem;
      white-space: pre-line;
      margin: 0;
    }
    /* Replies styles */
    .replies-section {
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }
    .reply-input-box {
      padding: 1.25rem;
    }
    .replying-to-banner {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.4rem 0.75rem;
      background: var(--bg-subtle);
      border-radius: var(--radius-sm);
      font-size: 0.85rem;
      margin-bottom: 0.75rem;
    }
    .cancel-reply-btn {
      background: none;
      border: none;
      font-size: 1.1rem;
      cursor: pointer;
      color: var(--text-muted);
    }
    .reply-textarea {
      resize: vertical;
      margin-bottom: 0.75rem;
    }
    .reply-box-actions {
      display: flex;
      justify-content: flex-end;
    }
    .empty-replies {
      padding: 2.5rem;
      text-align: center;
      color: var(--text-muted);
    }
    .replies-list {
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
    }
    .reply-card {
      padding: 1.25rem 1.5rem;
    }
    .nested-reply {
      margin-left: 2rem;
      border-left: 3px solid var(--primary);
      background-color: rgba(99, 102, 241, 0.02);
    }
    .deleted-reply {
      opacity: 0.6;
    }
    .reply-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.65rem;
    }
    .author-avatar-sm {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: var(--bg-subtle);
      border: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 0.75rem;
      color: var(--text-primary);
    }
    .author-meta-sm {
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .author-name-sm {
      font-weight: 600;
      font-size: 0.9rem;
    }
    .timestamp-sm {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .reply-actions {
      display: flex;
      gap: 0.5rem;
    }
    .btn-action {
      background: none;
      border: none;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      color: var(--text-muted);
      padding: 0.2rem 0.4rem;
      transition: color 0.2s;
    }
    .btn-action:hover {
      color: var(--primary);
    }
    .btn-action.text-danger:hover {
      color: var(--danger, #ef4444);
    }
    .reply-body p {
      margin: 0;
      font-size: 0.95rem;
      line-height: 1.6;
      color: var(--text-secondary);
      white-space: pre-line;
    }
    /* Modals */
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
  `],
})
export class CourseDiscussionsComponent implements OnInit {
  courseId = signal<number>(0);
  course = signal<Course | null>(null);

  // List View State
  threads = signal<DiscussionListItem[]>([]);
  totalThreads = signal<number>(0);
  currentPage = signal<number>(1);
  totalPages = signal<number>(1);
  searchQuery = '';
  isLoadingList = signal<boolean>(true);

  // Detail View State
  activeThread = signal<DiscussionDetail | null>(null);
  isLoadingDetail = signal<boolean>(false);

  // Replying State
  newReplyContent = '';
  replyingToParent = signal<DiscussionReply | null>(null);
  isPostingReply = signal<boolean>(false);

  // Create Thread Modal
  showCreateModal = signal<boolean>(false);
  newThreadTitle = '';
  newThreadContent = '';
  isSavingThread = signal<boolean>(false);

  // Edit Thread Modal
  showEditThreadModal = signal<boolean>(false);
  editThreadTitle = '';
  editThreadContent = '';

  // Edit Reply Modal
  showEditReplyModal = signal<boolean>(false);
  editingReply: DiscussionReply | null = null;
  editReplyContent = '';

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    public auth: AuthService,
    private courseService: CourseService,
    private discussionService: DiscussionService
  ) {}

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      const cId = Number(params.get('id'));
      const dId = params.get('discussionId') ? Number(params.get('discussionId')) : null;

      if (cId) {
        this.courseId.set(cId);
        this.loadCourseInfo();
        if (dId) {
          this.viewThread(dId);
        } else {
          this.loadThreads();
        }
      }
    });
  }

  loadCourseInfo(): void {
    this.courseService.getCourse(this.courseId()).subscribe({
      next: (c) => this.course.set(c),
      error: () => {},
    });
  }

  loadThreads(): void {
    this.isLoadingList.set(true);
    this.discussionService
      .getCourseDiscussions(
        this.courseId(),
        this.searchQuery,
        this.currentPage(),
        20
      )
      .subscribe({
        next: (res) => {
          this.threads.set(res.items);
          this.totalThreads.set(res.total);
          this.currentPage.set(res.page);
          this.totalPages.set(res.total_pages);
          this.isLoadingList.set(false);
        },
        error: (err) => {
          this.isLoadingList.set(false);
          alert(err.error?.detail || 'Failed to load discussions.');
        },
      });
  }

  onSearch(): void {
    this.currentPage.set(1);
    this.loadThreads();
  }

  clearSearch(): void {
    this.searchQuery = '';
    this.currentPage.set(1);
    this.loadThreads();
  }

  changePage(page: number): void {
    if (page < 1 || page > this.totalPages()) return;
    this.currentPage.set(page);
    this.loadThreads();
  }

  viewThread(threadId: number): void {
    this.isLoadingDetail.set(true);
    this.discussionService.getDiscussionDetail(threadId).subscribe({
      next: (detail) => {
        this.activeThread.set(detail);
        this.isLoadingDetail.set(false);
      },
      error: (err) => {
        this.isLoadingDetail.set(false);
        alert(err.error?.detail || 'Failed to load discussion thread.');
      },
    });
  }

  closeThreadDetail(): void {
    this.activeThread.set(null);
    this.replyingToParent.set(null);
    this.newReplyContent = '';
    this.loadThreads();
  }

  openCreateModal(): void {
    this.newThreadTitle = '';
    this.newThreadContent = '';
    this.showCreateModal.set(true);
  }

  closeCreateModal(): void {
    this.showCreateModal.set(false);
  }

  submitNewThread(): void {
    if (!this.newThreadTitle.trim() || !this.newThreadContent.trim()) return;

    this.isSavingThread.set(true);
    this.discussionService
      .createDiscussion(this.courseId(), {
        title: this.newThreadTitle.trim(),
        content: this.newThreadContent.trim(),
      })
      .subscribe({
        next: (created) => {
          this.isSavingThread.set(false);
          this.closeCreateModal();
          this.viewThread(created.id);
        },
        error: (err) => {
          this.isSavingThread.set(false);
          alert(err.error?.detail || 'Failed to create discussion.');
        },
      });
  }

  // Thread detail actions
  canPin(): boolean {
    const user = this.auth.currentUser();
    if (!user) return false;
    if (user.role === 'admin') return true;
    const c = this.course();
    return user.role === 'instructor' && c?.instructor_id === user.id;
  }

  togglePinThread(): void {
    const t = this.activeThread();
    if (!t) return;
    this.discussionService.togglePinDiscussion(t.id).subscribe({
      next: (updated) => {
        this.activeThread.update((curr) => curr ? { ...curr, is_pinned: updated.is_pinned } : null);
      },
      error: (err) => alert(err.error?.detail || 'Failed to toggle pin.'),
    });
  }

  canEditThread(): boolean {
    const user = this.auth.currentUser();
    const t = this.activeThread();
    if (!user || !t || t.is_deleted) return false;
    return user.id === t.user_id || user.role === 'admin';
  }

  openEditThreadModal(): void {
    const t = this.activeThread();
    if (!t) return;
    this.editThreadTitle = t.title;
    this.editThreadContent = t.content;
    this.showEditThreadModal.set(true);
  }

  closeEditThreadModal(): void {
    this.showEditThreadModal.set(false);
  }

  saveThreadEdit(): void {
    const t = this.activeThread();
    if (!t || !this.editThreadTitle.trim() || !this.editThreadContent.trim()) return;

    this.discussionService
      .updateDiscussion(t.id, {
        title: this.editThreadTitle.trim(),
        content: this.editThreadContent.trim(),
      })
      .subscribe({
        next: (updated) => {
          this.activeThread.set(updated);
          this.closeEditThreadModal();
        },
        error: (err) => alert(err.error?.detail || 'Failed to update thread.'),
      });
  }

  canDeleteThread(): boolean {
    const user = this.auth.currentUser();
    const t = this.activeThread();
    if (!user || !t || t.is_deleted) return false;
    const c = this.course();
    return user.id === t.user_id || user.role === 'admin' || (user.role === 'instructor' && c?.instructor_id === user.id);
  }

  confirmDeleteThread(): void {
    const t = this.activeThread();
    if (!t) return;
    if (confirm('Are you sure you want to remove this discussion thread?')) {
      this.discussionService.deleteDiscussion(t.id).subscribe({
        next: () => {
          this.closeThreadDetail();
        },
        error: (err) => alert(err.error?.detail || 'Failed to delete discussion.'),
      });
    }
  }

  // Reply actions
  replyTo(reply: DiscussionReply): void {
    this.replyingToParent.set(reply);
  }

  cancelParentReply(): void {
    this.replyingToParent.set(null);
  }

  postReply(): void {
    const t = this.activeThread();
    if (!t || !this.newReplyContent.trim()) return;

    this.isPostingReply.set(true);
    const parentId = this.replyingToParent()?.id || null;

    this.discussionService
      .createReply(t.id, {
        content: this.newReplyContent.trim(),
        parent_reply_id: parentId,
      })
      .subscribe({
        next: (created) => {
          this.isPostingReply.set(false);
          this.newReplyContent = '';
          this.replyingToParent.set(null);
          // Append to replies
          this.activeThread.update((curr) => {
            if (!curr) return null;
            return {
              ...curr,
              replies: [...curr.replies, created],
            };
          });
        },
        error: (err) => {
          this.isPostingReply.set(false);
          alert(err.error?.detail || 'Failed to post reply.');
        },
      });
  }

  canEditReply(reply: DiscussionReply): boolean {
    const user = this.auth.currentUser();
    if (!user || reply.is_deleted) return false;
    return user.id === reply.user_id || user.role === 'admin';
  }

  openEditReplyModal(reply: DiscussionReply): void {
    this.editingReply = reply;
    this.editReplyContent = reply.content;
    this.showEditReplyModal.set(true);
  }

  closeEditReplyModal(): void {
    this.showEditReplyModal.set(false);
    this.editingReply = null;
  }

  saveReplyEdit(): void {
    if (!this.editingReply || !this.editReplyContent.trim()) return;

    this.discussionService
      .updateReply(this.editingReply.id, {
        content: this.editReplyContent.trim(),
      })
      .subscribe({
        next: (updated) => {
          this.activeThread.update((curr) => {
            if (!curr) return null;
            return {
              ...curr,
              replies: curr.replies.map((r) => (r.id === updated.id ? updated : r)),
            };
          });
          this.closeEditReplyModal();
        },
        error: (err) => alert(err.error?.detail || 'Failed to update reply.'),
      });
  }

  canDeleteReply(reply: DiscussionReply): boolean {
    const user = this.auth.currentUser();
    if (!user || reply.is_deleted) return false;
    const c = this.course();
    return user.id === reply.user_id || user.role === 'admin' || (user.role === 'instructor' && c?.instructor_id === user.id);
  }

  deleteReply(reply: DiscussionReply): void {
    if (confirm('Are you sure you want to remove this reply?')) {
      this.discussionService.deleteReply(reply.id).subscribe({
        next: () => {
          this.activeThread.update((curr) => {
            if (!curr) return null;
            return {
              ...curr,
              replies: curr.replies.map((r) =>
                r.id === reply.id
                  ? { ...r, is_deleted: true, content: '[This reply has been deleted by the author or a moderator.]' }
                  : r
              ),
            };
          });
        },
        error: (err) => alert(err.error?.detail || 'Failed to delete reply.'),
      });
    }
  }

  getInitials(name: string): string {
    if (!name) return 'U';
    return name
      .split(' ')
      .map((n) => n[0])
      .slice(0, 2)
      .join('')
      .toUpperCase();
  }

  getRoleBadgeClass(role?: string): string {
    if (role === 'instructor') return 'badge-primary';
    if (role === 'admin') return 'badge-warning';
    return 'badge-neutral';
  }
}

