export interface DiscussionAuthor {
  id: number;
  full_name: string;
  email: string;
  role: string;
}

export interface DiscussionReply {
  id: number;
  thread_id: number;
  user_id: number;
  parent_reply_id?: number | null;
  content: string;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  author?: DiscussionAuthor;
}

export interface DiscussionListItem {
  id: number;
  course_id: number;
  user_id: number;
  title: string;
  content: string;
  is_pinned: boolean;
  is_deleted: boolean;
  reply_count: number;
  created_at: string;
  updated_at: string;
  author?: DiscussionAuthor;
}

export interface DiscussionDetail {
  id: number;
  course_id: number;
  user_id: number;
  title: string;
  content: string;
  is_pinned: boolean;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  author?: DiscussionAuthor;
  replies: DiscussionReply[];
}

export interface PaginatedDiscussions {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: DiscussionListItem[];
}

export interface DiscussionCreate {
  title: string;
  content: string;
}

export interface DiscussionUpdate {
  title?: string;
  content?: string;
}

export interface ReplyCreate {
  content: string;
  parent_reply_id?: number | null;
}

export interface ReplyUpdate {
  content: string;
}

