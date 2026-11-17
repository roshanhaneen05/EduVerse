import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  AICourseOutline,
  AIQuizAttemptResponse,
  AIQuizGeneratedResponse,
  AIQuizGenerationRequest,
  AIQuizHistoryItem,
  AIQuizReviewRequestResponse,
  AIQuizStartResponse,
  AIQuizAnswerSubmission,
  StudyPlannerDashboard,
  StudyPlanRequest,
  StudyPreference,
  StudyReminder,
  StudyTask,
} from '../models/ai-learning.model';

@Injectable({ providedIn: 'root' })
export class AILearningService {
  private readonly baseUrl = `${environment.apiUrl}/student/ai-learning`;

  constructor(private http: HttpClient) {}

  getErrorMessage(error: HttpErrorResponse, fallback: string): string {
    if (error.status === 0) {
      return 'Unable to reach the EduVerse backend. Check that the backend is running and try again.';
    }

    const detail = error.error?.detail ?? error.error?.message ?? error.error;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item && typeof item === 'object') {
            const issue = item as { msg?: unknown; message?: unknown; loc?: unknown };
            const message = typeof issue.msg === 'string'
              ? issue.msg
              : typeof issue.message === 'string' ? issue.message : '';
            const location = Array.isArray(issue.loc)
              ? issue.loc.filter((part) => typeof part === 'string' || typeof part === 'number').join('.')
              : '';
            return message ? (location ? `${location}: ${message}` : message) : '';
          }
          return '';
        })
        .filter((message) => message.length > 0);
      if (messages.length) return messages.join(' ');
    }
    if (detail && typeof detail === 'object') {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === 'string' && message.trim()) return message;
    }
    return fallback;
  }

  getCourses(): Observable<AICourseOutline[]> {
    return this.http.get<AICourseOutline[]>(`${this.baseUrl}/courses`);
  }

  generateQuiz(request: AIQuizGenerationRequest): Observable<AIQuizGeneratedResponse> {
    return this.http.post<AIQuizGeneratedResponse>(`${this.baseUrl}/quizzes`, request);
  }

  startQuiz(quizId: number): Observable<AIQuizStartResponse> {
    return this.http.post<AIQuizStartResponse>(`${this.baseUrl}/quizzes/${quizId}/attempts`, {});
  }

  submitQuiz(attemptId: number, answers: AIQuizAnswerSubmission[]): Observable<AIQuizAttemptResponse> {
    return this.http.post<AIQuizAttemptResponse>(`${this.baseUrl}/attempts/${attemptId}/submit`, { answers });
  }

  getQuizHistory(): Observable<AIQuizHistoryItem[]> {
    return this.http.get<AIQuizHistoryItem[]>(`${this.baseUrl}/quizzes/history`);
  }

  getQuizAttempt(attemptId: number): Observable<AIQuizAttemptResponse> {
    return this.http.get<AIQuizAttemptResponse>(`${this.baseUrl}/attempts/${attemptId}`);
  }

  requestInstructorReview(attemptId: number): Observable<AIQuizReviewRequestResponse> {
    return this.http.post<AIQuizReviewRequestResponse>(
      `${this.baseUrl}/attempts/${attemptId}/request-review`,
      {}
    );
  }

  getPlanner(): Observable<StudyPlannerDashboard> {
    return this.http.get<StudyPlannerDashboard>(`${this.baseUrl}/planner`);
  }

  savePreferences(request: StudyPlanRequest): Observable<StudyPreference> {
    return this.http.put<StudyPreference>(`${this.baseUrl}/planner/preferences`, request);
  }

  generatePlan(request: StudyPlanRequest): Observable<StudyPlannerDashboard> {
    return this.http.post<StudyPlannerDashboard>(`${this.baseUrl}/planner/generate`, request);
  }

  completeTask(taskId: number): Observable<StudyTask> {
    return this.http.patch<StudyTask>(`${this.baseUrl}/planner/tasks/${taskId}`, { status: 'completed' });
  }

  rescheduleTask(taskId: number, scheduledAt: string): Observable<StudyTask> {
    return this.http.put<StudyTask>(`${this.baseUrl}/planner/tasks/${taskId}/schedule`, {
      scheduled_at: scheduledAt,
    });
  }

  deleteTask(taskId: number): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/planner/tasks/${taskId}`);
  }

  markReminderRead(reminderId: number): Observable<StudyReminder> {
    return this.http.patch<StudyReminder>(
      `${this.baseUrl}/planner/reminders/${reminderId}/read`,
      {}
    );
  }
}
