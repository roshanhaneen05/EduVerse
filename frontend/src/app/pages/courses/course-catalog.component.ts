import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { CourseService } from '../../core/services/course.service';
import { Course } from '../../core/models/course.model';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-course-catalog',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="catalog-page">
      <div class="container">
        <!-- Page Header -->
        <div class="page-header">
          <div class="header-content">
            <h1>Explore Curated Courses</h1>
            <p class="subtitle">
              Expand your engineering expertise with structured curricula, hands-on lessons, and validated assessments.
            </p>
          </div>
        </div>

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
              (keyup.enter)="applyFilters()"
              placeholder="Search by topic, keyword, or framework..."
            />
            @if (searchQuery) {
              <button class="clear-search" (click)="clearSearch()">✕</button>
            }
          </div>

          <div class="filter-group">
            <label class="filter-label">Category:</label>
            <select class="form-select filter-select" [(ngModel)]="selectedCategory" (change)="applyFilters()">
              <option value="">All Categories</option>
              <option *ngFor="let cat of categories" [value]="cat">{{ cat }}</option>
            </select>
          </div>

          <div class="filter-group">
            <label class="filter-label">Level:</label>
            <select class="form-select filter-select" [(ngModel)]="selectedDifficulty" (change)="applyFilters()">
              <option value="">All Levels</option>
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </div>

          <button (click)="applyFilters()" class="btn btn-primary search-btn">
            Search
          </button>
        </div>

        <!-- Results Grid -->
        @if (isLoading) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading courses...</span>
          </div>
        } @else if (courses.length === 0) {
          <div class="empty-state card">
            <div class="empty-icon">🔍</div>
            <h3>No courses found</h3>
            <p>Try adjusting your search criteria or filter selections.</p>
            <button (click)="resetFilters()" class="btn btn-outline">Reset Filters</button>
          </div>
        } @else {
          <div class="catalog-summary">
            <span>Showing <strong>{{ courses.length }}</strong> available courses</span>
          </div>

          <div class="courses-grid">
            @for (course of courses; track course.id) {
              <div class="course-card card">
                <div class="course-card-top">
                  <div class="badges-row">
                    <span class="badge badge-primary">{{ course.category }}</span>
                    <span class="badge" [ngClass]="getDifficultyBadge(course.difficulty)">
                      {{ course.difficulty }}
                    </span>
                  </div>
                  <h3 class="course-title">
                    <a [routerLink]="['/courses', course.id]">{{ course.title }}</a>
                  </h3>
                  <p class="course-desc">{{ course.description }}</p>
                </div>

                <div class="course-card-middle">
                  <div class="meta-row">
                    <div class="meta-item">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                      </svg>
                      <span>{{ course.lesson_count }} Lessons</span>
                    </div>
                    <div class="meta-item">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                      </svg>
                      <span>{{ course.quiz_count }} Quizzes</span>
                    </div>
                  </div>
                </div>

                <div class="course-card-bottom">
                  <div class="instructor-cell">
                    <span class="inst-label">Instructor</span>
                    <span class="inst-name">{{ course.instructor?.full_name || 'EduVerse Instructor' }}</span>
                  </div>

                  <a [routerLink]="['/courses', course.id]" class="btn btn-sm btn-primary">
                    View Course →
                  </a>
                </div>
              </div>
            }
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .catalog-page {
      padding: 2.5rem 0 4rem 0;
      min-height: calc(100vh - 120px);
    }
    .page-header {
      margin-bottom: 2rem;
    }
    .page-header h1 {
      font-size: 2.25rem;
      color: #0f172a;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 0.5rem;
    }
    .subtitle {
      color: var(--text-muted);
      font-size: 1.05rem;
      max-width: 700px;
    }
    .toolbar {
      display: flex;
      align-items: center;
      gap: 1.25rem;
      padding: 1.35rem 1.6rem;
      margin-bottom: 2.25rem;
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 4px 18px rgba(99, 102, 241, 0.05);
      flex-wrap: wrap;
    }
    .search-box {
      flex: 1 1 300px;
      display: flex;
      align-items: center;
      gap: 0.65rem;
      background: #fbfaff;
      border: 1.5px solid #ddd6fe;
      border-radius: 12px;
      padding: 0.6rem 0.95rem;
      color: #4f46e5;
    }
    .search-input {
      border: none;
      background: transparent;
      outline: none;
      width: 100%;
      font-size: 0.95rem;
      font-family: var(--font-sans);
      color: var(--text-main);
    }
    .clear-search {
      background: none;
      border: none;
      cursor: pointer;
      color: var(--text-light);
      font-size: 1rem;
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
      padding: 0.55rem 0.85rem;
      font-size: 0.875rem;
      border-radius: 10px;
      border: 1.5px solid #ddd6fe;
      background-color: #ffffff;
    }
    .search-btn {
      padding: 0.65rem 1.45rem;
      border-radius: 12px;
    }
    .catalog-summary {
      margin-bottom: 1.25rem;
      color: var(--text-muted);
      font-size: 0.95rem;
    }
    .courses-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 1.85rem;
    }
    .course-card {
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      height: 100%;
      padding: 1.6rem;
      border: 1px solid rgba(221, 214, 254, 0.7);
      box-shadow: 0 8px 25px -4px rgba(99, 102, 241, 0.07);
      transition: var(--transition);
    }
    .course-card:hover {
      transform: translateY(-3px);
      box-shadow: 0 16px 36px -8px rgba(99, 102, 241, 0.14);
    }
    .badges-row {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 0.85rem;
    }
    .course-title {
      font-size: 1.25rem;
      margin-bottom: 0.5rem;
    }
    .course-title a {
      color: var(--text-main);
    }
    .course-title a:hover {
      color: var(--primary);
    }
    .course-desc {
      color: var(--text-muted);
      font-size: 0.9rem;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
      margin-bottom: 1.25rem;
    }
    .meta-row {
      display: flex;
      gap: 1.25rem;
      padding: 0.75rem 0;
      border-top: 1px solid var(--border-light);
      border-bottom: 1px solid var(--border-light);
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-bottom: 1.25rem;
    }
    .meta-item {
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .course-card-bottom {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .instructor-cell {
      display: flex;
      flex-direction: column;
    }
    .inst-label {
      font-size: 0.75rem;
      color: var(--text-light);
    }
    .inst-name {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-main);
    }
    .empty-state {
      text-align: center;
      padding: 4rem 2rem;
    }
    .empty-icon {
      font-size: 3rem;
      margin-bottom: 1rem;
    }
    .empty-state h3 {
      font-size: 1.35rem;
      margin-bottom: 0.5rem;
    }
    .empty-state p {
      color: var(--text-muted);
      margin-bottom: 1.5rem;
    }
    .loading-state {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
      padding: 4rem;
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
export class CourseCatalogComponent implements OnInit {
  courses: Course[] = [];
  isLoading = true;
  searchQuery = '';
  selectedCategory = '';
  selectedDifficulty = '';

  categories: string[] = ['Backend Engineering', 'Cloud & DevOps', 'Security & Architecture', 'Full-Stack Development', 'Data Engineering'];

  constructor(
    private courseService: CourseService,
    public auth: AuthService
  ) {}

  ngOnInit(): void {
    this.fetchCourses();
  }

  fetchCourses(): void {
    this.isLoading = true;
    this.courseService.getCourses({
      search: this.searchQuery.trim() || undefined,
      category: this.selectedCategory || undefined,
      difficulty: this.selectedDifficulty || undefined
    }).subscribe({
      next: (courses) => {
        this.courses = courses;
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  applyFilters(): void {
    this.fetchCourses();
  }

  clearSearch(): void {
    this.searchQuery = '';
    this.fetchCourses();
  }

  resetFilters(): void {
    this.searchQuery = '';
    this.selectedCategory = '';
    this.selectedDifficulty = '';
    this.fetchCourses();
  }

  getDifficultyBadge(diff: string): string {
    switch (diff) {
      case 'beginner': return 'badge-success';
      case 'intermediate': return 'badge-warning';
      case 'advanced': return 'badge-danger';
      default: return 'badge-neutral';
    }
  }
}

