import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  AnnouncementCreate,
  AnnouncementUpdate,
  CourseAnnouncement,
} from '../models/announcement.model';

@Injectable({
  providedIn: 'root',
})
export class AnnouncementService {
  private readonly baseUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getCourseAnnouncements(courseId: number): Observable<CourseAnnouncement[]> {
    return this.http.get<CourseAnnouncement[]>(`${this.baseUrl}/courses/${courseId}/announcements`);
  }

  createAnnouncement(courseId: number, data: AnnouncementCreate): Observable<CourseAnnouncement> {
    return this.http.post<CourseAnnouncement>(`${this.baseUrl}/courses/${courseId}/announcements`, data);
  }

  getAnnouncement(id: number): Observable<CourseAnnouncement> {
    return this.http.get<CourseAnnouncement>(`${this.baseUrl}/announcements/${id}`);
  }

  updateAnnouncement(id: number, data: AnnouncementUpdate): Observable<CourseAnnouncement> {
    return this.http.put<CourseAnnouncement>(`${this.baseUrl}/announcements/${id}`, data);
  }

  deleteAnnouncement(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/announcements/${id}`);
  }
}

