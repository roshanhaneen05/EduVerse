import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Course, CourseDetail, CourseSection } from '../models/course.model';
import { Enrollment } from '../models/enrollment.model';

@Injectable({
  providedIn: 'root'
})
export class CourseService {
  private readonly apiUrl = `${environment.apiUrl}/courses`;
  private readonly enrollmentsUrl = `${environment.apiUrl}/enrollments`;

  constructor(private http: HttpClient) {}

  getCourses(filters?: {
    search?: string;
    category?: string;
    difficulty?: string;
    skip?: number;
    limit?: number;
  }): Observable<Course[]> {
    let params = new HttpParams();
    if (filters?.search) params = params.set('search', filters.search);
    if (filters?.category) params = params.set('category', filters.category);
    if (filters?.difficulty) params = params.set('difficulty', filters.difficulty);
    if (filters?.skip !== undefined) params = params.set('skip', filters.skip.toString());
    if (filters?.limit !== undefined) params = params.set('limit', filters.limit.toString());

    return this.http.get<Course[]>(this.apiUrl, { params });
  }

  getCourse(id: number): Observable<CourseDetail> {
    return this.http.get<CourseDetail>(`${this.apiUrl}/${id}`);
  }

  getCourseSections(id: number): Observable<CourseSection[]> {
    return this.http.get<CourseSection[]>(`${this.apiUrl}/${id}/sections`);
  }

  enrollInCourse(id: number): Observable<Enrollment> {
    return this.http.post<Enrollment>(`${this.apiUrl}/${id}/enroll`, {});
  }

  getMyEnrollments(): Observable<Enrollment[]> {
    return this.http.get<Enrollment[]>(`${this.enrollmentsUrl}/my-courses`);
  }
}

