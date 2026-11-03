export interface StudentSummary {
  id: number;
  full_name: string;
  email: string;
}

export interface SubmissionSummary {
  id: number;
  student_id: number;
  status: string;
  submitted_at: string;
  is_late: boolean;
  grade?: number | null;
  feedback?: string | null;
  graded_at?: string | null;
}

export interface Assignment {
  id: number;
  course_id: number;
  section_id?: number | null;
  title: string;
  description?: string | null;
  instructions: string;
  max_marks: number;
  due_date?: string | null;
  is_published: boolean;
  is_closed: boolean;
  allow_resubmission: boolean;
  is_archived: boolean;
  submission_count?: number;
  graded_count?: number;
  created_at: string;
  updated_at: string;
  my_submission?: SubmissionSummary | null;
  course_title?: string | null;
  section_title?: string | null;
}

export interface AssignmentSubmission {
  id: number;
  assignment_id: number;
  student_id: number;
  student?: StudentSummary | null;
  submission_text: string;
  attachments_json?: string | null;
  status: string;
  is_late: boolean;
  submitted_at: string;
  updated_at: string;
  grade?: number | null;
  feedback?: string | null;
  graded_by_id?: number | null;
  graded_at?: string | null;
  assignment_title?: string | null;
  max_marks?: number | null;
}

export interface AssignmentCreatePayload {
  title: string;
  description?: string;
  instructions: string;
  max_marks: number;
  due_date?: string | null;
  section_id?: number | null;
  allow_resubmission?: boolean;
  is_published?: boolean;
}

export interface AssignmentUpdatePayload {
  title?: string;
  description?: string;
  instructions?: string;
  max_marks?: number;
  due_date?: string | null;
  section_id?: number | null;
  allow_resubmission?: boolean;
  is_published?: boolean;
  is_closed?: boolean;
  is_archived?: boolean;
}

export interface SubmissionCreatePayload {
  submission_text: string;
  attachments_json?: string | null;
}

export interface SubmissionGradePayload {
  grade: number;
  feedback?: string;
}

