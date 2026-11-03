export interface QuizAnalyticsItem {
  quiz_id: number;
  quiz_title: string;
  passing_score: number;
  total_questions: number;
  time_limit_minutes?: number | null;
  is_published: boolean;
  total_attempts: number;
  unique_students_attempted: number;
  pass_count: number;
  fail_count: number;
  pass_rate: number;
  average_score: number;
}

export interface AssignmentAnalyticsItem {
  assignment_id: number;
  title: string;
  max_marks: number;
  due_date?: string | null;
  is_published: boolean;
  total_submissions: number;
  pending_grading: number;
  graded_count: number;
  average_grade?: number | null;
}

export interface CourseOverviewItem {
  course_id: number;
  title: string;
  category: string;
  difficulty: string;
  is_published: boolean;
  student_count: number;
  lesson_count: number;
  assignment_count: number;
  quiz_count: number;
  average_progress: number;
  completion_rate: number;
  pending_grading_count: number;
}

export interface EnhancedInstructorDashboardStats {
  total_courses: number;
  published_courses: number;
  total_students_enrolled: number;
  unique_students_count: number;
  total_assignments: number;
  total_assignment_submissions: number;
  pending_grading_count: number;
  total_quizzes: number;
  total_quiz_attempts: number;
  average_quiz_score: number;
  average_student_progress: number;
  completed_enrollments_count: number;
  course_completion_rate: number;
  recent_enrollments: {
    enrollment_id: number;
    student_name: string;
    student_email: string;
    course_title: string;
    completion_percentage: number;
    enrolled_at: string;
  }[];
  courses_overview: CourseOverviewItem[];
}

export interface CourseAnalyticsResponse {
  course_id: number;
  course_title: string;
  category: string;
  difficulty: string;
  is_published: boolean;
  total_students: number;
  total_lessons: number;
  average_completion_percentage: number;
  completed_students_count: number;
  course_completion_rate: number;
  total_assignments: number;
  total_assignment_submissions: number;
  pending_grading_count: number;
  graded_submissions_count: number;
  assignment_submission_rate: number;
  average_assignment_grade?: number | null;
  total_quizzes: number;
  total_quiz_attempts: number;
  average_quiz_score: number;
  quiz_pass_rate: number;
  quizzes_breakdown: QuizAnalyticsItem[];
  assignments_breakdown: AssignmentAnalyticsItem[];
}

export interface StudentPerformanceItem {
  student_id: number;
  full_name: string;
  email: string;
  enrolled_at: string;
  completion_percentage: number;
  completed_lessons_count: number;
  total_lessons_count: number;
  assignments_submitted_count: number;
  total_assignments_count: number;
  pending_grading_count: number;
  average_assignment_grade?: number | null;
  quizzes_taken_count: number;
  total_quizzes_count: number;
  quizzes_passed_count: number;
  average_quiz_score?: number | null;
  status: 'Completed' | 'In Progress' | 'Needs Attention';
  assistance_reasons: string[];
}

export interface CourseStudentReportResponse {
  course_id: number;
  course_title: string;
  total_students: number;
  average_completion_percentage: number;
  students: StudentPerformanceItem[];
}

export interface StudentLessonProgressDetail {
  lesson_id: number;
  title: string;
  section_title?: string | null;
  order_index: number;
  is_completed: boolean;
  completed_at?: string | null;
}

export interface StudentAssignmentSubmissionDetail {
  assignment_id: number;
  title: string;
  max_marks: number;
  due_date?: string | null;
  status: string;
  is_submitted: boolean;
  submitted_at?: string | null;
  grade?: number | null;
  feedback?: string | null;
  is_late: boolean;
}

export interface StudentQuizAttemptDetail {
  quiz_id: number;
  title: string;
  passing_score: number;
  attempt_id: number;
  attempt_number: number;
  score: number;
  passed: boolean;
  submitted_at: string;
}

export interface StudentDetailedProgressResponse {
  student_id: number;
  full_name: string;
  email: string;
  course_id: number;
  course_title: string;
  enrolled_at: string;
  completion_percentage: number;
  total_lessons: number;
  completed_lessons: number;
  total_assignments: number;
  submitted_assignments: number;
  average_assignment_grade?: number | null;
  total_quizzes: number;
  attempted_quizzes: number;
  average_quiz_score?: number | null;
  status: string;
  assistance_reasons: string[];
  lessons_progress: StudentLessonProgressDetail[];
  assignment_submissions: StudentAssignmentSubmissionDetail[];
  quiz_attempts: StudentQuizAttemptDetail[];
}

