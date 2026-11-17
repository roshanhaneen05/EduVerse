export interface InstructorProfile {
  user_id: number;
  instructor_id: string;
  full_name: string;
  email: string;
  phone_number: string;
  qualification: string;
  department: string;
  subject_expertise: string;
  experience_years: number;
  profile_photo_url: string | null;
  is_active: boolean;
  registered_at: string;
  email_delivery_status?: 'sent' | 'failed' | 'not_configured' | 'not_needed';
}

export interface InstructorPayload {
  full_name: string;
  email: string;
  phone_number: string;
  qualification: string;
  department: string;
  subject_expertise: string;
  experience_years: number;
  profile_photo_url?: string | null;
}

export interface InstructorPasswordSetupPayload {
  token: string;
  new_password: string;
}
