export interface AIMessage {
  id?: number;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
  grounded_in?: string;
  is_course_grounded?: boolean;
  suggestions?: string[];
}

export interface AIConversationSummary {
  id: number;
  title: string;
  course_id?: number | null;
  message_count?: number;
  created_at: string;
  updated_at: string;
}

export interface AIConversationDetail {
  id: number;
  title: string;
  course_id?: number | null;
  created_at: string;
  updated_at: string;
  messages: AIMessage[];
}

export interface AIChatRequest {
  message: string;
  course_id?: number | null;
  lesson_id?: number | null;
  conversation_id?: number | null;
}

export interface AIChatResponse {
  conversation_id: number;
  message: string;
  response: string;
  provider: string;
  is_fallback?: boolean;
  grounded_in?: string | null;
  is_course_grounded?: boolean;
  suggestions?: string[];
  created_at: string;
}

export interface LessonSummaryResponse {
  lesson_id: number;
  lesson_title: string;
  course_id: number;
  course_title: string;
  summary: string;
  key_takeaways: string[];
  word_count: number;
  provider: string;
  generated_at: string;
}

export interface PracticeQuestionItem {
  id: number;
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
  concept_tested: string;
}

export interface PracticeQuestionsResponse {
  lesson_id?: number | null;
  lesson_title?: string | null;
  course_id: number;
  course_title: string;
  questions: PracticeQuestionItem[];
  disclaimer: string;
  provider: string;
  generated_at: string;
}

export interface StudyRecommendationItem {
  id: string;
  type: 'continue_lesson' | 'review_quiz' | 'assignment_due' | 'take_quiz' | string;
  priority: 'urgent' | 'high' | 'medium' | 'low';
  title: string;
  description: string;
  action_url: string;
  course_id: number;
  course_title: string;
  context_meta?: Record<string, any> | null;
}

export interface StudyRecommendationsResponse {
  student_id: number;
  total_recommendations: number;
  recommendations: StudyRecommendationItem[];
  advisory_notice: string;
  generated_at: string;
}
