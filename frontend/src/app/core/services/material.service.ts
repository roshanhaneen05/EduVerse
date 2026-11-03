import { Injectable } from '@angular/core';
import { HttpClient, HttpEvent, HttpParams, HttpRequest } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { LearningMaterial, MaterialUpdatePayload } from '../models/material.model';

@Injectable({
  providedIn: 'root'
})
export class MaterialService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getCourseMaterials(courseId: number, sectionId?: number, lessonId?: number): Observable<LearningMaterial[]> {
    let params = new HttpParams();
    if (sectionId) {
      params = params.set('section_id', sectionId.toString());
    }
    if (lessonId) {
      params = params.set('lesson_id', lessonId.toString());
    }
    return this.http.get<LearningMaterial[]>(`${this.apiUrl}/materials/course/${courseId}`, { params });
  }

  getMaterial(materialId: number): Observable<LearningMaterial> {
    return this.http.get<LearningMaterial>(`${this.apiUrl}/materials/${materialId}`);
  }

  uploadMaterialWithProgress(courseId: number, formData: FormData): Observable<HttpEvent<LearningMaterial>> {
    const req = new HttpRequest<FormData>(
      'POST',
      `${this.apiUrl}/instructor/courses/${courseId}/materials`,
      formData,
      {
        reportProgress: true,
      }
    );
    return this.http.request<LearningMaterial>(req);
  }

  uploadMaterial(courseId: number, formData: FormData): Observable<LearningMaterial> {
    return this.http.post<LearningMaterial>(`${this.apiUrl}/instructor/courses/${courseId}/materials`, formData);
  }

  updateMaterial(materialId: number, payload: MaterialUpdatePayload): Observable<LearningMaterial> {
    return this.http.put<LearningMaterial>(`${this.apiUrl}/instructor/materials/${materialId}`, payload);
  }

  deleteMaterial(materialId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/instructor/materials/${materialId}`);
  }

  downloadMaterialFile(materialId: number, originalFilename: string): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/materials/${materialId}/download`, {
      responseType: 'blob',
    });
  }

  triggerBrowserDownload(materialId: number, originalFilename: string): void {
    this.downloadMaterialFile(materialId, originalFilename).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = originalFilename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      },
      error: (err) => {
        console.error('Failed to download material file:', err);
      }
    });
  }
}

