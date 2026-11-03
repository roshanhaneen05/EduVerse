import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  DiscussionCreate,
  DiscussionDetail,
  DiscussionReply,
  DiscussionUpdate,
  PaginatedDiscussions,
  ReplyCreate,
  ReplyUpdate,
} from '../models/discussion.model';

@Injectable({
  providedIn: 'root',
})
export class DiscussionService {
  private readonly baseUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getCourseDiscussions(
    courseId: number,
    search?: string,
    page: number = 1,
    pageSize: number = 20
  ): Observable<PaginatedDiscussions> {
    let params = new HttpParams()
      .set('page', page.toString())
      .set('page_size', pageSize.toString());

    if (search && search.trim()) {
      params = params.set('search', search.trim());
    }

    return this.http.get<PaginatedDiscussions>(
      `${this.baseUrl}/courses/${courseId}/discussions`,
      { params }
    );
  }

  createDiscussion(courseId: number, data: DiscussionCreate): Observable<DiscussionDetail> {
    return this.http.post<DiscussionDetail>(
      `${this.baseUrl}/courses/${courseId}/discussions`,
      data
    );
  }

  getDiscussionDetail(id: number): Observable<DiscussionDetail> {
    return this.http.get<DiscussionDetail>(`${this.baseUrl}/discussions/${id}`);
  }

  updateDiscussion(id: number, data: DiscussionUpdate): Observable<DiscussionDetail> {
    return this.http.put<DiscussionDetail>(`${this.baseUrl}/discussions/${id}`, data);
  }

  deleteDiscussion(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/discussions/${id}`);
  }

  togglePinDiscussion(id: number): Observable<DiscussionDetail> {
    return this.http.patch<DiscussionDetail>(`${this.baseUrl}/discussions/${id}/pin`, {});
  }

  createReply(discussionId: number, data: ReplyCreate): Observable<DiscussionReply> {
    return this.http.post<DiscussionReply>(
      `${this.baseUrl}/discussions/${discussionId}/replies`,
      data
    );
  }

  updateReply(replyId: number, data: ReplyUpdate): Observable<DiscussionReply> {
    return this.http.put<DiscussionReply>(`${this.baseUrl}/replies/${replyId}`, data);
  }

  deleteReply(replyId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/replies/${replyId}`);
  }
}

