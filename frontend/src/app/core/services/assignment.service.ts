import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Assignment,
  AssignmentAttachment,
  AssignmentSubmission,
  SubmissionCreatePayload,
} from '../models/assignment.model';

@Injectable({
  providedIn: 'root'
})
export class AssignmentService {
  private readonly apiUrl = `${environment.apiUrl}/assignments`;

  constructor(private http: HttpClient) {}

  getCourseAssignments(courseId: number): Observable<Assignment[]> {
    return this.http.get<Assignment[]>(`${this.apiUrl}/course/${courseId}`);
  }

  getAssignment(assignmentId: number): Observable<Assignment> {
    return this.http.get<Assignment>(`${this.apiUrl}/${assignmentId}`);
  }

  submitAssignment(assignmentId: number, payload: SubmissionCreatePayload): Observable<AssignmentSubmission> {
    return this.http.post<AssignmentSubmission>(`${this.apiUrl}/${assignmentId}/submit`, payload);
  }

  uploadAssignmentAttachment(assignmentId: number, file: File): Observable<AssignmentAttachment> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<AssignmentAttachment>(`${this.apiUrl}/${assignmentId}/attachments`, formData);
  }

  getMySubmission(assignmentId: number): Observable<AssignmentSubmission | null> {
    return this.http.get<AssignmentSubmission | null>(`${this.apiUrl}/${assignmentId}/my-submission`);
  }
}

