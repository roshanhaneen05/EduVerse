export interface Lesson {
  id: number;
  course_id: number;
  section_id?: number | null;
  title: string;
  content: string;
  order_index: number;
  is_completed?: boolean;
  created_at: string;
  updated_at: string;
}

export interface LessonProgress {
  id: number;
  student_id: number;
  lesson_id: number;
  is_completed: boolean;
  completed_at: string;
  course_progress_percentage: number;
}

export interface LessonCreatePayload {
  title: string;
  content: string;
  order_index: number;
  section_id?: number | null;
}

export interface LessonUpdatePayload {
  title?: string;
  content?: string;
  order_index?: number;
  section_id?: number | null;
}

