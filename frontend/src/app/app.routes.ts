import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';

export const routes: Routes = [
  // Public Routes
  {
    path: '',
    loadComponent: () => import('./pages/landing/landing.component').then(m => m.LandingComponent),
    title: 'Learn & Grow - EduVerse'
  },
  {
    path: 'login',
    loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent),
    title: 'Sign In - EduVerse'
  },
  {
    path: 'student/login',
    redirectTo: 'login',
    pathMatch: 'full'
  },
  {
    path: 'instructor/login',
    redirectTo: 'login',
    pathMatch: 'full'
  },
  {
    path: 'admin/login',
    redirectTo: 'login',
    pathMatch: 'full'
  },
  {
    path: 'register',
    loadComponent: () => import('./pages/account-selection/account-selection.component').then(m => m.AccountSelectionComponent),
    data: { mode: 'register' },
    title: 'Choose Your Account - EduVerse'
  },
  {
    path: 'student/register',
    loadComponent: () => import('./pages/register/register.component').then(m => m.RegisterComponent),
    data: { role: 'student' },
    title: 'Student Registration - EduVerse'
  },
  {
    path: 'instructor/register',
    loadComponent: () => import('./pages/register/register.component').then(m => m.RegisterComponent),
    data: { role: 'instructor' },
    title: 'Instructor Registration - EduVerse'
  },
  {
    path: 'courses',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/courses/course-catalog.component').then(m => m.CourseCatalogComponent),
    title: 'Course Catalog - EduVerse'
  },
  {
    path: 'courses/:id',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/courses/course-detail.component').then(m => m.CourseDetailComponent),
    title: 'Course Details - EduVerse'
  },
  {
    path: 'courses/:id/announcements',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/courses/course-announcements.component').then(m => m.CourseAnnouncementsComponent),
    title: 'Course Announcements - EduVerse'
  },
  {
    path: 'courses/:id/discussions',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/courses/course-discussions.component').then(m => m.CourseDiscussionsComponent),
    title: 'Course Discussions - EduVerse'
  },
  {
    path: 'courses/:id/discussions/:discussionId',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/courses/course-discussions.component').then(m => m.CourseDiscussionsComponent),
    title: 'Discussion Thread - EduVerse'
  },

  // Authenticated Student Learning Routes
  {
    path: 'courses/:courseId/learn/:lessonId',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/learn/course-learn.component').then(m => m.CourseLearnComponent),
    title: 'Learning Environment - EduVerse'
  },
  {
    path: 'courses/:courseId/quizzes/:quizId',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/quizzes/quiz-interface.component').then(m => m.QuizInterfaceComponent),
    title: 'Take Assessment - EduVerse'
  },
  {
    path: 'courses/:courseId/assignments/:assignmentId',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/assignments/assignment-detail.component').then(m => m.AssignmentDetailComponent),
    title: 'Assignment & Submission - EduVerse'
  },
  {
    path: 'quizzes/attempts/:attemptId',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/quizzes/quiz-result.component').then(m => m.QuizResultComponent),
    title: 'Assessment Results Review - EduVerse'
  },
  {
    path: 'student/dashboard',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['student'] },
    loadComponent: () => import('./pages/student/student-dashboard.component').then(m => m.StudentDashboardComponent),
    title: 'Student Dashboard - EduVerse'
  },
  {
    path: 'student/my-learning',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['student'] },
    loadComponent: () => import('./pages/student/my-learning.component').then(m => m.MyLearningComponent),
    title: 'My Learning - EduVerse'
  },
  {
    path: 'student/assignments',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['student'] },
    loadComponent: () => import('./pages/student/student-assignments.component').then(m => m.StudentAssignmentsComponent),
    title: 'My Assignments & Tasks - EduVerse'
  },
  {
    path: 'student/quiz-history',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['student'] },
    loadComponent: () => import('./pages/student/student-quiz-history.component').then(m => m.StudentQuizHistoryComponent),
    title: 'Assessment History - EduVerse'
  },
  {
    path: 'profile',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/profile/profile.component').then(m => m.ProfileComponent),
    title: 'Account Profile - EduVerse'
  },
  {
    path: 'assistant',
    redirectTo: 'student/dashboard',
    pathMatch: 'full'
  },

  // Instructor Management Routes
  {
    path: 'instructor/dashboard',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['instructor', 'admin'] },
    loadComponent: () => import('./pages/instructor/instructor-dashboard.component').then(m => m.InstructorDashboardComponent),
    title: 'Instructor Hub - EduVerse'
  },
  {
    path: 'instructor/courses/new',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['instructor', 'admin'] },
    loadComponent: () => import('./pages/instructor/course-editor.component').then(m => m.CourseEditorComponent),
    title: 'Create Course - EduVerse'
  },
  {
    path: 'instructor/courses/:id/edit',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['instructor', 'admin'] },
    loadComponent: () => import('./pages/instructor/course-editor.component').then(m => m.CourseEditorComponent),
    title: 'Edit Course - EduVerse'
  },
  {
    path: 'instructor/courses/:id/lessons',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['instructor', 'admin'] },
    loadComponent: () => import('./pages/instructor/lesson-editor.component').then(m => m.LessonEditorComponent),
    title: 'Manage Lessons - EduVerse'
  },
  {
    path: 'instructor/courses/:id/quizzes',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['instructor', 'admin'] },
    loadComponent: () => import('./pages/instructor/quiz-editor.component').then(m => m.QuizEditorComponent),
    title: 'Manage Quizzes - EduVerse'
  },
  {
    path: 'instructor/courses/:id/assignments',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['instructor', 'admin'] },
    loadComponent: () => import('./pages/instructor/assignment-manager.component').then(m => m.AssignmentManagerComponent),
    title: 'Manage Assignments & Submissions - EduVerse'
  },
  {
    path: 'instructor/courses/:id/materials',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['instructor', 'admin'] },
    loadComponent: () => import('./pages/instructor/material-manager.component').then(m => m.MaterialManagerComponent),
    title: 'Manage Learning Materials & Resources - EduVerse'
  },
  {
    path: 'instructor/courses/:id/analytics',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['instructor', 'admin'] },
    loadComponent: () => import('./pages/instructor/course-analytics.component').then(m => m.CourseAnalyticsComponent),
    title: 'Course Analytics & Student Reports - EduVerse'
  },

  // Administrator Management Routes
  {
    path: 'admin/dashboard',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['admin'] },
    loadComponent: () => import('./pages/admin/admin-dashboard.component').then(m => m.AdminDashboardComponent),
    title: 'Administrator Governance - EduVerse'
  },
  {
    path: 'admin/analytics',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['admin'] },
    loadComponent: () => import('./pages/admin/admin-analytics.component').then(m => m.AdminAnalyticsComponent),
    title: 'Admin Analytics - EduVerse'
  },
  {
    path: 'admin/users',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['admin'] },
    loadComponent: () => import('./pages/admin/user-management.component').then(m => m.UserManagementComponent),
    title: 'User Governance - EduVerse'
  },
  {
    path: 'admin/courses',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['admin'] },
    loadComponent: () => import('./pages/admin/course-management.component').then(m => m.CourseManagementComponent),
    title: 'Course Governance - EduVerse'
  },

  // 404 Fallback
  {
    path: '**',
    loadComponent: () => import('./pages/not-found/not-found.component').then(m => m.NotFoundComponent),
    title: 'Page Not Found - EduVerse'
  }
];
