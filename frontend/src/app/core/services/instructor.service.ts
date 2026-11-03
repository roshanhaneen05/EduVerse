import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Course, CourseCreatePayload, CourseSection, CourseUpdatePayload, LessonAssignSectionPayload, SectionCreatePayload, SectionOrderUpdate, SectionUpdatePayload } from '../models/course.model';
import { CourseStudentProgress, InstructorDashboardStats } from '../models/admin.model';
import {
  CourseAnalyticsResponse,
  CourseStudentReportResponse,
  EnhancedInstructorDashboardStats,
  StudentDetailedProgressResponse,
} from '../models/analytics.model';
import { LessonCreatePayload, Lesson, LessonUpdatePayload } from '../models/lesson.model';
import { Quiz, QuizCreatePayload, QuizUpdatePayload } from '../models/quiz.model';
import { Assignment, AssignmentCreatePayload, AssignmentSubmission, AssignmentUpdatePayload, SubmissionGradePayload } from '../models/assignment.model';

@Injectable({
  providedIn: 'root'
})
export class InstructorService {
  private readonly apiUrl = `${environment.apiUrl}/instructor`;

  constructor(private http: HttpClient) {}

  getDashboard(): Observable<EnhancedInstructorDashboardStats> {
    return this.http.get<EnhancedInstructorDashboardStats>(`${this.apiUrl}/dashboard`);
  }

  getCourseAnalytics(courseId: number): Observable<CourseAnalyticsResponse> {
    return this.http.get<CourseAnalyticsResponse>(`${this.apiUrl}/courses/${courseId}/analytics`);
  }

  getCourseStudentReport(courseId: number): Observable<CourseStudentReportResponse> {
    return this.http.get<CourseStudentReportResponse>(`${this.apiUrl}/courses/${courseId}/student-report`);
  }

  getStudentDetailedProgress(courseId: number, studentId: number): Observable<StudentDetailedProgressResponse> {
    return this.http.get<StudentDetailedProgressResponse>(`${this.apiUrl}/courses/${courseId}/students/${studentId}/progress`);
  }

