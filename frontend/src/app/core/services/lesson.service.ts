import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Lesson, LessonProgress } from '../models/lesson.model';

@Injectable({
  providedIn: 'root'
})
export class LessonService {
  private readonly apiUrl = `${environment.apiUrl}/lessons`;

  constructor(private http: HttpClient) {}

  getLesson(id: number): Observable<Lesson> {
    return this.http.get<Lesson>(`${this.apiUrl}/${id}`);
  }

  completeLesson(id: number): Observable<LessonProgress> {
    return this.http.post<LessonProgress>(`${this.apiUrl}/${id}/complete`, {});
  }
}

