export interface AnnouncementAuthor {
  id: number;
  full_name: string;
  email: string;
  role: string;
}

export interface CourseAnnouncement {
  id: number;
  course_id: number;
  instructor_id: number;
  title: string;
  content: string;
  is_published: boolean;
  created_at: string;
  updated_at: string;
  author?: AnnouncementAuthor;
}

export interface AnnouncementCreate {
  title: string;
  content: string;
  is_published?: boolean;
}

export interface AnnouncementUpdate {
  title?: string;
  content?: string;
  is_published?: boolean;
}

