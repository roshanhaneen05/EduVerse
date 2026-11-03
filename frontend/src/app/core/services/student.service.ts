import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Course } from '../models/course.model';
import {
  ContinueLearningResponse,
  EnrolledCourseDetail,
  EnhancedStudentDashboardResponse,
  StudentAssignmentOverviewItem,
  StudentQuizHistoryItem,
} from '../models/student.model';

@Injectable({
  providedIn: 'root'
})
export class StudentService {
  private readonly apiUrl = `${environment.apiUrl}/student`;

  constructor(private http: HttpClient) {}

  getDashboard(): Observable<EnhancedStudentDashboardResponse> {
    return this.http.get<EnhancedStudentDashboardResponse>(`${this.apiUrl}/dashboard`);
  }

  getMyLearning(status?: string): Observable<EnrolledCourseDetail[]> {
    let params = new HttpParams();
    if (status && status !== 'all') {
      params = params.set('status', status);
    }
    return this.http.get<EnrolledCourseDetail[]>(`${this.apiUrl}/my-learning`, { params });
  }

  continueCourse(courseId: number): Observable<ContinueLearningResponse> {
    return this.http.get<ContinueLearningResponse>(`${this.apiUrl}/courses/${courseId}/continue`);
  }

  getAssignments(filter?: string): Observable<StudentAssignmentOverviewItem[]> {
    let params = new HttpParams();
    if (filter && filter !== 'all') {
      params = params.set('filter', filter);
    }
    return this.http.get<StudentAssignmentOverviewItem[]>(`${this.apiUrl}/assignments`, { params });
  }

  getQuizHistory(): Observable<StudentQuizHistoryItem[]> {
    return this.http.get<StudentQuizHistoryItem[]>(`${this.apiUrl}/quiz-history`);
  }

  getRecommendations(limit: number = 4): Observable<Course[]> {
    const params = new HttpParams().set('limit', limit.toString());
    return this.http.get<Course[]>(`${this.apiUrl}/recommendations`, { params });
  }
}
