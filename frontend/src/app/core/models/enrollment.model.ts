import { Course } from './course.model';

export interface Enrollment {
  id: number;
  student_id: number;
  course_id: number;
  enrolled_at: string;
  completion_percentage: number;
  course?: Course;
}

