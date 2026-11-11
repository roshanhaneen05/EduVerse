from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_student
from app.models.user import User
from app.schemas.course import CourseResponse
from app.schemas.student import (
    ContinueLearningResponse,
    EnrolledCourseDetail,
    EnhancedStudentDashboardResponse,
    StudentAssignmentOverviewItem,
    StudentQuizHistoryItem,
)
from app.services.student_service import (
    get_continue_learning_lesson,
    get_recommended_courses,
    get_student_dashboard_data,
    list_student_assignments,
    list_student_enrolled_courses,
    list_student_quiz_history,
)

router = APIRouter(prefix="/student", tags=["Student Experience & Learning"])


@router.get(
    "/dashboard",
    response_model=EnhancedStudentDashboardResponse,
    summary="Get comprehensive student dashboard metrics, deadlines, and real telemetry",
)
def get_student_dashboard(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Returns enhanced student dashboard with accurate metrics:
    - Enrolled, in-progress, and completed courses counts
    - Overall learning progress calculated across active enrollments
    - Recently accessed lessons with real timestamps
    - Upcoming assignment deadlines
    - Recent assessment grades (quizzes + graded assignments)
    - Course recommendations based on enrolled categories
    """
    return get_student_dashboard_data(db, current_user.id)


@router.get(
    "/my-learning",
    response_model=List[EnrolledCourseDetail],
    summary="Get enrolled courses with progress breakdown and next lesson actions",
)
def get_my_learning(
    status: Optional[str] = Query(None, description="Filter by status ('all', 'in_progress', 'completed')"),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Returns the student's enrolled courses with completed/remaining lesson counts,
    progress percentage, and next lesson ID for one-click continuation.
    """
    return list_student_enrolled_courses(db, current_user.id, status_filter=status)


@router.get(
    "/courses/{course_id}/continue",
    response_model=ContinueLearningResponse,
    summary="Get the next recommended lesson for an enrolled course",
)
def continue_course_learning(
    course_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Determines the next lesson to continue:
    - Active in-progress lesson if one is started
    - First incomplete lesson by order_index
    - First lesson for review if entire course is completed
    """
    return get_continue_learning_lesson(db, current_user.id, course_id)


@router.get(
    "/assignments",
    response_model=List[StudentAssignmentOverviewItem],
    summary="Get student assignment overview across enrolled courses",
)
def get_student_assignments(
    filter: Optional[str] = Query(None, description="Filter by status ('all', 'pending', 'submitted', 'graded', 'past_due')"),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Returns all published assignments across the student's enrolled courses,
    displaying personal submission state, deadlines, grades, and feedback.
    """
    return list_student_assignments(db, current_user.id, filter_status=filter)


@router.get(
    "/quiz-history",
    response_model=List[StudentQuizHistoryItem],
    summary="Get student quiz examination history",
)
def get_student_quiz_history(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Returns past quiz attempts for the student with scores and pass/fail states.
    Strictly excludes answer keys and other students' data.
    """
    return list_student_quiz_history(db, current_user.id)


@router.get(
    "/recommendations",
    response_model=List[CourseResponse],
    summary="Get personalized course recommendations based on enrolled categories",
)
def get_course_recommendations(
    limit: int = Query(4, ge=1, le=10, description="Max recommendations to return"),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Suggests published courses in categories the student has expressed interest in,
    strictly excluding courses the student is already enrolled in.
    """
    return get_recommended_courses(db, current_user.id, limit=limit)
