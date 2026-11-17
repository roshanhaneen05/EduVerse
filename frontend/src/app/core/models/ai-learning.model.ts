export interface AILessonOutline {
  id: number;
  title: string;
  order_index: number;
}

export interface AISectionOutline {
  id: number;
  title: string;
  order_index: number;
  lessons: AILessonOutline[];
}

export interface AICourseOutline {
  id: number;
  title: string;
  sections: AISectionOutline[];
  lessons: AILessonOutline[];
}

export type AIDifficulty = 'easy' | 'medium' | 'hard';
export type AIQuestionType = 'mcq' | 'true_false' | 'short_answer' | 'mixed';

export interface AIQuizOption {
  id: number;
  text: string;
}

export interface AIQuizQuestion {
  id: number;
  question: string;
  question_type: 'mcq' | 'true_false' | 'short_answer';
  options: AIQuizOption[];
  difficulty: AIDifficulty;
  order_index: number;
}

export interface AIQuizSummary {
  id: number;
  title: string;
  course_id: number;
  course_title: string;
  section_id?: number | null;
  lesson_id?: number | null;
  difficulty: AIDifficulty;
  question_type: AIQuestionType;
  question_count: number;
  created_at: string;
}

export interface AIQuizGeneratedResponse {
  quiz: AIQuizSummary;
  questions: AIQuizQuestion[];
}

export interface AIQuizStartResponse {
  attempt_id: number;
  started_at: string;
}

export interface AIQuizAnswerSubmission {
  question_id: number;
  selected_option_id?: number;
  answer_text?: string;
}

export interface AIQuizAnswerReview {
  question_id: number;
  question: string;
  question_type: 'mcq' | 'true_false' | 'short_answer';
  submitted_answer?: string | null;
  correct_answer: string;
  is_correct: boolean;
  awarded_points: number;
  total_points: number;
  explanation: string;
  automated_evaluation: boolean;
  automated_feedback?: string | null;
}

export interface AIQuizAttemptResponse {
  id: number;
  quiz_id: number;
  quiz_title: string;
  course_title: string;
  started_at: string;
  submitted_at?: string | null;
  awarded_points: number;
  total_points: number;
  percentage: number;
  duration_seconds?: number | null;
  performance_level?: string | null;
  review_requested_at?: string | null;
  answers: AIQuizAnswerReview[];
}

export interface AIQuizHistoryItem {
  attempt_id: number;
  quiz_id: number;
  quiz_name: string;
  course_name: string;
  attempted_at: string;
  total_marks: number;
  awarded_marks: number;
  percentage: number;
  difficulty: AIDifficulty;
  time_taken_seconds?: number | null;
}

export interface AIQuizGenerationRequest {
  course_id: number;
  section_id?: number;
  lesson_id?: number;
  difficulty: AIDifficulty;
  question_count: 5 | 10 | 15 | 20;
  question_type: AIQuestionType;
}

export interface AIPlannerDeadline {
  course_id: number;
  title: string;
  deadline_type: 'exam' | 'deadline';
  due_at: string;
}

export type PreferredStudyTime = 'morning' | 'afternoon' | 'evening' | 'night';

export interface StudyPlanRequest {
  course_ids: number[];
  available_hours_per_day: number;
  preferred_time: PreferredStudyTime;
  time_zone: string;
  daily_duration_minutes: number;
  target_completion_date: string;
  deadlines: AIPlannerDeadline[];
}

export interface StudyPreference {
  course_ids: number[];
  deadlines: AIPlannerDeadline[];
  available_hours_per_day: number;
  preferred_time: PreferredStudyTime;
  time_zone: string;
  daily_duration_minutes: number;
  target_completion_date?: string | null;
}

export interface StudyTask {
  id: number;
  course_id: number;
  course_name: string;
  section_name?: string | null;
  lesson_id: number;
  lesson_name: string;
  scheduled_at: string;
  scheduled_date: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  priority: 'high' | 'medium' | 'low';
  status: 'pending' | 'completed' | 'missed';
  rationale: string;
  completed_at?: string | null;
}

export interface StudyCourseProgress {
  course_id: number;
  course_name: string;
  completed_lessons: number;
  total_lessons: number;
  completion_percentage: number;
}

export interface StudyReminder {
  id: number;
  notification_type: string;
  message: string;
  remind_at: string;
  is_read: boolean;
  task_id?: number | null;
  deadline_id?: number | null;
}

export interface StudyDeadlineEntry extends AIPlannerDeadline {
  id?: number | null;
}

export interface StudyPlannerDashboard {
  preferences?: StudyPreference | null;
  plan_id?: number | null;
  generation_mode?: 'ai' | 'rules' | null;
  target_completion_date?: string | null;
  tasks: StudyTask[];
  deadlines: StudyDeadlineEntry[];
  course_progress: StudyCourseProgress[];
  recommendations: string[];
  reminders: StudyReminder[];
  overall_progress: number;
}

export interface AIQuizReviewRequestResponse {
  message: string;
  review_requested_at: string;
}
