export interface AnswerOption {
  id: number;
  question_id: number;
  option_text: string;
  is_correct?: boolean;
}

export interface Question {
  id: number;
  quiz_id: number;
  question_text: string;
  order_index: number;
  points: number;
  options: AnswerOption[];
}

export interface Quiz {
  id: number;
  course_id: number;
  section_id?: number;
  lesson_id?: number;
  title: string;
  description?: string;
  passing_score: number;
  is_published: boolean;
  time_limit_minutes?: number;
  max_attempts: number;
  created_at?: string;
  updated_at?: string;
  attempts_count?: number;
  can_attempt?: boolean;
  best_score?: number;
  total_attempts?: number;
  questions: Question[];
}

export interface QuizStartResponse {
  attempt_id: number;
  quiz_id: number;
  attempt_number: number;
  max_attempts: number;
  time_limit_minutes?: number;
  started_at: string;
  expires_at?: string;
}

export interface QuizAnswerSubmission {
  question_id: number;
  selected_option_id: number;
}

export interface QuizSubmissionPayload {
  attempt_id?: number;
  answers: QuizAnswerSubmission[];
}

export interface QuizAttemptAnswerReview {
  question_id: number;
  question_text: string;
  selected_option_id?: number;
  selected_option_text?: string;
  correct_option_id: number;
  correct_option_text: string;
  is_correct: boolean;
  awarded_points: number;
  points: number;
}

export interface QuizAttemptResult {
  id?: number;
  attempt_id: number;
  quiz_id: number;
  quiz_title: string;
  student_id?: number;
  attempt_number?: number;
  score: number;
  total_points: number;
  total_questions?: number;
  passing_score: number;
  passed: boolean;
  started_at: string;
  submitted_at: string;
  answers: QuizAttemptAnswerReview[];
}

export interface QuizAttemptSummary {
  id: number;
  quiz_id: number;
  quiz_title: string;
  course_id?: number;
  score: number;
  total_points: number;
  passed: boolean;
  submitted_at: string;
}

export interface QuestionCreatePayload {
  id?: number;
  question_text: string;
  order_index: number;
  points: number;
  options: {
    id?: number;
    option_text: string;
    is_correct: boolean;
  }[];
}

export interface QuizCreatePayload {
  title: string;
  description?: string;
  passing_score: number;
  is_published?: boolean;
  time_limit_minutes?: number;
  max_attempts?: number;
  section_id?: number;
  lesson_id?: number;
  questions: QuestionCreatePayload[];
}

export interface QuizUpdatePayload {
  title?: string;
  description?: string;
  passing_score?: number;
  is_published?: boolean;
  time_limit_minutes?: number;
  max_attempts?: number;
  section_id?: number;
  lesson_id?: number;
}
