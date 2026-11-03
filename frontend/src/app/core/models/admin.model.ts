import { Course } from './course.model';
import { Enrollment } from './enrollment.model';
import { User } from './user.model';

export interface AdminRecentActivity {
  activity_type: string; // user_registered, course_enrolled, course_created, quiz_attempt
  title: string;
  description: string;
  timestamp: string;
  user_name?: string;
  user_email?: string;
  reference_id?: number;
}

export interface PlatformStats {
  total_users: number;
  total_students: number;
  total_instructors: number;
  total_admins: number;
  total_courses: number;
  published_courses: number;
  total_enrollments: number;
  total_quiz_attempts: number;
  average_quiz_pass_rate: number;
  total_assignments: number;
  total_submissions: number;
  total_learning_materials: number;
  recent_activities: AdminRecentActivity[];
}

export interface PaginatedUsers {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: User[];
}

export interface AdminCourseItem {
  id: number;
  title: string;
  description: string;
  category: string;
  difficulty: string;
  is_published: boolean;
  instructor_id: number;
  instructor_name: string;
  instructor_email: string;
  enrolled_students_count: number;
  lesson_count: number;
  quiz_count: number;
  assignment_count: number;
  created_at: string;
  updated_at: string;
}

export interface PaginatedAdminCourses {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: AdminCourseItem[];
}

export interface StudentDashboardStats {
  enrolled_courses_count: number;
  completed_courses_count: number;
  in_progress_courses_count: number;
  total_quizzes_taken: number;
  quizzes_passed: number;
  average_quiz_score: number;
  recent_quiz_results: {
    attempt_id: number;
    quiz_id: number;
    quiz_title: string;
    score: number;
    passed: boolean;
    submitted_at: string;
  }[];
}

export interface StudentDashboardData {
  stats: StudentDashboardStats;
  enrolled_courses: Enrollment[];
}

export interface InstructorDashboardStats {
  total_courses: number;
  published_courses: number;
  total_students_enrolled: number;
  total_quizzes: number;
  average_student_progress: number;
  recent_enrollments: {
    enrollment_id: number;
    student_name: string;
    student_email: string;
    course_title: string;
    completion_percentage: number;
    enrolled_at: string;
  }[];
}

export interface CourseStudentProgress {
  enrollment_id: number;
  student_id: number;
  full_name: string;
  email: string;
  enrolled_at: string;
  completion_percentage: number;
}
