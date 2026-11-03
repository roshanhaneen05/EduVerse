export interface LearningMaterial {
  id: number;
  course_id: number;
  section_id?: number | null;
  lesson_id?: number | null;
  title: string;
  description?: string | null;
  original_filename: string;
  mime_type: string;
  file_size: number;
  file_size_formatted: string;
  file_extension: string;
  uploader_id: number;
  uploader_name?: string | null;
  section_title?: string | null;
  lesson_title?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaterialUpdatePayload {
  title?: string;
  description?: string;
  section_id?: number | null;
  lesson_id?: number | null;
}

