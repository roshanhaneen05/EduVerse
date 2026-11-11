import { LearningMaterial } from './material.model';

export interface InstructorSummary {
  id: number;
  full_name: string;
  email: string;
}

export interface LessonSummary {
  id: number;
  course_id: number;
  section_id?: number | null;
  title: string;
  order_index: number;
  is_completed?: boolean;
}

export interface CourseSection {
  id: number;
  course_id: number;
  title: string;
  description?: string | null;
  order_index: number;
  lesson_count: number;
  created_at: string;
  updated_at: string;
  lessons: LessonSummary[];
}

export interface SectionCreatePayload {
  title: string;
  description?: string;
  order_index?: number;
}

export interface SectionUpdatePayload {
  title?: string;
  description?: string;
  order_index?: number;
}

export interface SectionOrderUpdate {
  section_id: number;
  order_index: number;
}

export interface LessonAssignSectionPayload {
  section_id: number | null;
  order_index?: number;
}

export interface QuizSummary {
  id: number;
  course_id: number;
  title: string;
  description?: string;
  passing_score: number;
  is_published?: boolean;
  time_limit_minutes?: number | null;
  max_attempts?: number;
  section_id?: number | null;
  lesson_id?: number | null;
  question_count?: number;
}

export interface AssignmentSummary {
  id: number;
  course_id: number;
  section_id?: number | null;
  title: string;
  description?: string | null;
  max_marks: number;
  due_date?: string | null;
  is_closed: boolean;
  my_status?: string | null;
  my_grade?: number | null;
}

export interface Course {
  id: number;
  title: string;
  description: string;
  category: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  is_published: boolean;
  instructor_id: number;
  created_at: string;
  updated_at: string;
  instructor?: InstructorSummary;
  lesson_count: number;
  quiz_count: number;
  is_enrolled?: boolean;
}

export interface CourseDetail extends Course {
  sections?: CourseSection[];
  lessons: LessonSummary[];
  quizzes: QuizSummary[];
  assignments?: AssignmentSummary[];
  materials?: LearningMaterial[];
  enrollment_count: number;
  user_progress_percentage?: number;
  enrollment_status?: 'pending' | 'approved' | 'rejected' | null;
}

export interface CourseCreatePayload {
  title: string;
  description: string;
  category: string;
  difficulty: string;
  is_published?: boolean;
}

export interface CourseUpdatePayload {
  title?: string;
  description?: string;
  category?: string;
  difficulty?: string;
  is_published?: boolean;
}
