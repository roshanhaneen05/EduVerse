import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Quiz,
  QuizAttemptResult,
  QuizAttemptSummary,
  QuizStartResponse,
  QuizSubmissionPayload,
} from '../models/quiz.model';

@Injectable({
  providedIn: 'root'
})
export class QuizService {
  private readonly apiUrl = `${environment.apiUrl}/quizzes`;

  constructor(private http: HttpClient) {}

  getCourseQuizzes(courseId: number): Observable<Quiz[]> {
    return this.http.get<Quiz[]>(`${this.apiUrl}/course/${courseId}`);
  }

  getQuiz(quizId: number): Observable<Quiz> {
    return this.http.get<Quiz>(`${this.apiUrl}/${quizId}`);
  }

  startQuiz(quizId: number): Observable<QuizStartResponse> {
    return this.http.post<QuizStartResponse>(`${this.apiUrl}/${quizId}/start`, {});
  }

  submitQuiz(quizId: number, submission: QuizSubmissionPayload): Observable<QuizAttemptResult> {
    return this.http.post<QuizAttemptResult>(`${this.apiUrl}/${quizId}/submit`, submission);
  }

  getAttempt(attemptId: number): Observable<QuizAttemptResult> {
    return this.http.get<QuizAttemptResult>(`${this.apiUrl}/attempts/${attemptId}`);
  }

  getMyAttempts(quizId?: number): Observable<QuizAttemptSummary[]> {
    let params = new HttpParams();
    if (quizId) params = params.set('quiz_id', quizId.toString());
    return this.http.get<QuizAttemptSummary[]>(`${this.apiUrl}/my-history`, { params });
  }
}
