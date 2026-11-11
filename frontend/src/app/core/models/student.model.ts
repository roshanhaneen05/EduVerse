import { Course } from './course.model';

export interface StudentRecentLessonActivity {
  lesson_id: number;
  lesson_title: string;
  course_id: number;
  course_title: string;
  is_completed: boolean;
  completed_at?: string;
  updated_at: string;
}

export interface StudentUpcomingDeadline {
  assignment_id: number;
  assignment_title: string;
  course_id: number;
  course_title: string;
  due_date: string;
  max_marks: number;
  is_submitted: boolean;
  submission_status?: string;
  grade?: number;
}

export interface StudentRecentGrade {
  assessment_type: 'quiz' | 'assignment';
  title: string;
  course_title: string;
  score_or_grade: number;
  max_score_or_grade: number;
  percentage: number;
  feedback?: string;
  date: string;
  passed?: boolean;
  reference_id: number;
}

export interface EnrolledCourseDetail {
  enrollment_id: number;
  course_id: number;
  course_title: string;
  course_category: string;
  course_difficulty: string;
  instructor_name: string;
  instructor_email: string;
  enrolled_at: string;
  completion_percentage: number;
  status: 'in_progress' | 'completed';
  enrollment_status: 'pending' | 'approved' | 'rejected';
  total_lessons: number;
  completed_lessons: number;
  remaining_lessons: number;
  next_lesson_id?: number;
  next_lesson_title?: string;
  last_accessed_at?: string;
}

export interface ContinueLearningResponse {
  course_id: number;
  course_title: string;
  next_lesson_id?: number;
  next_lesson_title?: string;
  is_course_completed: boolean;
  reason: string;
}

export interface StudentAssignmentOverviewItem {
  assignment_id: number;
  assignment_title: string;
  course_id: number;
  course_title: string;
  instructions: string;
  max_marks: number;
  due_date?: string;
  is_closed: boolean;
  submission_id?: number;
  submission_status: 'not_submitted' | 'submitted' | 'graded' | 'past_due';
  submitted_at?: string;
  is_late: boolean;
  grade?: number;
  feedback?: string;
  allow_resubmission: boolean;
}

export interface StudentQuizHistoryItem {
  attempt_id: number;
  quiz_id: number;
  quiz_title: string;
  course_id: number;
  course_title: string;
  attempt_number: number;
  score: number;
  total_points: number;
  passing_score: number;
  passed: boolean;
  started_at: string;
  submitted_at?: string;
  max_attempts: number;
  remaining_attempts?: number;
}

export interface EnhancedStudentDashboardStats {
  enrolled_courses_count: number;
  in_progress_courses_count: number;
  completed_courses_count: number;
  overall_progress_percentage: number;
  total_quizzes_taken: number;
  quizzes_passed: number;
  average_quiz_score: number;
  total_assignments_count: number;
  submitted_assignments_count: number;
  pending_assignments_count: number;
}

export interface EnhancedStudentDashboardResponse {
  stats: EnhancedStudentDashboardStats;
  recently_accessed_lessons: StudentRecentLessonActivity[];
  upcoming_deadlines: StudentUpcomingDeadline[];
  recent_grades: StudentRecentGrade[];
  recommended_courses: Course[];
  enrolled_courses: EnrolledCourseDetail[];
}
