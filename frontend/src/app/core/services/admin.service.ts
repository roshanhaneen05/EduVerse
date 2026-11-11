import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  AdminCourseItem,
  PaginatedAdminCourses,
  PaginatedUsers,
  PlatformStats
} from '../models/admin.model';
import { User } from '../models/user.model';
import { AdminAnalyticsDashboard } from '../models/admin-analytics.model';

@Injectable({
  providedIn: 'root'
})
export class AdminService {
  private readonly apiUrl = `${environment.apiUrl}/admin`;

  constructor(private http: HttpClient) {}

  getStats(): Observable<PlatformStats> {
    return this.http.get<PlatformStats>(`${this.apiUrl}/stats`);
  }

  getAnalyticsDashboard(startDate: string, endDate: string): Observable<AdminAnalyticsDashboard> {
    const params = new HttpParams()
      .set('start_date', startDate)
      .set('end_date', endDate);
    return this.http.get<AdminAnalyticsDashboard>(`${this.apiUrl}/analytics/dashboard`, { params });
  }

  exportAnalytics(
    format: 'csv' | 'pdf',
    startDate: string,
    endDate: string
  ): Observable<Blob> {
    const params = new HttpParams()
      .set('format', format)
      .set('start_date', startDate)
      .set('end_date', endDate);
    return this.http.get(`${this.apiUrl}/analytics/export`, {
      params,
      responseType: 'blob'
    });
  }

  getUsers(filters?: {
    search?: string;
    role?: string;
    is_active?: boolean;
    page?: number;
    page_size?: number;
  }): Observable<PaginatedUsers> {
    let params = new HttpParams();
    if (filters?.search) params = params.set('search', filters.search);
    if (filters?.role) params = params.set('role', filters.role);
    if (filters?.is_active !== undefined) params = params.set('is_active', filters.is_active.toString());
    if (filters?.page !== undefined) params = params.set('page', filters.page.toString());
    if (filters?.page_size !== undefined) params = params.set('page_size', filters.page_size.toString());

    return this.http.get<PaginatedUsers>(`${this.apiUrl}/users`, { params });
  }

  updateUser(
    userId: number,
    payload: { role?: string; is_active?: boolean; full_name?: string }
  ): Observable<User> {
    return this.http.put<User>(`${this.apiUrl}/users/${userId}`, payload);
  }

  getCourses(filters?: {
    search?: string;
    category?: string;
    difficulty?: string;
    is_published?: boolean;
    page?: number;
    page_size?: number;
  }): Observable<PaginatedAdminCourses> {
    let params = new HttpParams();
    if (filters?.search) params = params.set('search', filters.search);
    if (filters?.category) params = params.set('category', filters.category);
    if (filters?.difficulty) params = params.set('difficulty', filters.difficulty);
    if (filters?.is_published !== undefined) params = params.set('is_published', filters.is_published.toString());
    if (filters?.page !== undefined) params = params.set('page', filters.page.toString());
    if (filters?.page_size !== undefined) params = params.set('page_size', filters.page_size.toString());

    return this.http.get<PaginatedAdminCourses>(`${this.apiUrl}/courses`, { params });
  }

  getCourseCategories(): Observable<string[]> {
    return this.http.get<string[]>(`${this.apiUrl}/courses/categories`);
  }

  toggleCoursePublish(courseId: number): Observable<AdminCourseItem> {
    return this.http.patch<AdminCourseItem>(`${this.apiUrl}/courses/${courseId}/publish`, {});
  }
}
