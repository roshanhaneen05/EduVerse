import { Component, OnInit, ElementRef, ViewChild, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AIService } from '../../core/services/ai.service';
import { AuthService } from '../../core/services/auth.service';
import { StudentService } from '../../core/services/student.service';
import { CourseService } from '../../core/services/course.service';
import {
  AIMessage,
  AIConversationSummary,
  StudyRecommendationsResponse,
  StudyRecommendationItem
} from '../../core/models/ai.model';
import { EnrolledCourseDetail } from '../../core/models/student.model';
import { LessonSummary } from '../../core/models/course.model';

@Component({
  selector: 'app-ai-assistant',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="assistant-page">
      <div class="assistant-container">
        <!-- Sidebar: Conversation Threads & Controls -->
        <aside class="threads-sidebar card">
          <div class="sidebar-top">
            <button (click)="startNewChat()" class="btn btn-primary btn-block">
              + New Conversation
            </button>
          </div>

          <div class="view-switch-group">
            <button
              type="button"
              class="switch-tab-btn"
              [class.active]="activeTab === 'chat'"
              (click)="activeTab = 'chat'"
            >
              💬 AI Tutor Chat
            </button>
            <button
              type="button"
              class="switch-tab-btn"
              [class.active]="activeTab === 'recommendations'"
              (click)="switchToRecommendations()"
            >
              🎯 Study Plans
              @if (recommendationsData && recommendationsData.total_recommendations > 0) {
                <span class="badge-count">{{ recommendationsData.total_recommendations }}</span>
              }
            </button>
          </div>

          @if (activeTab === 'chat') {
            <div class="threads-list">
              <span class="threads-label">Past Discussions</span>
              @if (loadingThreads) {
                <div class="thread-loader">Loading threads...</div>
              } @else if (threads.length === 0) {
                <p class="no-threads">No saved discussions yet. Ask a question to begin!</p>
              } @else {
                @for (t of threads; track t.id) {
                  <div
                    class="thread-item"
                    [class.active]="currentConversationId === t.id"
                    (click)="loadConversation(t.id)"
                  >
                    <span class="thread-title">{{ t.title }}</span>
                    <button (click)="deleteThread($event, t.id)" class="delete-thread-btn" title="Delete conversation">
                      ✕
                    </button>
                  </div>
                }
              }
            </div>
          } @else {
            <div class="sidebar-info-box">
              <h4>Progress-Driven Recommendations</h4>
              <p>Advisory learning insights generated directly from your quiz attempts, lesson progress, and assignments.</p>
            </div>
          }
        </aside>

        <!-- Main Workspace Area -->
        <main class="chat-main card">
          <!-- Chat Header -->
          <div class="chat-header">
            <div class="header-left-col">
              <div class="bot-badge">
                <div class="bot-icon">✨</div>
                <div class="bot-meta">
                  <h3>EduVerse AI Learning Tutor</h3>
                  <span class="status-online">
                    <span class="dot"></span>
                    {{ activeTab === 'chat' ? 'Intelligent Pedagogical Assistant' : 'Personalized Progress Analysis' }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Course / Lesson Context Selector (Visible in Chat) -->
            @if (activeTab === 'chat') {
              <div class="context-controls">
                <div class="context-field">
                  <label for="courseSelect">Grounding Course:</label>
                  <select
                    id="courseSelect"
                    class="context-select"
                    [ngModel]="selectedCourseId"
                    (ngModelChange)="onCourseSelected($event)"
                  >
                    <option [ngValue]="null">🌐 All Subjects (General)</option>
                    @for (c of enrolledCourses; track c.course_id) {
                      <option [ngValue]="c.course_id">📚 {{ c.course_title }}</option>
                    }
                  </select>
                </div>

                @if (selectedCourseId && courseLessons.length > 0) {
                  <div class="context-field">
                    <label for="lessonSelect">Lesson Scope:</label>
                    <select
                      id="lessonSelect"
                      class="context-select"
                      [ngModel]="selectedLessonId"
                      (ngModelChange)="selectedLessonId = $event"
                    >
                      <option [ngValue]="null">Whole Course Syllabus</option>
                      @for (l of courseLessons; track l.id) {
                        <option [ngValue]="l.id">📖 L{{ l.order_index }}: {{ l.title }}</option>
                      }
                    </select>
                  </div>
                }

                @if (selectedCourseId) {
                  <button type="button" class="btn-clear-context" (click)="clearContext()" title="Reset to general AI">
                    ✕
                  </button>
                }
              </div>
            }
          </div>

          <!-- TAB 1: Chat Stream -->
          @if (activeTab === 'chat') {
            <!-- Active Context Banner -->
            @if (selectedCourseId) {
              <div class="active-context-banner">
                <span class="context-pill">
                  🌿 <strong>Course Grounding Active:</strong> {{ getSelectedCourseTitle() }}
                  @if (selectedLessonId) {
                    <span> › {{ getSelectedLessonTitle() }}</span>
                  }
                </span>
                <span class="context-hint">Questions will be grounded in this syllabus.</span>
              </div>
            }

            <div class="messages-stream" #messagesContainer>
              @if (messages.length === 0) {
                <div class="empty-chat-welcome">
                  <div class="welcome-icon">🎓</div>
                  <h2>How can I assist your studies today?</h2>
                  <p>
                    @if (selectedCourseId) {
                      Ask specific questions about <strong>{{ getSelectedCourseTitle() }}</strong> or request code examples and concept breakdowns.
                    } @else {
                      Ask questions about course lessons, software design patterns, or test yourself with quick practice drills.
                    }
                  </p>

                  <div class="prompt-chips">
                    @for (prompt of getActivePromptChips(); track prompt) {
                      <button type="button" (click)="usePrompt(prompt)" class="prompt-chip">
                        {{ prompt }}
                      </button>
                    }
                  </div>
                </div>
              } @else {
                @for (msg of messages; track $index) {
                  <div class="message-row" [class.user-row]="msg.role === 'user'" [class.bot-row]="msg.role === 'assistant'">
                    <div class="message-avatar">
                      @if (msg.role === 'user') {
                        <span>{{ getInitials(auth.currentUser()?.full_name) }}</span>
                      } @else {
                        <span>✨</span>
                      }
                    </div>

                    <div class="message-bubble" [class.user-bubble]="msg.role === 'user'" [class.bot-bubble]="msg.role === 'assistant'">
                      <div class="bubble-header">
                        <span class="sender-name">
                          {{ msg.role === 'user' ? (auth.currentUser()?.full_name || 'You') : 'EduVerse AI Tutor' }}
                        </span>

                        @if (msg.role === 'assistant') {
                          @if (msg.is_course_grounded) {
                            <span class="grounding-badge grounded-badge" title="Grounded in official course materials">
                              🌿 {{ msg.grounded_in || 'Course Grounded' }}
                            </span>
                          } @else if (msg.is_course_grounded === false) {
                            <span class="grounding-badge ungrounded-badge" title="General technical explanation">
                              💡 General Concept
                            </span>
                          }
                        }
                      </div>

                      <div class="message-content" [innerHTML]="formatMessage(msg.content)"></div>

                      @if (msg.suggestions && msg.suggestions.length > 0) {
                        <div class="suggestions-container">
                          <span class="suggestions-label">Related Inquiries:</span>
                          <div class="suggestion-chips-row">
                            @for (s of msg.suggestions; track s) {
                              <button type="button" class="suggestion-chip" (click)="usePrompt(s)">
                                {{ s }}
                              </button>
                            }
                          </div>
                        </div>
                      }
                    </div>
                  </div>
                }

                @if (isGenerating) {
                  <div class="message-row bot-row">
                    <div class="message-avatar"><span>✨</span></div>
                    <div class="message-bubble bot-bubble generating-bubble">
                      <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    </div>
                  </div>
                }
              }
            </div>

            <!-- Chat Input -->
            <div class="chat-input-container">
              <form (ngSubmit)="sendMessage()" class="chat-input-form">
                <input
                  type="text"
                  class="chat-input"
                  [(ngModel)]="userPrompt"
                  name="userPrompt"
                  [placeholder]="selectedCourseId ? 'Ask anything about ' + getSelectedCourseTitle() + '...' : 'Ask anything about coding, systems, or course concepts...'"
                  [disabled]="isGenerating"
                  autocomplete="off"
                />
                <button
                  type="submit"
                  class="btn btn-primary send-btn"
                  [disabled]="!userPrompt.trim() || isGenerating"
                >
                  Send
                </button>
              </form>
            </div>
          }

          <!-- TAB 2: Study Recommendations View -->
          @if (activeTab === 'recommendations') {
            <div class="recommendations-container">
              @if (loadingRecommendations) {
                <div class="loading-state">
                  <div class="spinner"></div>
                  <span>Analyzing your quiz records, lesson completion, and assignment deadlines...</span>
                </div>
              } @else if (recommendationsError) {
                <div class="alert alert-warning">
                  {{ recommendationsError }}
                </div>
              } @else if (recommendationsData) {
                <!-- Advisory Banner -->
                <div class="advisory-banner">
                  <span class="advisory-icon">🎯</span>
                  <div class="advisory-text">
                    <strong>Progress Advisory:</strong>
                    <p>{{ recommendationsData.advisory_notice }}</p>
                  </div>
                </div>

                @if (recommendationsData.recommendations.length === 0) {
                  <div class="empty-recs-card">
                    <div class="empty-icon">🎉</div>
                    <h3>You are completely up to date!</h3>
                    <p>All enrolled lessons are completed, quizzes passed, and no pending assignments are due. Great work!</p>
                    <a routerLink="/courses" class="btn btn-primary">Browse More Courses</a>
                  </div>
                } @else {
                  <div class="recs-meta-bar">
                    <span class="recs-count">
                      {{ recommendationsData.total_recommendations }} Personalized Action Items
                    </span>
                    <button type="button" class="btn btn-sm btn-outline" (click)="loadRecommendations()">
                      ↻ Refresh Analysis
                    </button>
                  </div>

                  <div class="recs-grid">
                    @for (rec of recommendationsData.recommendations; track rec.id) {
                      <div class="rec-card" [class]="'priority-' + rec.priority">
                        <div class="rec-card-top">
                          <span class="priority-pill" [class]="'pill-' + rec.priority">
                            {{ rec.priority | uppercase }} PRIORITY
                          </span>
                          <span class="type-pill">
                            {{ formatRecommendationType(rec.type) }}
                          </span>
                        </div>

                        <h4 class="rec-title">{{ rec.title }}</h4>
                        <div class="rec-course">{{ rec.course_title }}</div>
                        <p class="rec-desc">{{ rec.description }}</p>

                        <div class="rec-footer">
                          <a [routerLink]="rec.action_url" class="btn btn-sm btn-primary">
                            {{ getActionLabel(rec.type) }} →
                          </a>
                        </div>
                      </div>
                    }
                  </div>
                }
              }
            </div>
          }
        </main>
      </div>
    </div>
  `,
  styles: [`
    .assistant-page {
      padding: 1.5rem;
      background-color: var(--bg-app);
      height: calc(100vh - 75px);
      display: flex;
      flex-direction: column;
    }
    .assistant-container {
      max-width: 1350px;
      margin: 0 auto;
      width: 100%;
      height: 100%;
      display: grid;
      grid-template-columns: 290px 1fr;
      gap: 1.5rem;
    }
    @media (max-width: 900px) {
      .assistant-container {
        grid-template-columns: 1fr;
      }
      .threads-sidebar {
        display: none;
      }
    }
    .threads-sidebar {
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
    }
    .view-switch-group {
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      margin-top: 1rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--border-color);
    }
    .switch-tab-btn {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.65rem 0.85rem;
      border-radius: var(--radius-md);
      font-size: 0.88rem;
      font-weight: 600;
      background: transparent;
      border: 1px solid transparent;
      cursor: pointer;
      color: var(--text-main);
      transition: all 0.15s ease;
    }
    .switch-tab-btn:hover {
      background: var(--bg-subtle);
    }
    .switch-tab-btn.active {
      background: #eef2ff;
      border-color: #c7d2fe;
      color: var(--primary);
    }
    .badge-count {
      background: var(--primary);
      color: #ffffff;
      font-size: 0.72rem;
      font-weight: 700;
      padding: 0.15rem 0.45rem;
      border-radius: 999px;
    }
    .threads-list {
      margin-top: 1.25rem;
      flex: 1 1 auto;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }
    .threads-label {
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--text-light);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.4rem;
    }
    .thread-item { display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0.75rem; border-radius: var(--radius-md); font-size: 0.85rem; font-weight: 600; color: var(--text-main); cursor: pointer; transition: var(--transition); background-color: var(--bg-subtle); }
    .thread-item:hover { background-color: #e2e8f0; }
    .thread-item.active { background-color: #eef2ff; border: 1px solid #c7d2fe; color: var(--primary); }
    .thread-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; margin-right: 0.5rem; }
    .delete-thread-btn { background: transparent; border: none; color: var(--text-light); cursor: pointer; padding: 0.2rem 0.4rem; border-radius: 4px; font-size: 0.75rem; }
    .delete-thread-btn:hover { background-color: #fee2e2; color: #ef4444; }
    .thread-loader, .no-threads { font-size: 0.85rem; color: var(--text-light); padding: 0.5rem 0; line-height: 1.4; }
    .sidebar-info-box {
      margin-top: 1.25rem;
      padding: 1rem;
      background: var(--bg-subtle);
      border-radius: var(--radius-md);
      font-size: 0.85rem;
      line-height: 1.5;
    }
    .sidebar-info-box h4 {
      font-size: 0.9rem;
      margin-bottom: 0.4rem;
      color: var(--text-main);
    }
    .sidebar-info-box p {
      margin: 0;
      color: var(--text-muted);
    }
    .chat-main {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      padding: 0;
    }
    .chat-header {
      padding: 1rem 1.5rem;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      flex-wrap: wrap;
      background: #ffffff;
    }
    .header-left-col {
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    .bot-badge {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .bot-icon {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
      color: #ffffff;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.2rem;
    }
    .bot-meta h3 {
      font-size: 1rem;
      margin: 0;
      line-height: 1.2;
    }
    .status-online {
      font-size: 0.75rem;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 0.4rem;
      margin-top: 0.2rem;
    }
    .dot {
      width: 7px;
      height: 7px;
      background-color: #10b981;
      border-radius: 50%;
    }
    .context-controls {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .context-field {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .context-select {
      padding: 0.35rem 0.6rem;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      font-size: 0.82rem;
      background: #ffffff;
      color: var(--text-main);
      max-width: 220px;
      outline: none;
    }
    .context-select:focus {
      border-color: var(--primary);
    }
    .btn-clear-context {
      background: transparent;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 0.9rem;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
    }
    .btn-clear-context:hover {
      background: var(--bg-subtle);
      color: var(--text-main);
    }
    .active-context-banner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.5rem 1.5rem;
      background: #f0fdf4;
      border-bottom: 1px solid #bbf7d0;
      font-size: 0.82rem;
      color: #166534;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .context-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
    }
    .context-hint {
      font-size: 0.78rem;
      color: #15803d;
    }
    .messages-stream {
      flex: 1 1 auto;
      overflow-y: auto;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
      background-color: #fafbfc;
    }
    .empty-chat-welcome {
      text-align: center;
      margin: auto;
      max-width: 550px;
      padding: 2rem 1rem;
    }
    .welcome-icon {
      font-size: 2.75rem;
      margin-bottom: 0.75rem;
    }
    .empty-chat-welcome h2 {
      font-size: 1.35rem;
      margin-bottom: 0.5rem;
    }
    .empty-chat-welcome p {
      color: var(--text-muted);
      font-size: 0.92rem;
      line-height: 1.5;
      margin-bottom: 1.5rem;
    }
    .prompt-chips {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .prompt-chip {
      background-color: #ffffff;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      padding: 0.75rem 1rem;
      font-size: 0.88rem;
      font-weight: 500;
      color: var(--text-main);
      text-align: left;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .prompt-chip:hover {
      border-color: var(--primary);
      background-color: #f8fafc;
      transform: translateY(-1px);
    }
    .message-row {
      display: flex;
      gap: 0.85rem;
      max-width: 82%;
    }
    .user-row {
      align-self: flex-end;
      flex-direction: row-reverse;
    }
    .bot-row {
      align-self: flex-start;
    }
    .message-avatar {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 0.85rem;
      flex-shrink: 0;
    }
    .user-row .message-avatar {
      background-color: var(--primary);
      color: #ffffff;
    }
    .bot-row .message-avatar {
      background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
      color: #ffffff;
    }
    .message-bubble {
      padding: 1rem 1.25rem;
      border-radius: var(--radius-lg);
      font-size: 0.95rem;
      line-height: 1.6;
    }
    .bubble-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      margin-bottom: 0.35rem;
    }
    .user-bubble {
      background-color: var(--primary);
      color: #ffffff;
      border-bottom-right-radius: 4px;
    }
    .user-bubble .sender-name {
      color: #e0e7ff;
      font-size: 0.75rem;
    }
    .bot-bubble {
      background-color: #ffffff;
      border: 1px solid var(--border-color);
      color: var(--text-main);
      border-bottom-left-radius: 4px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .bot-bubble .sender-name {
      color: var(--primary);
      font-size: 0.75rem;
      font-weight: 700;
    }
    .grounding-badge {
      font-size: 0.72rem;
      font-weight: 600;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
    }
    .grounded-badge {
      background: #ecfdf5;
      color: #065f46;
      border: 1px solid #a7f3d0;
    }
    .ungrounded-badge {
      background: #f8fafc;
      color: var(--text-muted);
      border: 1px solid var(--border-color);
    }
    .suggestions-container {
      margin-top: 0.85rem;
      padding-top: 0.75rem;
      border-top: 1px solid var(--border-light);
    }
    .suggestions-label {
      font-size: 0.75rem;
      color: var(--text-muted);
      font-weight: 600;
      display: block;
      margin-bottom: 0.4rem;
    }
    .suggestion-chips-row {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
    }
    .suggestion-chip {
      background: var(--bg-subtle);
      border: 1px solid var(--border-color);
      border-radius: 999px;
      padding: 0.25rem 0.65rem;
      font-size: 0.78rem;
      color: var(--text-main);
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .suggestion-chip:hover {
      background: #eef2ff;
      border-color: #c7d2fe;
      color: var(--primary);
    }
    .chat-input-container {
      padding: 1rem 1.5rem;
      border-top: 1px solid var(--border-color);
      background-color: #ffffff;
    }
    .chat-input-form {
      display: flex;
      gap: 0.75rem;
    }
    .chat-input {
      flex: 1;
      padding: 0.75rem 1rem;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      font-size: 0.95rem;
      font-family: var(--font-sans);
      outline: none;
    }
    .chat-input:focus {
      border-color: var(--primary);
    }
    .send-btn {
      padding: 0.75rem 1.5rem;
    }
    .typing-indicator {
      display: flex;
      gap: 0.35rem;
      align-items: center;
      padding: 0.3rem 0.5rem;
    }
    .typing-indicator span {
      width: 6px;
      height: 6px;
      background-color: var(--text-muted);
      border-radius: 50%;
      animation: bounce 1.4s infinite ease-in-out both;
    }
    .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
    .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
    @keyframes bounce {
      0%, 80%, 100% { transform: scale(0); }
      40% { transform: scale(1); }
    }
    /* Recommendations View Styles */
    .recommendations-container {
      flex: 1 1 auto;
      overflow-y: auto;
      padding: 1.5rem;
      background: #fafbfc;
    }
    .advisory-banner {
      display: flex;
      gap: 0.75rem;
      align-items: flex-start;
      padding: 1rem 1.25rem;
      background: #eff6ff;
      border-left: 4px solid #3b82f6;
      border-radius: var(--radius-md);
      margin-bottom: 1.5rem;
    }
    .advisory-icon {
      font-size: 1.4rem;
    }
    .advisory-text strong {
      font-size: 0.9rem;
      color: #1e3a8a;
    }
    .advisory-text p {
      margin: 0.2rem 0 0 0;
      font-size: 0.85rem;
      color: #1e40af;
      line-height: 1.4;
    }
    .recs-meta-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 1.25rem;
    }
    .recs-count {
      font-weight: 700;
      font-size: 0.95rem;
      color: var(--text-main);
    }
    .recs-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1.25rem;
    }
    .rec-card {
      background: #ffffff;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg);
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      box-shadow: 0 1px 3px rgba(0,0,0,0.03);
      border-left-width: 4px;
    }
    .rec-card.priority-urgent { border-left-color: #ef4444; }
    .rec-card.priority-high { border-left-color: #f59e0b; }
    .rec-card.priority-medium { border-left-color: #3b82f6; }
    .rec-card.priority-low { border-left-color: #94a3b8; }
    .rec-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
    .priority-pill { font-size: 0.7rem; font-weight: 800; padding: 0.15rem 0.45rem; border-radius: 4px; }
    .pill-urgent { background: #fee2e2; color: #991b1b; }
    .pill-high { background: #fef3c7; color: #92400e; }
    .pill-medium { background: #dbeafe; color: #1e40af; }
    .pill-low { background: #f1f5f9; color: #475569; }
    .type-pill { font-size: 0.75rem; font-weight: 600; color: var(--text-muted); background: var(--bg-subtle); padding: 0.15rem 0.45rem; border-radius: 4px; }
    .rec-title {
      font-size: 1rem;
      margin: 0 0 0.3rem 0;
      color: var(--text-main);
    }
    .rec-course {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--primary);
      margin-bottom: 0.6rem;
    }
    .rec-desc {
      font-size: 0.88rem;
      color: var(--text-muted);
      line-height: 1.5;
      margin: 0 0 1.25rem 0;
      flex: 1 1 auto;
    }
    .rec-footer {
      display: flex;
      justify-content: flex-end;
    }
    .empty-recs-card {
      text-align: center;
      padding: 3.5rem 1.5rem;
      background: #ffffff;
      border-radius: var(--radius-lg);
      border: 1px solid var(--border-color);
      max-width: 500px;
      margin: 2rem auto;
    }
    .empty-icon {
      font-size: 2.75rem;
      margin-bottom: 0.75rem;
    }
    .empty-recs-card h3 {
      font-size: 1.2rem;
      margin-bottom: 0.5rem;
    }
    .empty-recs-card p {
      color: var(--text-muted);
      font-size: 0.92rem;
      margin-bottom: 1.25rem;
      line-height: 1.5;
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
export class AIAssistantComponent implements OnInit, AfterViewChecked {
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;

  activeTab: 'chat' | 'recommendations' = 'chat';

  // Conversations
  threads: AIConversationSummary[] = [];
  loadingThreads = false;
  currentConversationId?: number;

  messages: AIMessage[] = [];
  userPrompt = '';
  isGenerating = false;

  // Grounding Context State
  enrolledCourses: EnrolledCourseDetail[] = [];
  selectedCourseId: number | null = null;
  selectedLessonId: number | null = null;
  courseLessons: LessonSummary[] = [];

  // Recommendations State
  loadingRecommendations = false;
  recommendationsData: StudyRecommendationsResponse | null = null;
  recommendationsError: string | null = null;

  promptChipsGeneral = [
    'Explain asynchronous programming in Python',
    'What is the difference between SQL and NoSQL databases?',
    'How does dependency injection work in FastAPI?',
    'Explain Argon2id password hashing and JWT security'
  ];

  constructor(
    private aiService: AIService,
    private studentService: StudentService,
    private courseService: CourseService,
    private route: ActivatedRoute,
    public auth: AuthService
  ) {}

  ngOnInit(): void {
    this.fetchThreads();
    this.loadEnrolledCourses();

    // Check query params for courseId or lessonId context
    this.route.queryParamMap.subscribe((params) => {
      const cId = params.get('courseId');
      const lId = params.get('lessonId');

      if (cId) {
        this.selectedCourseId = Number(cId);
        this.loadCourseLessons(this.selectedCourseId);
      }
      if (lId) {
        this.selectedLessonId = Number(lId);
      }
    });
  }

  ngAfterViewChecked(): void {
    if (this.activeTab === 'chat') {
      this.scrollToBottom();
    }
  }

  scrollToBottom(): void {
    try {
      if (this.messagesContainer) {
        this.messagesContainer.nativeElement.scrollTop = this.messagesContainer.nativeElement.scrollHeight;
      }
    } catch {}
  }

  loadEnrolledCourses(): void {
    this.studentService.getMyLearning().subscribe({
      next: (courses) => {
        this.enrolledCourses = courses;
      },
      error: () => {
        this.enrolledCourses = [];
      }
    });
  }

  onCourseSelected(courseId: number | null): void {
    this.selectedCourseId = courseId;
    this.selectedLessonId = null;
    this.courseLessons = [];

    if (courseId) {
      this.loadCourseLessons(courseId);
    }
  }

  loadCourseLessons(courseId: number): void {
    this.courseService.getCourse(courseId).subscribe({
      next: (detail) => {
        this.courseLessons = detail.lessons || [];
      },
      error: () => {
        this.courseLessons = [];
      }
    });
  }

  clearContext(): void {
    this.selectedCourseId = null;
    this.selectedLessonId = null;
    this.courseLessons = [];
  }

  getSelectedCourseTitle(): string {
    if (!this.selectedCourseId) return 'Selected Course';
    const found = this.enrolledCourses.find(c => c.course_id === this.selectedCourseId);
    return found ? found.course_title : 'Selected Course';
  }

  getSelectedLessonTitle(): string {
    if (!this.selectedLessonId) return '';
    const found = this.courseLessons.find(l => l.id === this.selectedLessonId);
    return found ? found.title : '';
  }

  getActivePromptChips(): string[] {
    if (this.selectedCourseId) {
      const cTitle = this.getSelectedCourseTitle();
      return [
        `Explain the core architectural concepts of ${cTitle}`,
        `What are the most common beginner mistakes in this syllabus?`,
        `Can you provide practical implementation examples?`,
        `Summarize the key takeaways for this module`
      ];
    }
    return this.promptChipsGeneral;
  }

  switchToRecommendations(): void {
    this.activeTab = 'recommendations';
    if (!this.recommendationsData) {
      this.loadRecommendations();
    }
  }

  loadRecommendations(): void {
    this.loadingRecommendations = true;
    this.recommendationsError = null;

    this.aiService.getStudyRecommendations().subscribe({
      next: (res) => {
        this.recommendationsData = res;
        this.loadingRecommendations = false;
      },
      error: (err) => {
        this.loadingRecommendations = false;
        this.recommendationsError = err?.error?.detail || 'Unable to analyze study recommendations at this time.';
      }
    });
  }

  formatRecommendationType(type: string): string {
    switch (type) {
      case 'continue_lesson': return 'Next Lesson';
      case 'review_quiz': return 'Quiz Retake';
      case 'assignment_due': return 'Upcoming Assignment';
      case 'take_quiz': return 'Assessment Ready';
      default: return 'Study Action';
    }
  }

  getActionLabel(type: string): string {
    switch (type) {
      case 'continue_lesson': return 'Resume Lesson';
      case 'review_quiz': return 'Retake Quiz';
      case 'assignment_due': return 'Submit Work';
      case 'take_quiz': return 'Start Quiz';
      default: return 'Review';
    }
  }

  fetchThreads(): void {
    this.loadingThreads = true;
    this.aiService.getConversations().subscribe({
      next: (list) => {
        this.threads = list;
        this.loadingThreads = false;
      },
      error: () => {
        this.loadingThreads = false;
      }
    });
  }

  startNewChat(): void {
    this.currentConversationId = undefined;
    this.messages = [];
  }

  loadConversation(conversationId: number): void {
    this.currentConversationId = conversationId;
    this.aiService.getConversationDetail(conversationId).subscribe({
      next: (detail) => {
        this.messages = detail.messages;
        if (detail.course_id) {
          this.selectedCourseId = detail.course_id;
          this.loadCourseLessons(detail.course_id);
        }
      }
    });
  }

  deleteThread(event: Event, threadId: number): void {
    event.stopPropagation();
    this.aiService.deleteConversation(threadId).subscribe({
      next: () => {
        if (this.currentConversationId === threadId) {
          this.startNewChat();
        }
        this.fetchThreads();
      }
    });
  }

  usePrompt(prompt: string): void {
    this.userPrompt = prompt;
    this.sendMessage();
  }

  sendMessage(): void {
    const text = this.userPrompt.trim();
    if (!text || this.isGenerating) return;

    this.messages.push({
      role: 'user',
      content: text
    });
    this.userPrompt = '';
    this.isGenerating = true;

    this.aiService.chat(text, this.currentConversationId, this.selectedCourseId, this.selectedLessonId).subscribe({
      next: (res) => {
        this.isGenerating = false;
        this.currentConversationId = res.conversation_id;
        this.messages.push({
          role: 'assistant',
          content: res.message || res.response,
          grounded_in: res.grounded_in || undefined,
          is_course_grounded: res.is_course_grounded,
          suggestions: res.suggestions
        });
        this.fetchThreads();
      },
      error: () => {
        this.isGenerating = false;
        this.messages.push({
          role: 'assistant',
          content: 'Sorry, I encountered an issue processing your request. Please try again shortly.',
          is_course_grounded: false
        });
      }
    });
  }

  getInitials(name?: string): string {
    if (!name) return 'U';
    return name
      .split(' ')
      .map(p => p.charAt(0).toUpperCase())
      .slice(0, 2)
      .join('');
  }

  formatMessage(content: string): string {
    if (!content) return '';
    return content
      .replace(/### (.*$)/gim, '<h4 style="margin: 0.5rem 0 0.2rem 0; font-size: 1rem;">$1</h4>')
      .replace(/## (.*$)/gim, '<h3 style="margin: 0.75rem 0 0.3rem 0; font-size: 1.1rem;">$1</h3>')
      .replace(/```python([\s\S]*?)```/gim, '<pre style="background: #1e293b; color: #f8fafc; padding: 0.75rem; border-radius: 6px; overflow-x: auto; margin: 0.5rem 0; font-family: monospace;"><code>$1</code></pre>')
      .replace(/```([\s\S]*?)```/gim, '<pre style="background: #1e293b; color: #f8fafc; padding: 0.75rem; border-radius: 6px; overflow-x: auto; margin: 0.5rem 0; font-family: monospace;"><code>$1</code></pre>')
      .replace(/`([^`]+)`/gim, '<code style="background: rgba(0,0,0,0.06); padding: 0.1rem 0.3rem; border-radius: 3px; font-family: monospace;">$1</code>')
      .replace(/\n\n/gim, '<br/><br/>')
      .replace(/\n/gim, '<br/>');
  }
}
