import { Component, OnInit, Input, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { CourseService } from '../../core/services/course.service';
import { LessonService } from '../../core/services/lesson.service';
import { MaterialService } from '../../core/services/material.service';
import { AIService } from '../../core/services/ai.service';
import { LessonSummaryResponse, PracticeQuestionsResponse, PracticeQuestionItem } from '../../core/models/ai.model';
import { CourseDetail, LessonSummary } from '../../core/models/course.model';
import { Lesson } from '../../core/models/lesson.model';

@Component({
  selector: 'app-course-learn',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="learn-page">
      @if (isLoading) {
        <div class="loading-state">
          <div class="spinner"></div>
          <span>Loading lesson content...</span>
        </div>
      } @else if (!lesson || !course) {
        <div class="container not-found card">
          <h2>Lesson Unavailable</h2>
          <p>This lesson could not be found or you may need to enroll first.</p>
          <a [routerLink]="['/courses', courseId]" class="btn btn-primary">Return to Course</a>
        </div>
      } @else {
        <!-- Top Sticky Sub-header -->
        <div class="learn-header">
          <div class="header-inner">
            <div class="header-left">
              <a [routerLink]="['/courses', course.id]" class="back-link">
                ← Back to Syllabus
              </a>
              <span class="divider">/</span>
              <span class="course-name">{{ course.title }}</span>
            </div>
            <div class="header-right">
              <div class="progress-pill">
                <span>Progress: {{ course.user_progress_percentage || 0 }}%</span>
                <div class="mini-bar">
                  <div class="mini-fill" [style.width.%]="course.user_progress_percentage || 0"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="learn-container">
          <!-- Left Syllabus Sidebar -->
          <aside class="syllabus-sidebar">
            <div class="sidebar-header">
              <h3>Curriculum Outline</h3>
            </div>

            <div class="sidebar-lessons">
              @if (hasSections()) {
                @for (sec of course.sections; track sec.id) {
                  <div class="sidebar-section-header">
                    <span class="sec-label">Section {{ sec.order_index }}</span>
                    <span class="sec-title">{{ sec.title }}</span>
                  </div>
                  @for (l of getLessonsForSection(sec.id); track l.id) {
                    <a
                      [routerLink]="['/courses', course.id, 'learn', l.id]"
                      class="sidebar-item"
                      [class.active]="l.id === lesson.id"
                      [class.completed]="l.is_completed"
                    >
                      <div class="item-status">
                        @if (l.is_completed) {
                          <span class="status-check">✓</span>
                        } @else {
                          <span class="status-index">{{ l.order_index }}</span>
                        }
                      </div>
                      <span class="item-title">{{ l.title }}</span>
                    </a>
                  }
                }

                @if (getUncategorizedLessons().length > 0) {
                  <div class="sidebar-section-header">
                    <span class="sec-label">General</span>
                    <span class="sec-title">Ungrouped Lessons</span>
                  </div>
                  @for (l of getUncategorizedLessons(); track l.id) {
                    <a
                      [routerLink]="['/courses', course.id, 'learn', l.id]"
                      class="sidebar-item"
                      [class.active]="l.id === lesson.id"
                      [class.completed]="l.is_completed"
                    >
                      <div class="item-status">
                        @if (l.is_completed) {
                          <span class="status-check">✓</span>
                        } @else {
                          <span class="status-index">{{ l.order_index }}</span>
                        }
                      </div>
                      <span class="item-title">{{ l.title }}</span>
                    </a>
                  }
                }
              } @else {
                @for (l of course.lessons; track l.id) {
                  <a
                    [routerLink]="['/courses', course.id, 'learn', l.id]"
                    class="sidebar-item"
                    [class.active]="l.id === lesson.id"
                    [class.completed]="l.is_completed"
                  >
                    <div class="item-status">
                      @if (l.is_completed) {
                        <span class="status-check">✓</span>
                      } @else {
                        <span class="status-index">{{ l.order_index }}</span>
                      }
                    </div>
                    <span class="item-title">{{ l.title }}</span>
                  </a>
                }
              }
            </div>

            @if (course.quizzes.length > 0) {
              <div class="sidebar-quizzes">
                <div class="quizzes-label">Assessments</div>
                @for (q of course.quizzes; track q.id) {
                  <a [routerLink]="['/courses', course.id, 'quizzes', q.id]" class="sidebar-quiz-item">
                    <span>📝 {{ q.title }}</span>
                    <span class="quiz-pts">Pass: {{ q.passing_score }}%</span>
                  </a>
                }
              </div>
            }

            @if (course.assignments && course.assignments.length > 0) {
              <div class="sidebar-quizzes">
                <div class="quizzes-label">Practical Assignments</div>
                @for (a of course.assignments; track a.id) {
                  <a [routerLink]="['/courses', course.id, 'assignments', a.id]" class="sidebar-quiz-item">
                    <span>💼 {{ a.title }}</span>
                    <span class="quiz-pts">{{ a.max_marks }} pts</span>
                  </a>
                }
              </div>
            }

            @if (course.materials && course.materials.length > 0) {
              <div class="sidebar-quizzes">
                <div class="quizzes-label">Downloads & Resources</div>
                @for (m of course.materials; track m.id) {
                  <button (click)="downloadMaterial(m)" class="sidebar-quiz-item sidebar-mat-btn">
                    <span>📎 {{ m.title }}</span>
                    <span class="quiz-pts">{{ m.file_size_formatted }}</span>
                  </button>
                }
              </div>
            }
          </aside>

          <!-- Main Lesson Content Viewer -->
          <main class="lesson-viewer">
            <div class="content-card card">
              <div class="lesson-badge-row">
                <span class="badge badge-primary">Lesson {{ lesson.order_index }} of {{ course.lessons.length }}</span>
                @if (lesson.is_completed) {
                  <span class="badge badge-success">✓ Completed</span>
                }
              </div>

              <h1 class="lesson-main-title">{{ lesson.title }}</h1>

              <!-- Formatted Content -->
              <div class="lesson-body">
                <div class="formatted-content" [innerHTML]="formatContent(lesson.content)"></div>
              </div>

              <!-- Lesson Actions & Bottom Navigation -->
              <div class="lesson-footer">
                <div class="nav-prev">
                  @if (hasPreviousLesson()) {
                    <a [routerLink]="['/courses', course.id, 'learn', getPreviousLessonId()]" class="btn btn-secondary">
                      ← Previous Lesson
                    </a>
                  }
                </div>

                <div class="nav-center">
                  <button
                    (click)="toggleCompleted()"
                    class="btn"
                    [ngClass]="lesson.is_completed ? 'btn-outline' : 'btn-primary'"
                    [disabled]="isCompleting"
                  >
                    @if (isCompleting) {
                      <span>Saving...</span>
                    } @else if (lesson.is_completed) {
                      <span>✓ Completed</span>
                    } @else {
                      <span>Mark as Complete</span>
                    }
                  </button>
                </div>

                <div class="nav-next">
                  @if (hasNextLesson()) {
                    <a [routerLink]="['/courses', course.id, 'learn', getNextLessonId()]" class="btn btn-primary">
                      Next Lesson →
                    </a>
                  } @else if (course.quizzes.length > 0) {
                    <a [routerLink]="['/courses', course.id, 'quizzes', course.quizzes[0].id]" class="btn btn-primary">
                      Take Quiz Assessment →
                    </a>
                  }
                </div>
              </div>
            </div>
          </main>
        </div>
      }
    </div>
  `,
  styles: [`
    .learn-page {
      background-color: var(--bg-app);
      min-height: calc(100vh - 120px);
    }
    .learn-header {
      background: #ffffff;
      border-bottom: 1px solid var(--border-color);
      position: sticky;
      top: 61px;
      z-index: 99;
    }
    .header-inner {
      max-width: 1400px;
      margin: 0 auto;
      padding: 0.75rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .header-left {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.9rem;
    }
    .back-link {
      color: var(--text-muted);
      font-weight: 600;
    }
    .back-link:hover {
      color: var(--primary);
    }
    .divider {
      color: var(--border-color);
    }
    .course-name {
      font-weight: 700;
      color: var(--text-main);
    }
    .progress-pill {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-muted);
    }
    .mini-bar {
      width: 100px;
      height: 6px;
      background: var(--border-color);
      border-radius: var(--radius-full);
      overflow: hidden;
    }
    .mini-fill {
      height: 100%;
      background: var(--primary);
      transition: width 0.3s;
    }
    .learn-container {
      max-width: 1400px;
      margin: 0 auto;
      padding: 1.5rem;
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 2rem;
      align-items: start;
    }
    @media (max-width: 900px) {
      .learn-container {
        grid-template-columns: 1fr;
      }
      .syllabus-sidebar {
        order: 2;
      }
      .lesson-viewer {
        order: 1;
      }
    }
    .syllabus-sidebar {
      background: #ffffff;
      border: 1px solid rgba(221, 214, 254, 0.7);
      border-radius: var(--radius-lg);
      padding: 1.35rem;
      position: sticky;
      top: 130px;
      box-shadow: 0 4px 18px rgba(99, 102, 241, 0.05);
    }
    .sidebar-header h3 {
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 1rem;
      color: #1e1b4b;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid rgba(221, 214, 254, 0.6);
    }
    .sidebar-lessons {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
    }
    .sidebar-section-header {
      padding: 0.75rem 0.5rem 0.25rem 0.5rem;
      border-top: 1px solid var(--border-light);
      margin-top: 0.5rem;
      display: flex;
      flex-direction: column;
      gap: 0.15rem;
    }
    .sec-label {
      font-size: 0.7rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--primary);
    }
    .sec-title {
      font-size: 0.825rem;
      font-weight: 600;
      color: var(--text-main);
    }
    .sidebar-item {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.65rem 0.75rem;
      border-radius: var(--radius-md);
      text-decoration: none;
      color: var(--text-main);
      font-size: 0.875rem;
      transition: var(--transition);
    }
    .sidebar-item:hover {
      background-color: var(--bg-subtle);
    }
    .sidebar-item.active {
      background-color: var(--primary-light);
      color: var(--primary);
      font-weight: 700;
    }
    .item-status {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background-color: var(--bg-subtle);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.75rem;
      font-weight: 700;
      flex-shrink: 0;
    }
    .sidebar-item.completed .item-status {
      background-color: var(--success-light);
      color: var(--success);
    }
    .sidebar-item.active .item-status {
      background-color: var(--primary);
      color: #ffffff;
    }
    .item-title {
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .sidebar-quizzes {
      margin-top: 1.5rem;
      padding-top: 1.25rem;
      border-top: 1px solid var(--border-light);
    }
    .quizzes-label {
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      color: var(--text-light);
      margin-bottom: 0.5rem;
    }
    .sidebar-quiz-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.6rem 0.75rem;
      border-radius: var(--radius-md);
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-main);
      background-color: var(--bg-subtle);
      margin-bottom: 0.35rem;
      text-decoration: none;
    }
    .sidebar-quiz-item:hover {
      background-color: #e2e8f0;
      color: var(--primary);
    }
    .quiz-pts {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .sidebar-mat-btn {
      width: 100%;
      background: transparent;
      border: 1px solid var(--border-light);
      cursor: pointer;
      font-family: inherit;
      text-align: left;
    }
    .sidebar-mat-btn:hover {
      background-color: var(--bg-subtle);
      border-color: var(--primary);
    }
    .content-card {
      padding: 2.5rem;
      background: #ffffff;
      border: 1px solid rgba(221, 214, 254, 0.7);
      border-radius: var(--radius-lg);
      box-shadow: 0 8px 25px -4px rgba(99, 102, 241, 0.07);
      min-height: 500px;
      display: flex;
      flex-direction: column;
    }
    .lesson-badge-row {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1rem;
    }
    .lesson-main-title {
      font-size: 2rem;
      margin-bottom: 2rem;
      padding-bottom: 1.25rem;
      border-bottom: 1px solid var(--border-light);
    }
    .lesson-body {
      flex: 1 0 auto;
      font-size: 1.05rem;
      line-height: 1.8;
      color: #334155;
    }
    .formatted-content h2 {
      font-size: 1.45rem;
      margin: 1.75rem 0 0.85rem 0;
      color: var(--text-main);
    }
    .formatted-content h3 {
      font-size: 1.2rem;
      margin: 1.5rem 0 0.75rem 0;
      color: var(--text-main);
    }
    .formatted-content p {
      margin-bottom: 1.25rem;
    }
    .formatted-content ul, .formatted-content ol {
      margin: 1rem 0 1.5rem 1.5rem;
    }
    .formatted-content li {
      margin-bottom: 0.5rem;
    }
    .formatted-content code {
      font-family: var(--font-mono);
      background-color: #f1f5f9;
      color: #e11d48;
      padding: 0.15rem 0.4rem;
      border-radius: 4px;
      font-size: 0.9em;
    }
    .formatted-content pre {
      background-color: #0f172a;
      color: #f8fafc;
      padding: 1.25rem;
      border-radius: var(--radius-md);
      overflow-x: auto;
      margin: 1.5rem 0;
      font-family: var(--font-mono);
      font-size: 0.9rem;
    }
    .formatted-content pre code {
      background: transparent;
      color: inherit;
      padding: 0;
    }
    .lesson-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 3rem;
      padding-top: 2rem;
      border-top: 1px solid var(--border-light);
      flex-wrap: wrap;
      gap: 1rem;
    }
    .ai-help-panel {
      margin-top: 1.75rem;
      display: flex;
      align-items: center;
      gap: 1.25rem;
      padding: 1.25rem 1.75rem;
      background: linear-gradient(135deg, #ffffff 0%, #eef2ff 100%);
      border-color: #c7d2fe;
    }
    .ai-help-icon {
      font-size: 1.75rem;
    }
    .ai-help-content {
      flex: 1;
    }
    .ai-help-content h4 {
      font-size: 0.95rem;
      margin-bottom: 0.2rem;
    }
    .ai-help-content p {
      font-size: 0.85rem;
      color: var(--text-muted);
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
    .ai-action-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-top: 0.75rem;
    }
    .btn-outline-ai {
      background: #ffffff;
      border: 1px solid #c7d2fe;
      color: var(--primary);
      font-weight: 600;
      border-radius: var(--radius-md);
      cursor: pointer;
      transition: all 0.15s ease;
      padding: 0.4rem 0.8rem;
    }
    .btn-outline-ai:hover {
      background: #eef2ff;
      border-color: var(--primary);
    }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.65);
      backdrop-filter: blur(4px);
      z-index: 1000;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
    }
    .modal-dialog {
      background: #ffffff;
      max-width: 650px;
      width: 100%;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      border-radius: var(--radius-lg);
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
      animation: modalFadeIn 0.2s ease-out;
    }
    .modal-dialog-lg {
      max-width: 800px;
    }
    @keyframes modalFadeIn {
      from { opacity: 0; transform: scale(0.96); }
      to { opacity: 1; transform: scale(1); }
    }
    .modal-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border-color);
    }
    .modal-title-wrap {
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }
    .modal-title-wrap h3 {
      margin: 0;
      font-size: 1.15rem;
    }
    .modal-icon {
      font-size: 1.3rem;
    }
    .close-btn {
      background: transparent;
      border: none;
      font-size: 1.25rem;
      cursor: pointer;
      color: var(--text-muted);
      border-radius: 4px;
      padding: 0.2rem 0.5rem;
    }
    .close-btn:hover {
      background: var(--bg-subtle);
      color: var(--text-main);
    }
    .modal-body {
      padding: 1.5rem;
      overflow-y: auto;
      flex: 1 1 auto;
    }
    .modal-footer {
      display: flex;
      justify-content: flex-end;
      gap: 0.75rem;
      padding: 1rem 1.5rem;
      border-top: 1px solid var(--border-color);
      background: var(--bg-subtle);
      border-bottom-left-radius: var(--radius-lg);
      border-bottom-right-radius: var(--radius-lg);
    }
    .summary-meta-bar {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1.25rem;
      font-size: 0.85rem;
      color: var(--text-muted);
      flex-wrap: wrap;
    }
    .summary-section {
      margin-bottom: 1.25rem;
    }
    .summary-section h4 {
      font-size: 0.95rem;
      margin-bottom: 0.5rem;
      color: var(--text-main);
      font-weight: 700;
    }
    .summary-text {
      line-height: 1.7;
      color: var(--text-main);
      font-size: 0.95rem;
      background: var(--bg-subtle);
      padding: 1rem;
      border-radius: var(--radius-md);
    }
    .takeaways-list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .takeaways-list li {
      display: flex;
      gap: 0.6rem;
      align-items: flex-start;
      font-size: 0.92rem;
      line-height: 1.5;
    }
    .takeaway-bullet {
      color: #10b981;
      font-weight: 700;
    }
    .practice-disclaimer {
      display: flex;
      gap: 0.6rem;
      padding: 0.75rem 1rem;
      background: #eff6ff;
      border-left: 4px solid #3b82f6;
      border-radius: 4px;
      margin-bottom: 1.25rem;
      font-size: 0.85rem;
      color: #1e40af;
    }
    .practice-disclaimer p {
      margin: 0;
    }
    .disclaimer-icon {
      font-size: 1.1rem;
      flex-shrink: 0;
    }
    .questions-list {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }
    .practice-card {
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      padding: 1.25rem;
      background: #ffffff;
    }
    .question-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.75rem;
    }
    .question-number {
      font-weight: 700;
      font-size: 0.9rem;
      color: var(--primary);
    }
    .concept-tag {
      font-size: 0.75rem;
      background: var(--bg-subtle);
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      color: var(--text-muted);
    }
    .question-text {
      font-size: 0.95rem;
      font-weight: 600;
      margin-bottom: 1rem;
      line-height: 1.5;
    }
    .options-group {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .option-btn {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.75rem 1rem;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      background: #ffffff;
      text-align: left;
      cursor: pointer;
      font-size: 0.9rem;
      transition: all 0.15s ease;
      width: 100%;
    }
    .option-btn:hover:not(:disabled) {
      border-color: var(--primary);
      background: #f8fafc;
    }
    .opt-label {
      width: 26px;
      height: 26px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      background: var(--bg-subtle);
      font-weight: 700;
      font-size: 0.85rem;
      flex-shrink: 0;
    }
    .opt-text {
      flex: 1;
    }
    .option-btn.correct {
      border-color: #10b981;
      background: #ecfdf5;
    }
    .option-btn.correct .opt-label {
      background: #10b981;
      color: #ffffff;
    }
    .option-btn.incorrect {
      border-color: #ef4444;
      background: #fef2f2;
    }
    .option-btn.incorrect .opt-label {
      background: #ef4444;
      color: #ffffff;
    }
    .status-badge {
      font-size: 0.75rem;
      font-weight: 700;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
    }
    .correct-badge {
      color: #065f46;
      background: #d1fae5;
    }
    .incorrect-badge {
      color: #991b1b;
      background: #fee2e2;
    }
    .explanation-box {
      margin-top: 1rem;
      padding: 0.9rem 1rem;
      border-radius: var(--radius-md);
      font-size: 0.88rem;
      line-height: 1.5;
    }
    .explanation-success {
      background: #f0fdf4;
      border: 1px solid #bbf7d0;
      color: #166534;
    }
    .explanation-error {
      background: #fefce8;
      border: 1px solid #fef08a;
      color: #854d0e;
    }
    .explanation-title {
      font-weight: 700;
      margin-bottom: 0.35rem;
    }
    .explanation-box p {
      margin: 0;
    }
  `]
})
export class CourseLearnComponent implements OnInit, OnChanges {
  @Input() courseId!: string;
  @Input() lessonId!: string;

  course: CourseDetail | null = null;
  lesson: Lesson | null = null;
  isLoading = true;
  isCompleting = false;

  // AI Study Tools State
  showSummaryModal = false;
  isLoadingSummary = false;
  lessonSummary: LessonSummaryResponse | null = null;
  summaryError: string | null = null;

  showPracticeModal = false;
  isLoadingPractice = false;
  practiceData: PracticeQuestionsResponse | null = null;
  practiceError: string | null = null;
  userAnswers: { [questionId: number]: number } = {};

  constructor(
    private courseService: CourseService,
    private lessonService: LessonService,
    private materialService: MaterialService,
    private aiService: AIService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadData();
  }

  ngOnChanges(): void {
    this.loadData();
  }

  loadData(): void {
    if (!this.courseId || !this.lessonId) return;

    this.showSummaryModal = false;
    this.lessonSummary = null;
    this.showPracticeModal = false;
    this.practiceData = null;
    this.userAnswers = {};

    this.isLoading = true;
    const cId = Number(this.courseId);
    const lId = Number(this.lessonId);

    this.courseService.getCourse(cId).subscribe({
      next: (courseData) => {
        this.course = courseData;
        this.lessonService.getLesson(lId).subscribe({
          next: (lessonData) => {
            this.lesson = lessonData;
            this.isLoading = false;
          },
          error: () => {
            this.isLoading = false;
          }
        });
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  toggleCompleted(): void {
    if (!this.lesson) return;
    this.isCompleting = true;

    this.lessonService.completeLesson(this.lesson.id).subscribe({
      next: (progress) => {
        this.isCompleting = false;
        this.lesson!.is_completed = true;
        if (this.course) {
          this.course.user_progress_percentage = progress.course_progress_percentage;
          const found = this.course.lessons.find(l => l.id === this.lesson!.id);
          if (found) found.is_completed = true;
        }
      },
      error: () => {
        this.isCompleting = false;
      }
    });
  }

  hasPreviousLesson(): boolean {
    if (!this.course || !this.lesson) return false;
    const index = this.course.lessons.findIndex(l => l.id === this.lesson!.id);
    return index > 0;
  }

  getPreviousLessonId(): number {
    if (!this.course || !this.lesson) return 0;
    const index = this.course.lessons.findIndex(l => l.id === this.lesson!.id);
    return index > 0 ? this.course.lessons[index - 1].id : 0;
  }

  hasNextLesson(): boolean {
    if (!this.course || !this.lesson) return false;
    const index = this.course.lessons.findIndex(l => l.id === this.lesson!.id);
    return index < this.course.lessons.length - 1;
  }

  getNextLessonId(): number {
    if (!this.course || !this.lesson) return 0;
    const index = this.course.lessons.findIndex(l => l.id === this.lesson!.id);
    return index < this.course.lessons.length - 1 ? this.course.lessons[index + 1].id : 0;
  }

  formatContent(rawContent: string): string {
    if (!rawContent) return '';
    // Format markdown-like elements safely
    let formatted = rawContent
      .replace(/### (.*$)/gim, '<h3>$1</h3>')
      .replace(/## (.*$)/gim, '<h2>$1</h2>')
      .replace(/# (.*$)/gim, '<h2>$1</h2>')
      .replace(/```python([\s\S]*?)```/gim, '<pre><code>$1</code></pre>')
      .replace(/```([\s\S]*?)```/gim, '<pre><code>$1</code></pre>')
      .replace(/`([^`]+)`/gim, '<code>$1</code>')
      .replace(/\n\n/gim, '</p><p>')
      .replace(/\n/gim, '<br/>');

    return `<p>${formatted}</p>`;
  }

  hasSections(): boolean {
    return !!(this.course?.sections && this.course.sections.length > 0);
  }

  getLessonsForSection(sectionId: number) {
    if (!this.course) return [];
    return this.course.lessons.filter(l => l.section_id === sectionId);
  }

  getUncategorizedLessons() {
    if (!this.course) return [];
    return this.course.lessons.filter(l => !l.section_id);
  }

  downloadMaterial(m: any): void {
    if (!m || !m.id) return;
    this.materialService.triggerBrowserDownload(m.id, m.original_filename);
  }

  openSummary(): void {
    if (!this.lesson) return;
    this.showSummaryModal = true;
    this.summaryError = null;
    if (this.lessonSummary && this.lessonSummary.lesson_id === this.lesson.id) {
      return;
    }
    this.isLoadingSummary = true;
    this.aiService.summarizeLesson(this.lesson.id).subscribe({
      next: (res) => {
        this.lessonSummary = res;
        this.isLoadingSummary = false;
      },
      error: (err) => {
        this.isLoadingSummary = false;
        this.summaryError = err?.error?.detail || 'Unable to generate summary for this lesson.';
      }
    });
  }

  closeSummary(): void {
    this.showSummaryModal = false;
  }

  openPractice(): void {
    if (!this.lesson) return;
    this.showPracticeModal = true;
    this.practiceError = null;
    if (this.practiceData && this.practiceData.lesson_id === this.lesson.id) {
      return;
    }
    this.isLoadingPractice = true;
    this.userAnswers = {};
    this.aiService.getPracticeQuestions(this.lesson.id).subscribe({
      next: (res) => {
        this.practiceData = res;
        this.isLoadingPractice = false;
      },
      error: (err) => {
        this.isLoadingPractice = false;
        this.practiceError = err?.error?.detail || 'Unable to generate practice questions for this lesson.';
      }
    });
  }

  closePractice(): void {
    this.showPracticeModal = false;
  }

  selectOption(questionId: number, optionIndex: number): void {
    if (this.userAnswers[questionId] !== undefined) return;
    this.userAnswers[questionId] = optionIndex;
  }

  isOptionSelected(questionId: number, optionIndex: number): boolean {
    return this.userAnswers[questionId] === optionIndex;
  }

  isAnswerCorrect(q: PracticeQuestionItem): boolean | null {
    if (this.userAnswers[q.id] === undefined) return null;
    return this.userAnswers[q.id] === q.correct_index;
  }

  hasUserAnswers(): boolean {
    return Object.keys(this.userAnswers).length > 0;
  }

  resetDrills(): void {
    this.userAnswers = {};
  }
}

