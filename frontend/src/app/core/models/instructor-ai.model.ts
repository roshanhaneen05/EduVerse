export interface InstructorTeachingCourse {
  id: number;
  title: string;
}

export interface InstructorPaperOutline {
  course_id: number;
  sections: Array<{
    id: number;
    title: string;
    lessons: Array<{ id: number; title: string }>;
  }>;
}

export interface InstructorTeachingSubmission {
  id: number;
  assignment_id: number;
  assignment_title: string;
  course_id: number;
  course_title: string;
  student_id: number;
  student_name: string;
  student_email: string;
  submission_text: string;
  attachments_json?: string | null;
  submitted_at: string;
  status: string;
  grade?: number | null;
  max_marks: number;
  latest_evaluation_id?: number | null;
  evaluation_status?: 'pending_review' | 'approved' | null;
}

export interface RubricCriterion {
  id?: number;
  criterion_name: string;
  maximum_marks: number;
  description: string;
  guidelines: string;
  order_index?: number;
}

export interface AssignmentRubric {
  assignment_id: number;
  assignment_title: string;
  max_marks: number;
  expected_answer: string;
  criteria: RubricCriterion[];
}

export interface EvaluationCriterion {
  id: number;
  criterion_name: string;
  maximum_marks: number;
  suggested_marks: number;
  final_marks?: number | null;
  feedback: string;
  order_index: number;
}

export interface AssignmentEvaluation {
  id: number;
  submission_id: number;
  assignment_id: number;
  assignment_title: string;
  student_id: number;
  student_name: string;
  instructor_id: number;
  ai_suggested_marks: number;
  final_marks?: number | null;
  ai_feedback: string;
  instructor_feedback?: string | null;
  evaluation_status: 'pending_review' | 'approved';
  created_at: string;
  approved_at?: string | null;
  criteria: EvaluationCriterion[];
}

export type InstructorQuestionType = 'mcq' | 'true_false' | 'short_answer' | 'long_answer' | 'fill_blank';
export type InstructorDifficulty = 'easy' | 'medium' | 'hard';

export interface InstructorPaperQuestion {
  id?: number;
  question_text: string;
  question_type: InstructorQuestionType;
  difficulty: InstructorDifficulty;
  marks: number;
  options: string[];
  correct_answer: string;
  explanation: string;
  question_order: number;
}

export interface InstructorQuestionPaper {
  id: number;
  course_id: number;
  course_title: string;
  title: string;
  total_marks: number;
  duration_minutes: number;
  difficulty: InstructorDifficulty | 'mixed';
  section_ids: number[];
  lesson_ids: number[];
  exam_date?: string | null;
  status: 'draft' | 'published';
  created_at: string;
  updated_at: string;
  questions: InstructorPaperQuestion[];
}

export interface InstructorQuestionPaperSummary {
  id: number;
  course_id: number;
  course_title: string;
  title: string;
  total_marks: number;
  duration_minutes: number;
  difficulty: InstructorDifficulty | 'mixed';
  status: 'draft' | 'published';
  exam_date?: string | null;
  updated_at: string;
}

export interface QuestionPaperGeneratePayload {
  course_id: number;
  section_ids: number[];
  lesson_ids: number[];
  title: string;
  difficulty: InstructorDifficulty | 'mixed';
  question_types: InstructorQuestionType[];
  question_count: number;
  total_marks: number;
  duration_minutes: number;
  exam_date?: string | null;
}
