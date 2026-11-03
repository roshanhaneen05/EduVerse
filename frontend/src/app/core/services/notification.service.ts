import { Injectable, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  MarkAllReadResponse,
  UnreadCountResponse,
  UserNotification,
} from '../models/notification.model';

@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private readonly baseUrl = `${environment.apiUrl}/notifications`;

  unreadCount = signal<number>(0);

  constructor(private http: HttpClient) {}

  fetchUnreadCount(): Observable<UnreadCountResponse> {
    return this.http.get<UnreadCountResponse>(`${this.baseUrl}/unread-count`).pipe(
      tap((res) => {
        this.unreadCount.set(res.unread_count);
      })
    );
  }

  getNotifications(unreadOnly: boolean = false, limit: number = 50): Observable<UserNotification[]> {
    let params = new HttpParams().set('limit', limit.toString());
    if (unreadOnly) {
      params = params.set('unread_only', 'true');
    }
    return this.http.get<UserNotification[]>(this.baseUrl, { params });
  }

  markAsRead(notificationId: number): Observable<UserNotification> {
    return this.http.patch<UserNotification>(`${this.baseUrl}/${notificationId}/read`, {}).pipe(
      tap(() => {
        this.unreadCount.update((count) => Math.max(0, count - 1));
      })
    );
  }

  markAllAsRead(): Observable<MarkAllReadResponse> {
    return this.http.post<MarkAllReadResponse>(`${this.baseUrl}/mark-all-read`, {}).pipe(
      tap(() => {
        this.unreadCount.set(0);
      })
    );
  }
}

