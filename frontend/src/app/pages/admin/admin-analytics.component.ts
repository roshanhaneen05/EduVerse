import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AdminAnalyticsDashboard, MonthlyAnalyticsPoint } from '../../core/models/admin-analytics.model';
import { AdminService } from '../../core/services/admin.service';

type DateRangePreset = '7d' | '30d' | '3m' | '6m' | '1y' | 'custom';

@Component({
  selector: 'app-admin-analytics',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <main class="analytics-page">
      <div class="container">
        <header class="page-header">
          <div>
            <a routerLink="/admin/dashboard" class="back-link">← Administrator dashboard</a>
            <span class="eyebrow">Platform intelligence</span>
            <h1>Advanced Admin Analytics</h1>
            <p class="subtitle">Database-backed insight into learners, courses, instructors, and engagement.</p>
          </div>
          <div class="header-actions">
            <button type="button" class="btn btn-secondary" (click)="exportReport('csv')" [disabled]="isExporting">
              {{ isExporting ? 'Preparing report…' : 'Download CSV' }}
            </button>
            <button type="button" class="btn btn-primary" (click)="exportReport('pdf')" [disabled]="isExporting">
              Download PDF
            </button>
          </div>
        </header>

        <section class="filter-panel card" aria-label="Analytics date range">
          <div>
            <h2>Reporting period</h2>
            <p>Enrollment and activity metrics use the selected period. Account and course totals are lifetime totals.</p>
          </div>
          <div class="filter-controls">
            <label for="range">Date range</label>
            <select id="range" class="form-input" [(ngModel)]="rangePreset" (ngModelChange)="onRangeChange($event)">
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="3m">Last 3 months</option>
              <option value="6m">Last 6 months</option>
              <option value="1y">Last 1 year</option>
              <option value="custom">Custom range</option>
            </select>
            @if (rangePreset === 'custom') {
              <label class="sr-only" for="custom-start">Start date</label>
              <input id="custom-start" class="form-input date-input" type="date" [(ngModel)]="customStart">
              <label class="sr-only" for="custom-end">End date</label>
              <input id="custom-end" class="form-input date-input" type="date" [(ngModel)]="customEnd">
              <button type="button" class="btn btn-primary" (click)="applyCustomRange()">Apply</button>
            }
          </div>
        </section>

        @if (rangeError) {
          <div class="alert alert-danger" role="alert">{{ rangeError }}</div>
        }
        @if (feedbackMessage) {
          <div class="alert" [class.alert-danger]="feedbackIsError" [class.alert-success]="!feedbackIsError" role="status">
            {{ feedbackMessage }}
          </div>
        }

        @if (isLoading) {
          <div class="loading-state card" role="status">
            <span class="spinner"></span>
            <span>Loading live analytics from EduVerse…</span>
          </div>
        } @else if (errorMessage) {
          <div class="error-state card" role="alert">
            <h2>Analytics are unavailable</h2>
            <p>{{ errorMessage }}</p>
            <button type="button" class="btn btn-primary" (click)="loadAnalytics()">Try again</button>
          </div>
        } @else if (data) {
          <section class="summary-grid" aria-label="Platform overview">
            <article class="summary-card card">
              <span class="summary-icon icon-indigo">🎓</span>
              <div><strong>{{ data.overview.total_registered_students }}</strong><span>Registered students</span></div>
            </article>
            <article class="summary-card card">
              <span class="summary-icon icon-amber">👩‍🏫</span>
              <div><strong>{{ data.overview.total_registered_instructors }}</strong><span>Registered instructors</span></div>
            </article>
            <article class="summary-card card">
              <span class="summary-icon icon-green">📚</span>
              <div><strong>{{ data.overview.total_published_courses }}</strong><span>Published courses</span></div>
            </article>
            <article class="summary-card card">
              <span class="summary-icon icon-blue">🧾</span>
              <div><strong>{{ data.overview.total_enrollments }}</strong><span>Enrollments in period</span></div>
            </article>
            <article class="summary-card card">
              <span class="summary-icon icon-violet">✅</span>
              <div><strong>{{ data.overview.total_completed_courses }}</strong><span>Completed enrollments</span></div>
            </article>
            <article class="summary-card card">
              <span class="summary-icon icon-teal">🟢</span>
              <div><strong>{{ data.overview.total_active_users }}</strong><span>Active user accounts</span></div>
            </article>
          </section>

          <section class="section-block">
            <div class="section-heading">
              <div><h2>Engagement trends</h2><p>Monthly database activity within the selected period.</p></div>
            </div>
            <div class="charts-grid">
              <article class="chart-card card">
                <h3>Student registrations</h3>
                @if (data.trends.monthly.length && hasTrendData('student_registrations')) {
                  <div class="bar-chart" role="img" aria-label="Monthly student registration chart">
                    @for (point of data.trends.monthly; track point.month) {
                      <div class="bar-column" [title]="monthLabel(point.month) + ': ' + point.student_registrations + ' registrations'">
                        <span class="bar-value">{{ point.student_registrations }}</span>
                        <div class="bar-track"><span class="bar-fill fill-indigo" [style.height.%]="barHeight(point.student_registrations, 'student_registrations')"></span></div>
                        <span class="bar-label">{{ monthLabel(point.month) }}</span>
                      </div>
                    }
                  </div>
                } @else { <p class="empty-state">No student registrations in this period.</p> }
              </article>

              <article class="chart-card card">
                <h3>Monthly enrollments</h3>
                @if (data.trends.monthly.length && hasTrendData('enrollments')) {
                  <div class="bar-chart" role="img" aria-label="Monthly enrollment chart">
                    @for (point of data.trends.monthly; track point.month) {
                      <div class="bar-column" [title]="monthLabel(point.month) + ': ' + point.enrollments + ' enrollments'">
                        <span class="bar-value">{{ point.enrollments }}</span>
                        <div class="bar-track"><span class="bar-fill fill-blue" [style.height.%]="barHeight(point.enrollments, 'enrollments')"></span></div>
                        <span class="bar-label">{{ monthLabel(point.month) }}</span>
                      </div>
                    }
                  </div>
                } @else { <p class="empty-state">No enrollments in this period.</p> }
              </article>

              <article class="chart-card card">
                <h3>Course category distribution</h3>
                @if (data.courses.categories.length) {
                  <div class="pie-layout">
                    <div class="pie-chart" [style.background]="categoryPieStyle()" role="img" aria-label="Course category distribution pie chart"></div>
                    <ul class="legend">
                      @for (category of data.courses.categories; track category.category; let i = $index) {
                        <li [title]="category.category + ': ' + category.course_count + ' courses'">
                          <span class="legend-swatch" [style.background]="pieColor(i)"></span>
                          <span>{{ category.category }}</span><strong>{{ category.course_count }}</strong>
                        </li>
                      }
                    </ul>
                  </div>
                } @else { <p class="empty-state">No courses are available to categorize.</p> }
              </article>

              <article class="chart-card card">
                <h3>Course completion rates</h3>
                @if (data.courses.highest_completion_courses.length) {
                  <div class="completion-chart">
                    @for (course of data.courses.highest_completion_courses.slice(0, 8); track course.course_id) {
                      <div class="completion-row" [title]="course.course_name + ': ' + course.completion_rate + '%'">
                        <span class="completion-name">{{ course.course_name }}</span>
                        <span class="completion-track"><span [style.width.%]="course.completion_rate"></span></span>
                        <strong>{{ course.completion_rate }}%</strong>
                      </div>
                    }
                  </div>
                } @else { <p class="empty-state">No course completions in this period.</p> }
              </article>

              <article class="chart-card card chart-wide">
                <h3>Student activity trends</h3>
                @if (data.trends.monthly.length && hasTrendData('active_students')) {
                  <div class="line-chart">
                    <svg viewBox="0 0 600 190" preserveAspectRatio="none" role="img" aria-label="Monthly active student trend">
                      <line x1="20" y1="165" x2="580" y2="165" class="axis-line"></line>
                      <polyline [attr.points]="activityLinePoints()" class="trend-line"></polyline>
                      @for (point of data.trends.monthly; track point.month; let i = $index) {
                        <circle [attr.cx]="lineX(i)" [attr.cy]="lineY(point.active_students)" r="5" class="trend-point">
                          <title>{{ monthLabel(point.month) }}: {{ point.active_students }} active students</title>
                        </circle>
                      }
                    </svg>
                    <div class="line-labels">
                      @for (point of data.trends.monthly; track point.month) { <span>{{ monthLabel(point.month) }}</span> }
                    </div>
                  </div>
                } @else { <p class="empty-state">No lesson activity recorded in this period.</p> }
              </article>
            </div>
          </section>

          <section class="section-block data-grid">
            <article class="data-card card">
              <div class="card-heading"><div><h2>Student analytics</h2><p>{{ data.students.new_student_registrations }} new registrations in range · {{ data.students.active_students }} active · {{ data.students.inactive_students }} inactive accounts · {{ data.students.total_enrollments }} enrollments ({{ data.students.average_enrollments_per_student }} avg/student)</p></div></div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Top-performing student</th><th>Enrollments</th><th>Avg. completion</th></tr></thead>
                  <tbody>
                    @for (student of data.students.top_students; track $index) {
                      <tr><td>{{ student.name }}</td><td>{{ student.enrollment_count }}</td><td>{{ student.average_completion_rate }}%</td></tr>
                    }
                  </tbody>
                </table>
                @if (!data.students.top_students.length) { <p class="empty-state">No student enrollment data in this period.</p> }
              </div>
              <h3 class="subheading">Highest course completion rates</h3>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Student</th><th>Enrollments</th><th>Avg. completion</th></tr></thead>
                  <tbody>
                    @for (student of data.students.highest_completion_students; track $index) {
                      <tr><td>{{ student.name }}</td><td>{{ student.enrollment_count }}</td><td>{{ student.average_completion_rate }}%</td></tr>
                    }
                  </tbody>
                </table>
                @if (!data.students.highest_completion_students.length) { <p class="empty-state">No completion data in this period.</p> }
              </div>
            </article>

            <article class="data-card card">
              <div class="card-heading"><div><h2>Instructor analytics</h2><p>Course ownership and learner enrollments by instructor.</p></div></div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Instructor</th><th>Courses</th><th>Enrollments</th><th>Recent activity*</th></tr></thead>
                  <tbody>
                    @for (instructor of data.instructors.instructors; track $index) {
                      <tr>
                        <td>{{ instructor.name }}</td><td>{{ instructor.course_count }}</td>
                        <td>{{ instructor.student_enrollments }}</td>
                        <td>{{ instructor.period_course_creations + instructor.period_enrollments }}</td>
                      </tr>
                    }
                  </tbody>
                </table>
                @if (!data.instructors.instructors.length) { <p class="empty-state">No instructors registered.</p> }
              </div>
              <p class="table-note">* Recent activity is the count of courses created and enrollments into their courses during the selected period.</p>
              <h3 class="subheading">Most popular instructor courses</h3>
              @if (data.instructors.popular_courses.length) {
                <ul class="compact-list">
                  @for (course of data.instructors.popular_courses.slice(0, 5); track course.course_id) {
                    <li><span>{{ course.course_name }} <small>by {{ course.instructor_name }}</small></span><strong>{{ course.enrollment_count }}</strong></li>
                  }
                </ul>
              } @else { <p class="empty-state">No instructor courses to rank yet.</p> }
            </article>
          </section>

          <section class="section-block card course-section">
            <div class="card-heading">
              <div><h2>Course analytics</h2><p>{{ data.courses.total_courses }} total · {{ data.courses.published_courses }} published · {{ data.courses.unpublished_courses }} unpublished</p></div>
            </div>
            <div class="ranking-grid">
              <article class="ranking-card">
                <h3>Most popular courses</h3>
                @if (data.courses.most_popular_courses.length) {
                  <ul class="compact-list">
                    @for (course of data.courses.most_popular_courses.slice(0, 5); track course.course_id) {
                      <li><span>{{ course.course_name }}</span><strong>{{ course.enrollment_count }} enrollments</strong></li>
                    }
                  </ul>
                } @else { <p class="empty-state">No courses available.</p> }
              </article>
              <article class="ranking-card">
                <h3>Least enrolled courses</h3>
                @if (data.courses.least_enrolled_courses.length) {
                  <ul class="compact-list">
                    @for (course of data.courses.least_enrolled_courses.slice(0, 5); track course.course_id) {
                      <li><span>{{ course.course_name }}</span><strong>{{ course.enrollment_count }} enrollments</strong></li>
                    }
                  </ul>
                } @else { <p class="empty-state">No courses available.</p> }
              </article>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>Course</th><th>Instructor</th><th>Category</th><th>Status</th><th>Enrollments</th><th>Completed</th><th>Completion rate</th></tr></thead>
                <tbody>
                  @for (course of data.courses.courses; track course.course_id) {
                    <tr>
                      <td>{{ course.course_name }}</td><td>{{ course.instructor_name }}</td><td>{{ course.category }}</td>
                      <td><span class="status-pill" [class.published]="course.is_published">{{ course.is_published ? 'Published' : 'Draft' }}</span></td>
                      <td>{{ course.enrollment_count }}</td><td>{{ course.completed_enrollments }}</td><td>{{ course.completion_rate }}%</td>
                    </tr>
                  }
                </tbody>
              </table>
              @if (!data.courses.courses.length) { <p class="empty-state">No courses found.</p> }
            </div>
          </section>

          <section class="section-block card activity-section">
            <div class="card-heading"><div><h2>Recent activities</h2><p>Registrations, course creation, enrollments, and course completions.</p></div></div>
            @if (data.recent_activities.length) {
              <ul class="activity-list">
                @for (activity of data.recent_activities; track activity.activity_type + activity.date + activity.activity_name) {
                  <li>
                    <span class="activity-dot" [class.completion]="activity.activity_type === 'course_completed'"></span>
                    <span class="activity-kind">{{ activity.activity_name }}</span>
                    <strong>{{ activity.user_name }}</strong>
                    <time [attr.datetime]="activity.date">{{ activity.date | date:'medium' }}</time>
                  </li>
                }
              </ul>
            } @else { <p class="empty-state">No activities were recorded in this period.</p> }
          </section>
        }
      </div>
    </main>
  `,
  styles: [`
    .analytics-page { min-height: calc(100vh - 120px); padding: 2rem 0 4rem; color: #172033; }
    .page-header { display: flex; justify-content: space-between; align-items: flex-end; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
    .back-link { display: block; width: fit-content; color: var(--primary); font-weight: 650; margin-bottom: 1rem; text-decoration: none; }
    .eyebrow { display: block; color: #6554c0; font-size: .78rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
    h1 { margin: .25rem 0 .45rem; color: #111827; font-size: clamp(1.8rem, 4vw, 2.45rem); letter-spacing: -.035em; }
    .subtitle, .section-heading p, .card-heading p, .filter-panel p { margin: 0; color: var(--text-muted); font-size: .92rem; }
    .header-actions, .filter-controls { display: flex; gap: .65rem; align-items: center; flex-wrap: wrap; }
    .filter-panel { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1.25rem; padding: 1.15rem 1.35rem; margin-bottom: 1.25rem; }
    .filter-panel h2 { font-size: 1rem; margin: 0 0 .25rem; }
    .filter-panel p { max-width: 550px; font-size: .8rem; }
    .filter-controls label { font-size: .82rem; font-weight: 700; }
    .filter-controls .form-input { min-width: 150px; }
    .date-input { max-width: 155px; }
    .summary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; }
    .summary-card { display: flex; gap: .9rem; align-items: center; padding: 1.1rem; border: 1px solid #e8eaf2; }
    .summary-card > div { display: flex; flex-direction: column; min-width: 0; }
    .summary-card strong { color: #111827; font-size: 1.8rem; line-height: 1.1; }
    .summary-card div span { color: var(--text-muted); font-size: .82rem; margin-top: .2rem; }
    .summary-icon { width: 43px; height: 43px; display: grid; place-items: center; border-radius: 12px; font-size: 1.25rem; flex: 0 0 auto; }
    .icon-indigo { background: #e9e7ff; } .icon-amber { background: #fff2d6; } .icon-green { background: #e0f7e9; }
    .icon-blue { background: #e2efff; } .icon-violet { background: #f1e7ff; } .icon-teal { background: #dff7f5; }
    .section-block { margin-top: 2rem; }
    .section-heading, .card-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; margin-bottom: .95rem; }
    .section-heading h2, .card-heading h2 { margin: 0 0 .22rem; font-size: 1.28rem; }
    .section-heading p, .card-heading p { font-size: .82rem; }
    .charts-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
    .chart-card { min-width: 0; padding: 1.2rem; border: 1px solid #e8eaf2; }
    .chart-card h3, .subheading { font-size: .98rem; margin: 0 0 1rem; }
    .chart-wide { grid-column: 1 / -1; }
    .bar-chart { display: flex; align-items: flex-end; gap: .45rem; min-height: 195px; padding-top: 1.4rem; overflow-x: auto; }
    .bar-column { display: flex; align-items: center; flex-direction: column; gap: .35rem; flex: 1 0 34px; min-width: 34px; height: 185px; }
    .bar-value { font-size: .68rem; color: #465166; }
    .bar-track { height: 125px; width: min(100%, 28px); display: flex; align-items: flex-end; background: #f0f2f7; border-radius: 6px 6px 0 0; overflow: hidden; }
    .bar-fill { width: 100%; min-height: 2px; border-radius: 6px 6px 0 0; transition: height .25s ease; }
    .fill-indigo { background: #7164d8; } .fill-blue { background: #3687db; }
    .bar-label { font-size: .66rem; color: var(--text-muted); white-space: nowrap; }
    .pie-layout { display: flex; align-items: center; justify-content: center; gap: 1.5rem; min-height: 175px; }
    .pie-chart { width: 148px; height: 148px; border-radius: 50%; flex: 0 0 auto; box-shadow: inset 0 0 0 1px rgba(0,0,0,.04); }
    .legend { list-style: none; margin: 0; padding: 0; display: grid; gap: .55rem; }
    .legend li { display: grid; grid-template-columns: 12px minmax(60px, auto) auto; align-items: center; gap: .45rem; font-size: .78rem; }
    .legend li strong { color: #465166; }
    .legend-swatch { width: 10px; height: 10px; border-radius: 3px; }
    .completion-chart { display: grid; gap: .72rem; }
    .completion-row { display: grid; grid-template-columns: minmax(90px, 1.2fr) minmax(70px, 2fr) 42px; align-items: center; gap: .65rem; font-size: .75rem; }
    .completion-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .completion-track { height: 9px; border-radius: 10px; background: #edf0f6; overflow: hidden; }
    .completion-track span { display: block; height: 100%; background: linear-gradient(90deg, #32b78a, #62d6ab); border-radius: inherit; }
    .completion-row strong { text-align: right; }
    .line-chart svg { width: 100%; height: 180px; overflow: visible; }
    .axis-line { stroke: #dfe3ed; stroke-width: 1; }
    .trend-line { fill: none; stroke: #675bd1; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }
    .trend-point { fill: #fff; stroke: #675bd1; stroke-width: 3; }
    .line-labels { display: flex; justify-content: space-between; gap: .4rem; overflow: hidden; color: var(--text-muted); font-size: .68rem; }
    .line-labels span { white-space: nowrap; }
    .data-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
    .data-card, .course-section, .activity-section { padding: 1.25rem; border: 1px solid #e8eaf2; min-width: 0; }
    .data-card .subheading { margin-top: 1.15rem; }
    .ranking-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .9rem; margin: 0 0 1rem; }
    .ranking-card { min-width: 0; border: 1px solid #edf0f5; border-radius: 10px; padding: .9rem; }
    .ranking-card h3 { margin: 0 0 .45rem; font-size: .9rem; }
    .compact-list { list-style: none; margin: 0; padding: 0; }
    .compact-list li { display: flex; justify-content: space-between; gap: .75rem; align-items: flex-start; padding: .55rem 0; border-bottom: 1px solid #edf0f5; font-size: .78rem; }
    .compact-list li:last-child { border-bottom: 0; }
    .compact-list li strong { white-space: nowrap; color: #4a5266; }
    .compact-list small { display: block; color: var(--text-muted); margin-top: .15rem; }
    .table-wrap { width: 100%; overflow-x: auto; }
    table { border-collapse: collapse; width: 100%; font-size: .81rem; }
    th, td { padding: .68rem .55rem; border-bottom: 1px solid #edf0f5; text-align: left; white-space: nowrap; }
    th { color: #586174; font-size: .72rem; font-weight: 750; background: #fafbfe; }
    td { color: #293348; }
    .table-note { color: var(--text-muted); font-size: .73rem; margin: .75rem 0 0; }
    .status-pill { display: inline-block; padding: .2rem .55rem; color: #925b0b; background: #fff2d6; border-radius: 20px; font-size: .7rem; font-weight: 700; }
    .status-pill.published { color: #16794a; background: #e0f7e9; }
    .course-section .card-heading { margin-bottom: .5rem; }
    .activity-list { list-style: none; margin: 0; padding: 0; }
    .activity-list li { display: grid; grid-template-columns: 10px minmax(140px, 1fr) minmax(100px, .7fr) auto; align-items: center; gap: .8rem; padding: .8rem .1rem; border-bottom: 1px solid #edf0f5; font-size: .82rem; }
    .activity-list li:last-child { border-bottom: 0; }
    .activity-dot { width: 9px; height: 9px; border-radius: 50%; background: #6960d3; }
    .activity-dot.completion { background: #24a36b; }
    .activity-kind { color: #3b465b; }
    .activity-list time { color: var(--text-muted); font-size: .74rem; white-space: nowrap; }
    .empty-state { color: var(--text-muted); font-size: .84rem; text-align: center; padding: 1.2rem .5rem; margin: 0; }
    .loading-state, .error-state { display: flex; justify-content: center; align-items: center; gap: .8rem; padding: 4rem 1rem; margin-top: 1rem; color: var(--text-muted); }
    .error-state { flex-direction: column; text-align: center; }
    .error-state h2 { color: #a42b31; margin: 0; }
    .error-state p { margin: 0 0 .5rem; }
    .spinner { width: 25px; height: 25px; border: 3px solid #e3e5ee; border-top-color: var(--primary); border-radius: 50%; animation: spin .8s linear infinite; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (max-width: 800px) {
      .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .data-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 620px) {
      .charts-grid { grid-template-columns: 1fr; }
      .ranking-grid { grid-template-columns: 1fr; }
      .chart-wide { grid-column: auto; }
      .summary-card { padding: .85rem; gap: .6rem; }
      .summary-icon { width: 36px; height: 36px; font-size: 1rem; }
      .summary-card strong { font-size: 1.5rem; }
      .filter-panel { align-items: flex-start; }
      .filter-controls { width: 100%; }
      .filter-controls .form-input { flex: 1; }
      .pie-layout { gap: .8rem; }
      .pie-chart { width: 125px; height: 125px; }
      .activity-list li { grid-template-columns: 10px 1fr auto; }
      .activity-kind { grid-column: 2; }
      .activity-list strong { grid-column: 2; }
      .activity-list time { grid-column: 3; grid-row: 1 / span 2; }
    }
  `]
})
export class AdminAnalyticsComponent implements OnInit {
  data: AdminAnalyticsDashboard | null = null;
  rangePreset: DateRangePreset = '30d';
  customStart = '';
  customEnd = '';
  startDate = '';
  endDate = '';
  isLoading = true;
  isExporting = false;
  errorMessage = '';
  feedbackMessage = '';
  feedbackIsError = false;
  rangeError = '';

  private readonly colors = ['#7164d8', '#2f8bd8', '#2eae7a', '#f0a63b', '#e26a8a', '#2da7a3', '#8792a8'];

  constructor(private readonly adminService: AdminService) {}

  ngOnInit(): void {
    this.setPresetDates('30d');
    this.loadAnalytics();
  }

  onRangeChange(preset: DateRangePreset): void {
    this.rangeError = '';
    if (preset === 'custom') {
      this.customStart = this.startDate;
      this.customEnd = this.endDate;
      return;
    }
    this.setPresetDates(preset);
    this.loadAnalytics();
  }

  applyCustomRange(): void {
    if (!this.customStart || !this.customEnd || this.customStart > this.customEnd) {
      this.rangeError = 'Choose a valid custom range with a start date on or before the end date.';
      return;
    }
    this.rangeError = '';
    this.startDate = this.customStart;
    this.endDate = this.customEnd;
    this.loadAnalytics();
  }

  loadAnalytics(): void {
    this.isLoading = true;
    this.errorMessage = '';
    this.adminService.getAnalyticsDashboard(this.startDate, this.endDate).subscribe({
      next: (data) => {
        this.data = data;
        this.isLoading = false;
      },
      error: (error) => {
        this.isLoading = false;
        this.errorMessage = error.error?.detail || 'Could not load analytics. Please try again.';
      }
    });
  }

  exportReport(format: 'csv' | 'pdf'): void {
    if (this.isExporting) {
      return;
    }
    this.isExporting = true;
    this.feedbackMessage = '';
    this.adminService.exportAnalytics(format, this.startDate, this.endDate).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `eduverse-analytics.${format}`;
        anchor.click();
        window.URL.revokeObjectURL(url);
        this.isExporting = false;
        this.feedbackMessage = `${format.toUpperCase()} report downloaded.`;
        this.feedbackIsError = false;
      },
      error: () => {
        this.isExporting = false;
        this.feedbackMessage = `Could not export the ${format.toUpperCase()} report. Please try again.`;
        this.feedbackIsError = true;
      }
    });
  }

  hasTrendData(key: 'student_registrations' | 'enrollments' | 'active_students'): boolean {
    return !!this.data?.trends.monthly.some((point) => point[key] > 0);
  }

  barHeight(value: number, key: 'student_registrations' | 'enrollments'): number {
    const points = this.data?.trends.monthly ?? [];
    const max = Math.max(1, ...points.map((point) => point[key]));
    return value === 0 ? 0 : Math.max(5, (value / max) * 100);
  }

  monthLabel(month: string): string {
    const [year, value] = month.split('-').map(Number);
    return new Date(year, value - 1, 1).toLocaleDateString(undefined, { month: 'short', year: '2-digit' });
  }

  pieColor(index: number): string {
    return this.colors[index % this.colors.length];
  }

  categoryPieStyle(): string {
    const categories = this.data?.courses.categories ?? [];
    const total = categories.reduce((sum, item) => sum + item.course_count, 0);
    if (!total) {
      return '#edf0f6';
    }
    let start = 0;
    const stops = categories.map((item, index) => {
      const end = start + (item.course_count / total) * 100;
      const segment = `${this.pieColor(index)} ${start}% ${end}%`;
      start = end;
      return segment;
    });
    return `conic-gradient(${stops.join(', ')})`;
  }

  activityLinePoints(): string {
    const points = this.data?.trends.monthly ?? [];
    return points.map((point, index) => `${this.lineX(index)},${this.lineY(point.active_students)}`).join(' ');
  }

  lineX(index: number): number {
    const count = this.data?.trends.monthly.length ?? 1;
    return count < 2 ? 300 : 24 + index * (552 / (count - 1));
  }

  lineY(value: number): number {
    const points: MonthlyAnalyticsPoint[] = this.data?.trends.monthly ?? [];
    const max = Math.max(1, ...points.map((point) => point.active_students));
    return 160 - (value / max) * 130;
  }

  private setPresetDates(preset: Exclude<DateRangePreset, 'custom'>): void {
    const end = new Date();
    const start = new Date(end);
    if (preset === '7d') {
      start.setDate(start.getDate() - 6);
    } else if (preset === '30d') {
      start.setDate(start.getDate() - 29);
    } else if (preset === '3m') {
      start.setMonth(start.getMonth() - 3);
    } else if (preset === '6m') {
      start.setMonth(start.getMonth() - 6);
    } else {
      start.setFullYear(start.getFullYear() - 1);
    }
    this.startDate = this.localDate(start);
    this.endDate = this.localDate(end);
  }

  private localDate(value: Date): string {
    const year = value.getFullYear();
    const month = `${value.getMonth() + 1}`.padStart(2, '0');
    const day = `${value.getDate()}`.padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
}
