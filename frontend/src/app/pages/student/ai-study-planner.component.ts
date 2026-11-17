import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  AICourseOutline,
  AIPlannerDeadline,
  PreferredStudyTime,
  StudyPlanRequest,
  StudyPlannerDashboard,
  StudyTask,
} from '../../core/models/ai-learning.model';
import { AILearningService } from '../../core/services/ai-learning.service';

@Component({
  selector: 'app-ai-study-planner',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="planner-page">
      <div class="container">
        <nav class="student-nav-bar" aria-label="Student navigation">
          <a routerLink="/student/dashboard" class="nav-pill">Overview</a>
          <a routerLink="/student/my-learning" class="nav-pill">My Learning</a>
          <a routerLink="/student/assignments" class="nav-pill">Assignments & Tasks</a>
          <a routerLink="/student/quiz-history" class="nav-pill">Assessment History</a>
          <a routerLink="/student/ai-quiz" class="nav-pill">AI Quiz Generator</a>
          <a routerLink="/student/study-planner" class="nav-pill active">Study Planner</a>
        </nav>

        <header class="page-header">
          <div>
            <span class="eyebrow">AI Learning Tools</span>
            <h1>AI Smart Study Planner</h1>
            <p>A personalized timetable built from your actual lesson progress, assessment scores, and deadlines.</p>
          </div>
          <button class="btn btn-primary" type="button" (click)="generatePlan()" [disabled]="busy || selectedCourseIds.length === 0">
            {{ busy ? 'Building your plan…' : 'Regenerate study plan' }}
          </button>
        </header>

        @if (errorMessage) {
          <div class="alert error">{{ errorMessage }}</div>
        }
        @if (planner?.generation_mode === 'rules') {
          <div class="alert fallback-notice">
            AI planning is unavailable right now. This timetable was created with EduVerse rules using your saved progress and deadlines.
          </div>
        }
        @if (noticeMessage) {
          <div class="alert success">{{ noticeMessage }}</div>
        }

        <section class="card setup-card">
          <div class="section-heading">
            <div>
              <h2>Study preferences</h2>
              <p class="muted">Choose courses and your available schedule. Your local time zone is {{ timeZone }}.</p>
            </div>
            <div class="setup-actions">
              <button class="btn btn-outline" type="button" (click)="savePreferences()" [disabled]="busy || selectedCourseIds.length === 0">
                Save preferences
              </button>
              <button class="btn btn-primary" type="button" (click)="generatePlan()" [disabled]="busy || selectedCourseIds.length === 0">
                Generate plan
              </button>
            </div>
          </div>

          @if (courses.length === 0) {
            <p class="empty-state">Enroll in a course and get instructor approval to start a personalized plan.</p>
          } @else {
            <div class="course-picker">
              <span class="field-label">Courses to include</span>
              <div class="course-options">
                @for (course of courses; track course.id) {
                  <label class="course-option">
                    <input type="checkbox" [checked]="selectedCourseIds.includes(course.id)" (change)="toggleCourse(course.id, $event)" />
                    <span>{{ course.title }}</span>
                  </label>
                }
              </div>
            </div>
            <div class="preferences-grid">
              <label>
                Available study hours per day
                <input type="number" min="0.25" max="16" step="0.25" [(ngModel)]="availableHours" name="availableHours" />
              </label>
              <label>
                Preferred study time
                <select [(ngModel)]="preferredTime" name="preferredTime">
                  <option value="morning">Morning</option>
                  <option value="afternoon">Afternoon</option>
                  <option value="evening">Evening</option>
                  <option value="night">Night</option>
                </select>
              </label>
              <label>
                Daily session duration (minutes)
                <select [(ngModel)]="dailyDuration" name="dailyDuration">
                  <option [ngValue]="15">15 minutes</option>
                  <option [ngValue]="30">30 minutes</option>
                  <option [ngValue]="45">45 minutes</option>
                  <option [ngValue]="60">60 minutes</option>
                  <option [ngValue]="90">90 minutes</option>
                  <option [ngValue]="120">120 minutes</option>
                </select>
              </label>
              <label>
                Target completion date
                <input type="date" [(ngModel)]="targetDate" name="targetDate" />
              </label>
            </div>
            <div class="deadline-form">
              <h3>Upcoming exams or deadlines</h3>
              <div class="deadline-inputs">
                <label>
                  Course
                  <select [(ngModel)]="deadlineCourseId" name="deadlineCourse">
                    @for (course of selectedCourses; track course.id) {
                      <option [ngValue]="course.id">{{ course.title }}</option>
                    }
                  </select>
                </label>
                <label>
                  Title
                  <input type="text" [(ngModel)]="deadlineTitle" name="deadlineTitle" placeholder="e.g. Final exam" />
                </label>
                <label>
                  Type
                  <select [(ngModel)]="deadlineType" name="deadlineType">
                    <option value="exam">Exam</option>
                    <option value="deadline">Other deadline</option>
                  </select>
                </label>
                <label>
                  Date and time
                  <input type="datetime-local" [(ngModel)]="deadlineDate" name="deadlineDate" />
                </label>
                <button class="btn btn-outline" type="button" (click)="addDeadline()" [disabled]="!deadlineCourseId || !deadlineTitle || !deadlineDate">
                  Add deadline
                </button>
              </div>
              @if (deadlines.length > 0) {
                <ul class="deadline-tags">
                  @for (deadline of deadlines; track $index) {
                    <li>
                      <span>{{ deadline.title }} · {{ courseName(deadline.course_id) }} · {{ deadline.due_at | date:'medium' }}</span>
                      <button type="button" (click)="removeDeadline($index)" aria-label="Remove deadline">×</button>
                    </li>
                  }
                </ul>
              }
            </div>
          }
        </section>

        @if (planner; as plan) {
          <section class="metrics-grid">
            <div class="metric card">
              <span class="metric-icon">📈</span>
              <strong>{{ plan.overall_progress }}%</strong>
              <span>Course progress</span>
            </div>
            <div class="metric card">
              <span class="metric-icon">🗓️</span>
              <strong>{{ pendingTasks.length }}</strong>
              <span>Pending sessions</span>
            </div>
            <div class="metric card">
              <span class="metric-icon">✅</span>
              <strong>{{ completedTasks.length }}</strong>
              <span>Completed tasks</span>
            </div>
            <div class="metric card">
              <span class="metric-icon">⚠️</span>
              <strong>{{ missedTasks.length }}</strong>
              <span>Missed tasks</span>
            </div>
          </section>

          <section class="card recommendations-card">
            <div class="section-heading">
              <div>
                <h2>Smart recommendations</h2>
                <p class="muted">Generated from your lessons, scores, deadlines, and task history.</p>
              </div>
            </div>
            @if (plan.recommendations.length) {
              <ul class="recommendations">
                @for (recommendation of plan.recommendations; track recommendation) {
                  <li><span class="sparkle">✦</span>{{ recommendation }}</li>
                }
              </ul>
            } @else {
              <p class="empty-state">Generate a study plan to receive recommendations based on your progress.</p>
            }
          </section>

          @if (plan.reminders.length > 0) {
            <section class="card reminders-card">
              <div class="section-heading"><h2>Study reminders</h2><span class="badge badge-warning">{{ plan.reminders.length }} upcoming</span></div>
              @for (reminder of plan.reminders; track reminder.id) {
                <div class="reminder-row">
                  <div>
                    <strong>{{ reminder.message }}</strong>
                    <span class="muted">{{ reminder.remind_at | date:'medium' }} · {{ reminder.notification_type | titlecase }}</span>
                  </div>
                  <button class="btn btn-sm btn-outline" (click)="markReminderRead(reminder.id)">Dismiss</button>
                </div>
              }
            </section>
          }

          @if (plan.course_progress.length > 0) {
            <section class="card progress-card">
              <div class="section-heading"><h2>Course-wise progress</h2></div>
              @for (course of plan.course_progress; track course.course_id) {
                <div class="course-progress">
                  <div class="progress-label"><strong>{{ course.course_name }}</strong><span>{{ course.completed_lessons }}/{{ course.total_lessons }} lessons · {{ course.completion_percentage }}%</span></div>
                  <div class="progress-track"><span [style.width.%]="course.completion_percentage"></span></div>
                </div>
              }
            </section>
          }

          <section class="card timetable-card">
            <div class="section-heading">
              <div><h2>Weekly timetable</h2><p class="muted">Your next seven days, scheduled in your local time.</p></div>
              @if (plan.target_completion_date) { <span class="badge badge-primary">Target {{ plan.target_completion_date | date:'mediumDate' }}</span> }
            </div>
            <div class="week-grid">
              @for (day of weekDays; track day.key) {
                <div class="day-column" [class.today]="day.isToday">
                  <div class="day-header"><strong>{{ day.label }}</strong><span>{{ day.date | date:'MMM d' }}</span></div>
                  @for (task of tasksForDate(day.key); track task.id) {
                    <article class="mini-task" [class.completed]="task.status === 'completed'" [class.missed]="task.status === 'missed'">
                      <span class="mini-time">{{ task.start_time }}–{{ task.end_time }}</span>
                      <strong>{{ task.lesson_name }}</strong>
                      <small>{{ task.course_name }}</small>
                      <span class="badge" [ngClass]="priorityBadge(task.priority)">{{ task.priority | titlecase }}</span>
                    </article>
                  }
                  @if (tasksForDate(day.key).length === 0) { <p class="empty-day">No tasks</p> }
                </div>
              }
            </div>
          </section>

          <section class="card task-list-card">
            <div class="section-heading"><h2>Today's study tasks</h2><span class="badge badge-neutral">{{ todayTasks.length }} scheduled</span></div>
            @if (todayTasks.length === 0) {
              <p class="empty-state">No study tasks scheduled for today.</p>
            } @else {
              @for (task of todayTasks; track task.id) {
                <ng-container *ngTemplateOutlet="taskCard; context: { $implicit: task }"></ng-container>
              }
            }
          </section>

          <section class="card task-list-card">
            <div class="section-heading"><h2>Pending tasks</h2><span class="badge badge-warning">{{ pendingTasks.length }}</span></div>
            @if (pendingTasks.length === 0) { <p class="empty-state">No pending study tasks.</p> }
            @for (task of pendingTasks; track task.id) {
              <ng-container *ngTemplateOutlet="taskCard; context: { $implicit: task }"></ng-container>
            }
          </section>

          <section class="card task-list-card">
            <div class="section-heading"><h2>Completed tasks</h2><span class="badge badge-success">{{ completedTasks.length }}</span></div>
            @if (completedTasks.length === 0) { <p class="empty-state">No completed tasks in this plan yet.</p> }
            @for (task of completedTasks; track task.id) {
              <ng-container *ngTemplateOutlet="taskCard; context: { $implicit: task }"></ng-container>
            }
          </section>

          <section class="card task-list-card">
            <div class="section-heading"><h2>Missed tasks</h2><span class="badge badge-danger">{{ missedTasks.length }}</span></div>
            @if (missedTasks.length === 0) { <p class="empty-state">You have no missed study tasks.</p> }
            @for (task of missedTasks; track task.id) {
              <ng-container *ngTemplateOutlet="taskCard; context: { $implicit: task }"></ng-container>
            }
          </section>

          <ng-template #taskCard let-task>
            <article class="task-row">
              <div class="task-main">
                <div class="task-title">
                  <strong>{{ task.lesson_name }}</strong>
                  <span class="badge" [ngClass]="statusBadge(task.status)">{{ task.status | titlecase }}</span>
                  <span class="badge" [ngClass]="priorityBadge(task.priority)">{{ task.priority | titlecase }} priority</span>
                </div>
                <span class="muted">{{ task.course_name }}{{ task.section_name ? ' · ' + task.section_name : '' }} · {{ task.scheduled_at | date:'medium' }} · {{ task.duration_minutes }} min</span>
                <p>{{ task.rationale }}</p>
                @if (reschedulingTaskId === task.id) {
                  <div class="reschedule-controls">
                    <input type="datetime-local" [(ngModel)]="rescheduleInput" [ngModelOptions]="{standalone: true}" />
                    <button class="btn btn-sm btn-primary" (click)="rescheduleTask(task)" [disabled]="busy">Save new time</button>
                    <button class="btn btn-sm btn-outline" (click)="reschedulingTaskId = null">Cancel</button>
                  </div>
                }
              </div>
              <div class="task-actions">
                @if (task.status === 'pending') {
                  <button class="btn btn-sm btn-outline" (click)="prepareReschedule(task)">Reschedule</button>
                  <button class="btn btn-sm btn-primary" (click)="completeTask(task)" [disabled]="busy">Complete</button>
                } @else if (task.status === 'missed') {
                  <button class="btn btn-sm btn-outline" (click)="prepareReschedule(task)">Reschedule</button>
                }
                <button class="btn btn-sm btn-danger-outline" (click)="deleteTask(task)" [disabled]="busy">Delete</button>
              </div>
            </article>
          </ng-template>
        }
      </div>
    </div>
  `,
  styles: [`
    .planner-page { min-height:calc(100vh - 120px); padding:2rem 0 4rem; }
    .student-nav-bar { display:flex; gap:.6rem; margin-bottom:2rem; padding-bottom:.85rem; border-bottom:1px solid var(--border-light); overflow-x:auto; }
    .nav-pill { white-space:nowrap; padding:.55rem 1rem; border:1px solid var(--border-color); border-radius:999px; background:#fff; color:var(--text-muted); text-decoration:none; font-weight:600; }
    .nav-pill.active { color:#fff; background:var(--primary); border-color:var(--primary); }
    .page-header,.section-heading { display:flex; justify-content:space-between; align-items:center; gap:1rem; }
    .page-header { margin-bottom:1.5rem; }
    h1 { margin:.25rem 0; font-size:2rem; }
    h2 { margin:.2rem 0 .45rem; }
    h3 { margin:.3rem 0 .75rem; }
    .eyebrow { color:var(--primary); font-size:.78rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
    .muted { color:var(--text-muted); }
    .card { padding:1.4rem; margin-bottom:1.25rem; }
    .setup-actions { display:flex; gap:.55rem; flex-wrap:wrap; }
    .course-picker { margin:1.25rem 0; }
    .field-label { display:block; font-weight:700; margin-bottom:.55rem; }
    .course-options { display:flex; flex-wrap:wrap; gap:.6rem; }
    .course-option { display:flex; align-items:center; gap:.5rem; padding:.7rem .85rem; border:1px solid var(--border-color); border-radius:var(--radius-md); cursor:pointer; }
    .course-option input { accent-color:var(--primary); }
    .preferences-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:1rem; margin:1.25rem 0; }
    label { display:grid; gap:.45rem; font-weight:650; }
    input,select { width:100%; min-height:42px; padding:.65rem; border:1px solid var(--border-color); border-radius:var(--radius-md); background:#fff; color:var(--text-primary); font:inherit; }
    .deadline-form { border-top:1px solid var(--border-light); padding-top:1rem; }
    .deadline-inputs { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); align-items:end; gap:.75rem; }
    .deadline-tags { display:flex; flex-wrap:wrap; gap:.5rem; list-style:none; padding:0; }
    .deadline-tags li { display:flex; gap:.5rem; align-items:center; padding:.35rem .65rem; border-radius:999px; background:var(--bg-subtle); }
    .deadline-tags button { border:0; background:transparent; color:var(--text-muted); cursor:pointer; font-size:1.1rem; }
    .metrics-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:1rem; margin-bottom:1.25rem; }
    .metric { display:grid; gap:.2rem; text-align:center; }
    .metric-icon { font-size:1.4rem; }
    .metric strong { font-size:1.5rem; color:var(--primary); }
    .metric span:last-child { color:var(--text-muted); font-size:.86rem; }
    .recommendations { display:grid; gap:.7rem; list-style:none; padding:0; margin:.5rem 0 0; }
    .recommendations li { display:flex; gap:.7rem; align-items:flex-start; padding:.75rem; border-radius:var(--radius-md); background:var(--bg-subtle); }
    .sparkle { color:var(--primary); font-size:1.2rem; }
    .reminder-row { display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:.75rem 0; border-top:1px solid var(--border-light); }
    .reminder-row div { display:grid; gap:.3rem; }
    .course-progress { margin:1rem 0; }
    .progress-label { display:flex; justify-content:space-between; gap:1rem; font-size:.9rem; }
    .progress-track { height:9px; margin-top:.5rem; overflow:hidden; background:var(--bg-subtle); border-radius:10px; }
    .progress-track span { display:block; height:100%; background:var(--primary); }
    .week-grid { display:grid; grid-template-columns:repeat(7,minmax(145px,1fr)); gap:.65rem; overflow-x:auto; margin-top:1rem; padding-bottom:.4rem; }
    .day-column { min-height:155px; padding:.65rem; border:1px solid var(--border-light); border-radius:var(--radius-md); background:#fff; }
    .day-column.today { border-color:var(--primary); box-shadow:0 0 0 1px var(--primary); }
    .day-header { display:flex; justify-content:space-between; gap:.4rem; margin-bottom:.6rem; font-size:.78rem; }
    .mini-task { display:grid; gap:.2rem; padding:.55rem; margin:.45rem 0; border-radius:var(--radius-sm); background:var(--bg-subtle); font-size:.76rem; }
    .mini-task.completed { opacity:.65; }
    .mini-task.missed { border-left:3px solid #e11d48; }
    .mini-task small,.mini-time { color:var(--text-muted); }
    .empty-day,.empty-state { color:var(--text-muted); text-align:center; padding:.8rem; }
    .task-row { display:flex; justify-content:space-between; gap:1.25rem; padding:1rem 0; border-top:1px solid var(--border-light); }
    .task-main { min-width:0; }
    .task-main p { color:var(--text-muted); margin:.5rem 0 0; font-size:.87rem; }
    .task-title { display:flex; align-items:center; flex-wrap:wrap; gap:.5rem; margin-bottom:.4rem; }
    .task-actions,.reschedule-controls { display:flex; flex-wrap:wrap; align-items:center; gap:.5rem; }
    .task-actions { align-content:flex-start; justify-content:flex-end; min-width:230px; }
    .reschedule-controls { margin-top:.75rem; }
    .reschedule-controls input { max-width:230px; }
    .alert { padding:.9rem 1rem; border-radius:var(--radius-md); margin-bottom:1rem; }
    .alert.error { color:#9f1239; background:#fff1f2; border:1px solid #fecdd3; }
    .alert.success { color:#166534; background:#f0fdf4; border:1px solid #bbf7d0; }
    .alert.fallback-notice { color:#854d0e; background:#fefce8; border:1px solid #fde68a; }
    .btn-danger-outline { border:1px solid #fda4af; background:#fff; color:#be123c; border-radius:var(--radius-md); padding:.45rem .7rem; }
    @media (max-width:900px) { .metrics-grid { grid-template-columns:repeat(2,1fr); } .week-grid { grid-template-columns:repeat(7,155px); } }
    @media (max-width:620px) {
      .page-header,.section-heading { align-items:flex-start; flex-direction:column; }
      .task-row,.reminder-row { flex-direction:column; }
      .task-actions { justify-content:flex-start; min-width:0; }
      .card { padding:1rem; }
    }
  `]
})
export class AIStudyPlannerComponent implements OnInit {
  courses: AICourseOutline[] = [];
  planner: StudyPlannerDashboard | null = null;
  selectedCourseIds: number[] = [];
  availableHours = 2;
  preferredTime: PreferredStudyTime = 'evening';
  dailyDuration = 30;
  targetDate = this.dateAfter(14);
  readonly timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  deadlines: AIPlannerDeadline[] = [];
  deadlineCourseId: number | null = null;
  deadlineTitle = '';
  deadlineType: 'exam' | 'deadline' = 'exam';
  deadlineDate = '';
  reschedulingTaskId: number | null = null;
  rescheduleInput = '';
  busy = false;
  errorMessage = '';
  noticeMessage = '';

  constructor(private aiLearning: AILearningService) {}

  ngOnInit(): void {
    this.aiLearning.getCourses().subscribe({
      next: (courses) => {
        this.courses = courses;
        this.deadlineCourseId = courses[0]?.id ?? null;
        if (this.selectedCourseIds.length === 0) this.selectedCourseIds = courses.map((course) => course.id);
      },
      error: (error: HttpErrorResponse) => this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not load enrolled courses.'),
    });
    this.loadPlanner();
  }

  get selectedCourses(): AICourseOutline[] {
    return this.courses.filter((course) => this.selectedCourseIds.includes(course.id));
  }

  get todayTasks(): StudyTask[] {
    const today = this.dateKey(new Date());
    return (this.planner?.tasks ?? []).filter((task) => task.scheduled_date === today);
  }

  get pendingTasks(): StudyTask[] {
    return (this.planner?.tasks ?? []).filter((task) => task.status === 'pending');
  }

  get completedTasks(): StudyTask[] {
    return (this.planner?.tasks ?? []).filter((task) => task.status === 'completed');
  }

  get missedTasks(): StudyTask[] {
    return (this.planner?.tasks ?? []).filter((task) => task.status === 'missed');
  }

  get weekDays(): { key: string; date: Date; label: string; isToday: boolean }[] {
    return Array.from({ length: 7 }, (_, index) => {
      const date = new Date();
      date.setHours(0, 0, 0, 0);
      date.setDate(date.getDate() + index);
      return {
        key: this.dateKey(date),
        date,
        label: date.toLocaleDateString(undefined, { weekday: 'short' }),
        isToday: index === 0,
      };
    });
  }

  toggleCourse(courseId: number, event: Event): void {
    const selected = (event.target as HTMLInputElement).checked;
    this.selectedCourseIds = selected
      ? [...this.selectedCourseIds, courseId]
      : this.selectedCourseIds.filter((id) => id !== courseId);
    if (this.deadlineCourseId && !this.selectedCourseIds.includes(this.deadlineCourseId)) {
      this.deadlineCourseId = this.selectedCourseIds[0] ?? null;
    }
    this.deadlines = this.deadlines.filter((item) => this.selectedCourseIds.includes(item.course_id));
  }

  addDeadline(): void {
    if (!this.deadlineCourseId || !this.deadlineTitle.trim() || !this.deadlineDate) return;
    const dueAt = new Date(this.deadlineDate);
    if (Number.isNaN(dueAt.getTime())) return;
    this.deadlines = [
      ...this.deadlines,
      {
        course_id: this.deadlineCourseId,
        title: this.deadlineTitle.trim(),
        deadline_type: this.deadlineType,
        due_at: dueAt.toISOString(),
      },
    ];
    this.deadlineTitle = '';
    this.deadlineDate = '';
  }

  removeDeadline(index: number): void {
    this.deadlines = this.deadlines.filter((_, current) => current !== index);
  }

  courseName(courseId: number): string {
    return this.courses.find((course) => course.id === courseId)?.title ?? 'Course';
  }

  tasksForDate(date: string): StudyTask[] {
    return (this.planner?.tasks ?? []).filter((task) => task.scheduled_date === date);
  }

  generatePlan(): void {
    const payload = this.buildRequest();
    if (!payload) return;
    this.busy = true;
    this.errorMessage = '';
    this.noticeMessage = '';
    this.aiLearning.generatePlan(payload).subscribe({
      next: (planner) => {
        this.planner = planner;
        this.deadlines = planner.deadlines ?? [];
        this.selectedCourseIds = planner.preferences?.course_ids ?? this.selectedCourseIds;
        this.busy = false;
        this.noticeMessage = planner.generation_mode === 'rules'
          ? 'Your study plan was created from your recorded course progress and deadlines using the rule-based scheduler.'
          : 'Your AI-personalized study plan is ready.';
      },
      error: (error: HttpErrorResponse) => {
        this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not generate the study plan.');
        this.busy = false;
      },
    });
  }

  savePreferences(): void {
    const payload = this.buildRequest();
    if (!payload) return;
    this.busy = true;
    this.errorMessage = '';
    this.aiLearning.savePreferences(payload).subscribe({
      next: (preference) => {
        this.deadlines = preference.deadlines ?? [];
        if (this.planner) this.planner.preferences = preference;
        this.noticeMessage = 'Study preferences saved.';
        this.busy = false;
      },
      error: (error: HttpErrorResponse) => {
        this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not save your study preferences.');
        this.busy = false;
      },
    });
  }

  completeTask(task: StudyTask): void {
    this.busy = true;
    this.aiLearning.completeTask(task.id).subscribe({
      next: () => this.loadPlanner(),
      error: (error: HttpErrorResponse) => {
        this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not mark the task complete.');
        this.busy = false;
      },
    });
  }

  prepareReschedule(task: StudyTask): void {
    this.reschedulingTaskId = task.id;
    const date = new Date(task.scheduled_at);
    date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    this.rescheduleInput = date.toISOString().slice(0, 16);
  }

  rescheduleTask(task: StudyTask): void {
    if (!this.rescheduleInput) return;
    this.busy = true;
    this.aiLearning.rescheduleTask(task.id, new Date(this.rescheduleInput).toISOString()).subscribe({
      next: () => {
        this.reschedulingTaskId = null;
        this.loadPlanner();
      },
      error: (error: HttpErrorResponse) => {
        this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not reschedule this task.');
        this.busy = false;
      },
    });
  }

  deleteTask(task: StudyTask): void {
    if (!window.confirm(`Delete the study task "${task.lesson_name}"?`)) return;
    this.busy = true;
    this.aiLearning.deleteTask(task.id).subscribe({
      next: () => this.loadPlanner(),
      error: (error: HttpErrorResponse) => {
        this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not delete this study task.');
        this.busy = false;
      },
    });
  }

  markReminderRead(reminderId: number): void {
    this.aiLearning.markReminderRead(reminderId).subscribe({
      next: () => {
        if (this.planner) this.planner.reminders = this.planner.reminders.filter((item) => item.id !== reminderId);
      },
      error: (error: HttpErrorResponse) => this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not dismiss this reminder.'),
    });
  }

  priorityBadge(priority: string): string {
    return priority === 'high' ? 'badge-danger' : priority === 'medium' ? 'badge-warning' : 'badge-neutral';
  }

  statusBadge(status: string): string {
    return status === 'completed' ? 'badge-success' : status === 'missed' ? 'badge-danger' : 'badge-warning';
  }

  private loadPlanner(): void {
    this.aiLearning.getPlanner().subscribe({
      next: (planner) => {
        this.planner = planner;
        this.deadlines = planner.deadlines ?? planner.preferences?.deadlines ?? [];
        const preference = planner.preferences;
        if (preference) {
          this.selectedCourseIds = preference.course_ids;
          this.availableHours = preference.available_hours_per_day;
          this.preferredTime = preference.preferred_time;
          this.dailyDuration = preference.daily_duration_minutes;
          this.targetDate = preference.target_completion_date ?? this.targetDate;
        }
        this.busy = false;
      },
      error: (error: HttpErrorResponse) => {
        this.errorMessage = this.aiLearning.getErrorMessage(error, 'Could not load the study planner.');
        this.busy = false;
      },
    });
  }

  private buildRequest(): StudyPlanRequest | null {
    if (this.selectedCourseIds.length === 0) {
      this.errorMessage = 'Select at least one approved course.';
      return null;
    }
    if (!this.targetDate) {
      this.errorMessage = 'Choose a target completion date.';
      return null;
    }
    return {
      course_ids: this.selectedCourseIds,
      available_hours_per_day: Number(this.availableHours),
      preferred_time: this.preferredTime,
      time_zone: this.timeZone,
      daily_duration_minutes: Number(this.dailyDuration),
      target_completion_date: this.targetDate,
      deadlines: this.deadlines,
    };
  }

  private dateAfter(days: number): string {
    const date = new Date();
    date.setDate(date.getDate() + days);
    return this.dateKey(date);
  }

  private dateKey(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

}
