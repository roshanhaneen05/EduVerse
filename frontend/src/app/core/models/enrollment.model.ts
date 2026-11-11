import { Course } from './course.model';

export interface Enrollment {
  id: number;
  student_id: number;
  course_id: number;
  enrolled_at: string;
  completion_percentage: number;
  status: 'pending' | 'approved' | 'rejected';
  student_name: string;
  student_email: string;
  course_name: string;
  instructor_id: number;
  email_notification_status?: 'sent' | 'failed' | 'not_configured' | null;
  reviewed_at?: string | null;
  reviewed_by_instructor_id?: number | null;
  course?: Course;
}

export interface InstructorEnrollment {
  enrollment_id: number;
  student_id: number;
  student_name: string;
  student_email: string;
  course_id: number;
  course_name: string;
  instructor_id: number;
  enrolled_at: string;
  status: 'pending' | 'approved' | 'rejected';
  reviewed_at?: string | null;
}

export interface EnrollmentDecision {
  enrollment_id: number;
  status: 'approved' | 'rejected';
  email_notification_status: 'sent' | 'failed' | 'not_configured';
}
