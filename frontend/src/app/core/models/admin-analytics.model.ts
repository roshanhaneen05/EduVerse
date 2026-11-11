export interface AdminAnalyticsOverview {
  total_registered_students: number;
  total_registered_instructors: number;
  total_published_courses: number;
  total_enrollments: number;
  total_completed_courses: number;
  total_active_users: number;
}

export interface StudentMetric {
  name: string;
  enrollment_count: number;
  average_completion_rate: number;
}

export interface AdminStudentAnalytics {
  total_students: number;
  new_student_registrations: number;
  active_students: number;
  inactive_students: number;
  total_enrollments: number;
  average_enrollments_per_student: number;
  top_students: StudentMetric[];
  highest_completion_students: StudentMetric[];
}

export interface CourseMetric {
  course_id: number;
  course_name: string;
  instructor_name: string | null;
  category: string;
  is_published: boolean;
  enrollment_count: number;
  completed_enrollments: number;
  completion_rate: number;
}

export interface CourseCategoryMetric {
  category: string;
  course_count: number;
}

export interface AdminCourseAnalytics {
  total_courses: number;
  published_courses: number;
  unpublished_courses: number;
  categories: CourseCategoryMetric[];
  courses: CourseMetric[];
  most_popular_courses: CourseMetric[];
  least_enrolled_courses: CourseMetric[];
  highest_completion_courses: CourseMetric[];
}

export interface InstructorMetric {
  name: string;
  course_count: number;
  student_enrollments: number;
  period_course_creations: number;
  period_enrollments: number;
}

export interface AdminInstructorAnalytics {
  total_instructors: number;
  instructors: InstructorMetric[];
  popular_courses: CourseMetric[];
}

export interface MonthlyAnalyticsPoint {
  month: string;
  student_registrations: number;
  enrollments: number;
  active_students: number;
}

export interface AdminAnalyticsTrends {
  monthly: MonthlyAnalyticsPoint[];
}

export interface AdminAnalyticsActivity {
  activity_type: string;
  activity_name: string;
  user_name: string;
  date: string;
}

export interface AdminAnalyticsDashboard {
  overview: AdminAnalyticsOverview;
  students: AdminStudentAnalytics;
  courses: AdminCourseAnalytics;
  instructors: AdminInstructorAnalytics;
  trends: AdminAnalyticsTrends;
  recent_activities: AdminAnalyticsActivity[];
}