  exportCourseStudentReportCsv(courseId: number): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/courses/${courseId}/student-report/csv`, {
      responseType: 'blob'
    });
  }

  getMyCourses(): Observable<Course[]> {
    return this.http.get<Course[]>(`${this.apiUrl}/courses`);
  }

  createCourse(payload: CourseCreatePayload): Observable<Course> {
    return this.http.post<Course>(`${this.apiUrl}/courses`, payload);
  }

  updateCourse(courseId: number, payload: CourseUpdatePayload): Observable<Course> {
    return this.http.put<Course>(`${this.apiUrl}/courses/${courseId}`, payload);
  }

  deleteCourse(courseId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/courses/${courseId}`);
  }

  togglePublish(courseId: number): Observable<Course> {
    return this.http.patch<Course>(`${this.apiUrl}/courses/${courseId}/publish`, {});
  }

  getCourseStudents(courseId: number): Observable<CourseStudentProgress[]> {
    return this.http.get<CourseStudentProgress[]>(`${this.apiUrl}/courses/${courseId}/students`);
  }

  // Course Sections
  getCourseSections(courseId: number): Observable<CourseSection[]> {
    return this.http.get<CourseSection[]>(`${this.apiUrl}/courses/${courseId}/sections`);
  }

  createSection(courseId: number, payload: SectionCreatePayload): Observable<CourseSection> {
    return this.http.post<CourseSection>(`${this.apiUrl}/courses/${courseId}/sections`, payload);
  }

  updateSection(sectionId: number, payload: SectionUpdatePayload): Observable<CourseSection> {
    return this.http.put<CourseSection>(`${this.apiUrl}/sections/${sectionId}`, payload);
  }

  deleteSection(sectionId: number, reassignToSectionId?: number): Observable<{ message: string }> {
    let params = new HttpParams();
    if (reassignToSectionId !== undefined && reassignToSectionId !== null) {
      params = params.set('reassign_to_section_id', reassignToSectionId.toString());
    }
    return this.http.delete<{ message: string }>(`${this.apiUrl}/sections/${sectionId}`, { params });
  }

  reorderSections(courseId: number, orders: SectionOrderUpdate[]): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}/courses/${courseId}/sections/reorder`, orders);
  }

  assignLessonSection(lessonId: number, payload: LessonAssignSectionPayload): Observable<any> {
    return this.http.put<any>(`${this.apiUrl}/lessons/${lessonId}/assign-section`, payload);
  }

  addLesson(courseId: number, payload: LessonCreatePayload): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/courses/${courseId}/lessons`, payload);
  }

  updateLesson(lessonId: number, payload: LessonUpdatePayload): Observable<any> {
    return this.http.put<any>(`${this.apiUrl}/lessons/${lessonId}`, payload);
  }

  deleteLesson(lessonId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/lessons/${lessonId}`);
  }

  getCourseQuizzes(courseId: number): Observable<Quiz[]> {
    return this.http.get<Quiz[]>(`${this.apiUrl}/courses/${courseId}/quizzes`);
  }

  getQuizDetail(quizId: number): Observable<Quiz> {
    return this.http.get<Quiz>(`${this.apiUrl}/quizzes/${quizId}`);
  }

  createQuiz(courseId: number, payload: QuizCreatePayload): Observable<Quiz> {
    return this.http.post<Quiz>(`${this.apiUrl}/courses/${courseId}/quizzes`, payload);
  }

  updateQuiz(quizId: number, payload: QuizUpdatePayload): Observable<Quiz> {
    return this.http.put<Quiz>(`${this.apiUrl}/quizzes/${quizId}`, payload);
  }

  toggleQuizPublication(quizId: number): Observable<Quiz> {
    return this.http.patch<Quiz>(`${this.apiUrl}/quizzes/${quizId}/publish`, {});
  }

  deleteQuiz(quizId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/quizzes/${quizId}`);
  }

  // Course Assignments & Grading
  getCourseAssignments(courseId: number): Observable<Assignment[]> {
    return this.http.get<Assignment[]>(`${this.apiUrl}/courses/${courseId}/assignments`);
  }

  createAssignment(courseId: number, payload: AssignmentCreatePayload): Observable<Assignment> {
    return this.http.post<Assignment>(`${this.apiUrl}/courses/${courseId}/assignments`, payload);
  }

  updateAssignment(assignmentId: number, payload: AssignmentUpdatePayload): Observable<Assignment> {
    return this.http.put<Assignment>(`${this.apiUrl}/assignments/${assignmentId}`, payload);
  }

  togglePublishAssignment(assignmentId: number): Observable<Assignment> {
    return this.http.patch<Assignment>(`${this.apiUrl}/assignments/${assignmentId}/publish`, {});
  }

  toggleCloseAssignment(assignmentId: number): Observable<Assignment> {
    return this.http.patch<Assignment>(`${this.apiUrl}/assignments/${assignmentId}/close`, {});
  }

  toggleArchiveAssignment(assignmentId: number): Observable<Assignment> {
    return this.http.patch<Assignment>(`${this.apiUrl}/assignments/${assignmentId}/archive`, {});
  }

  deleteAssignment(assignmentId: number, archiveIfSubmissions = false): Observable<{ message: string; archived: boolean }> {
    let params = new HttpParams();
    if (archiveIfSubmissions) {
      params = params.set('archive_if_submissions', 'true');
    }
    return this.http.delete<{ message: string; archived: boolean }>(`${this.apiUrl}/assignments/${assignmentId}`, { params });
  }

  getAssignmentSubmissions(assignmentId: number): Observable<AssignmentSubmission[]> {
    return this.http.get<AssignmentSubmission[]>(`${this.apiUrl}/assignments/${assignmentId}/submissions`);
  }

  getSubmissionDetail(submissionId: number): Observable<AssignmentSubmission> {
    return this.http.get<AssignmentSubmission>(`${this.apiUrl}/submissions/${submissionId}`);
  }

  gradeSubmission(submissionId: number, payload: SubmissionGradePayload): Observable<AssignmentSubmission> {
    return this.http.put<AssignmentSubmission>(`${this.apiUrl}/submissions/${submissionId}/grade`, payload);
  }
}
