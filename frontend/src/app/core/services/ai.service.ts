import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  AIChatRequest,
  AIChatResponse,
  AIConversationDetail,
  AIConversationSummary,
  LessonSummaryResponse,
  PracticeQuestionsResponse,
  StudyRecommendationsResponse
} from '../models/ai.model';

@Injectable({
  providedIn: 'root'
})
export class AIService {
  private readonly apiUrl = `${environment.apiUrl}/ai`;

  constructor(private http: HttpClient) {}

  chat(
    message: string,
    conversationId?: number | null,
    courseId?: number | null,
    lessonId?: number | null
  ): Observable<AIChatResponse> {
    const payload: AIChatRequest = { message };
    if (conversationId) {
      payload.conversation_id = conversationId;
    }
    if (courseId) {
      payload.course_id = courseId;
    }
    if (lessonId) {
      payload.lesson_id = lessonId;
    }
    return this.http.post<AIChatResponse>(`${this.apiUrl}/chat`, payload);
  }

  summarizeLesson(lessonId: number): Observable<LessonSummaryResponse> {
    return this.http.post<LessonSummaryResponse>(`${this.apiUrl}/lessons/${lessonId}/summarize`, {});
  }

  getPracticeQuestions(lessonId: number): Observable<PracticeQuestionsResponse> {
    return this.http.post<PracticeQuestionsResponse>(`${this.apiUrl}/lessons/${lessonId}/practice-questions`, {});
  }

  getStudyRecommendations(): Observable<StudyRecommendationsResponse> {
    return this.http.get<StudyRecommendationsResponse>(`${this.apiUrl}/study-recommendations`);
  }

  getConversations(): Observable<AIConversationSummary[]> {
    return this.http.get<AIConversationSummary[]>(`${this.apiUrl}/conversations`);
  }

  getConversationDetail(conversationId: number): Observable<AIConversationDetail> {
    return this.http.get<AIConversationDetail>(`${this.apiUrl}/conversations/${conversationId}`);
  }

  deleteConversation(conversationId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/conversations/${conversationId}`);
  }
}
