from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_mongo_db, require_instructor
from app.models.course import Course
from app.models.section import CourseSection
from app.models.lesson import Lesson
from app.models.instructor import InstructorProfile
from app.repositories.communication_repository import (
    create_email_delivery_doc,
    delete_email_delivery_doc,
    delete_email_delivery_from_sqlite_shadow,
    get_email_delivery_by_id,
    sync_email_delivery_to_sqlite_shadow,
)
from app.repositories.course_repository import (
    MongoCourse,
    claim_pending_enrollment_review,
    count_lessons_for_section,
    create_lesson_doc,
    create_section_doc,
    delete_course_cascade_mongo,
    delete_course_from_sqlite_shadow,
    delete_lesson_doc,
    delete_lesson_from_sqlite_shadow,
    delete_section_doc,
    delete_section_from_sqlite_shadow,
    get_course_by_id,
    get_enrollment_by_id,
    get_lesson_by_id,
    get_section_by_id,
    list_courses_filtered,
    list_enrollments_for_courses,
    list_lessons_for_course,
    list_sections_for_course,
    reassign_lessons_section,
    reorder_sections_in_course,
    restore_course_snapshot,
    restore_enrollment_snapshot,
    restore_lesson_snapshot,
    restore_section_snapshot,
    sync_course_to_sqlite_shadow,
    sync_enrollment_to_sqlite_shadow,
    sync_lesson_to_sqlite_shadow,
    sync_section_to_sqlite_shadow,
    update_course_doc,
    update_lesson_doc,
    update_section_doc,
)
from app.repositories.user_repository import (
    MongoUser,
    get_instructor_profile_by_user_id,
    get_users_by_ids,
)
from app.models.user import User
from app.schemas.admin import InstructorDashboardStats
from app.schemas.instructor import InstructorResponse
from app.schemas.enrollment import (
    EnrollmentDecisionResponse,
    InstructorEnrollmentResponse,
)
from app.schemas.analytics import (
    CourseAnalyticsResponse,
    CourseStudentReportResponse,
    EnhancedInstructorDashboardStats,
    StudentDetailedProgressResponse,
)
from app.services.analytics_service import (
    generate_student_report_csv,
    get_course_analytics,
    get_course_student_report,
    get_instructor_dashboard_analytics,
    get_student_detailed_progress,
)
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
    SubmissionGradePayload,
    SubmissionResponse,
)
from app.schemas.common import MessageResponse
from app.schemas.course import CourseCreate, CourseResponse, CourseUpdate, LessonOutlineItem
from app.schemas.lesson import LessonCreate, LessonResponse, LessonUpdate
from app.schemas.quiz import (
    QuestionCreate,
    QuestionDetail,
    QuizCreate,
    QuizDetail,
    QuizUpdate,
)
from app.services.quiz_service import (
    add_quiz_question,
    create_instructor_quiz,
    delete_instructor_quiz,
    delete_quiz_question,
    get_quiz_detail_for_instructor,
    list_quizzes_for_course_instructor,
    toggle_publish_quiz,
    update_instructor_quiz,
    update_quiz_question,
)
from app.schemas.section import (
    LessonAssignSection,
    SectionCreate,
    SectionDetailResponse,
    SectionOrderUpdate,
    SectionResponse,
    SectionUpdate,
)
from app.services.assignment_service import (
    create_assignment as service_create_assignment,
    delete_assignment as service_delete_assignment,
    get_assignment_for_instructor,
    get_assignment_submissions_for_instructor,
    get_submission_detail_for_instructor,
    grade_submission as service_grade_submission,
    list_instructor_assignments,
    toggle_assignment_status,
    update_assignment as service_update_assignment,
)
from app.services.course_service import (
    create_course,
    enrich_course_response,
    list_courses,
    update_course,
)
from app.services.email_service import (
    ENROLLMENT_APPROVED,
    ENROLLMENT_REJECTED,
    send_email_delivery,
)
from app.config import get_settings

router = APIRouter(prefix="/instructor", tags=["Instructor Management"])
settings = get_settings()


def check_course_ownership(course: MongoCourse | Course, user: MongoUser | User):
    """Ensure that the instructor owns this course (or is an administrator)."""
    if user.role != "admin" and course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this course.",
        )


@router.get(
    "/profile",
    response_model=InstructorResponse,
    summary="Get the authenticated instructor's profile",
)
def get_instructor_profile(
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    profile = get_instructor_profile_by_user_id(mongo_db, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor profile not found.")
    return InstructorResponse(
        user_id=current_user.id,
        instructor_id=profile.instructor_id,
        full_name=current_user.full_name,
        email=current_user.email,
        phone_number=profile.phone_number,
        qualification=profile.qualification,
        department=profile.department,
        subject_expertise=profile.subject_expertise,
        experience_years=profile.experience_years,
        profile_photo_url=profile.profile_photo_url,
        is_active=current_user.is_active,
        registered_at=profile.registered_at,
    )


@router.get(
    "/dashboard",
    response_model=EnhancedInstructorDashboardStats,
    summary="Get instructor dashboard statistics and recent enrollments",
)
def get_instructor_stats(
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_instructor_dashboard_analytics(mongo_db, current_user)


@router.get(
    "/enrollments",
    response_model=List[InstructorEnrollmentResponse],
    summary="List enrollments for courses managed by the authenticated instructor",
)
def get_instructor_enrollments(
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    instructor_filter = None if current_user.role == "admin" else current_user.id
    courses = list_courses_filtered(mongo_db, instructor_id=instructor_filter, limit=5000)
    course_map = {c.id: c for c in courses}
    if not course_map:
        return []

    enrollments = list_enrollments_for_courses(
        mongo_db,
        course_ids=list(course_map.keys()),
        sort_asc=False,
    )
    student_map = get_users_by_ids(mongo_db, [e.student_id for e in enrollments])

    results = []
    for enrollment in enrollments:
        course = course_map.get(enrollment.course_id)
        student = student_map.get(enrollment.student_id)
        if not course or not student:
            continue
        results.append(
            InstructorEnrollmentResponse(
                enrollment_id=enrollment.id,
                student_id=enrollment.student_id,
                student_name=student.full_name,
                student_email=student.email,
                course_id=enrollment.course_id,
                course_name=course.title,
                instructor_id=course.instructor_id,
                enrolled_at=enrollment.enrolled_at,
                status=enrollment.status,
                reviewed_at=enrollment.reviewed_at,
            )
        )
    return results


@router.get(
    "/enrollment-requests",
    response_model=List[InstructorEnrollmentResponse],
    summary="List pending enrollment requests for the authenticated instructor",
)
def get_enrollment_requests(
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    if current_user.role != "instructor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned instructor can review enrollment requests.",
        )

    courses = list_courses_filtered(mongo_db, instructor_id=current_user.id, limit=5000)
    course_map = {c.id: c for c in courses}
    if not course_map:
        return []

    requests = list_enrollments_for_courses(
        mongo_db,
        course_ids=list(course_map.keys()),
        status_filter="pending",
        sort_asc=True,
    )
    student_map = get_users_by_ids(mongo_db, [e.student_id for e in requests])

    results = []
    for enrollment in requests:
        course = course_map.get(enrollment.course_id)
        student = student_map.get(enrollment.student_id)
        if not course or not student:
            continue
        results.append(
            InstructorEnrollmentResponse(
                enrollment_id=enrollment.id,
                student_id=enrollment.student_id,
                student_name=student.full_name,
                student_email=student.email,
                course_id=enrollment.course_id,
                course_name=course.title,
                instructor_id=current_user.id,
                enrolled_at=enrollment.enrolled_at,
                status=enrollment.status,
                reviewed_at=enrollment.reviewed_at,
            )
        )
    return results


def _review_enrollment(
    enrollment_id: int,
    decision: str,
    event_type: str,
    current_user: MongoUser,
    mongo_db: Database,
    db: Session,
) -> EnrollmentDecisionResponse:
    if current_user.role != "instructor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned instructor can review enrollment requests.",
        )

    enrollment = get_enrollment_by_id(mongo_db, enrollment_id)
    course = get_course_by_id(mongo_db, enrollment.course_id) if enrollment else None
    if not enrollment or not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment request not found.")
    if course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only review requests for your assigned courses.",
        )
    if enrollment.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This enrollment request has already been reviewed.",
        )

    student = get_users_by_ids(mongo_db, [enrollment.student_id]).get(enrollment.student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student account not found.")

    reviewed_at = datetime.now(timezone.utc)
    updated_enr = claim_pending_enrollment_review(
        mongo_db,
        enrollment.id,
        decision=decision,
        reviewer_id=current_user.id,
        reviewed_at=reviewed_at,
    )
    if not updated_enr:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This enrollment request has already been reviewed.",
        )

    delivery = None
    try:
        delivery = create_email_delivery_doc(
            mongo_db,
            enrollment_id=updated_enr.id,
            event_type=event_type,
            recipient_email=student.email,
        )
        sync_enrollment_to_sqlite_shadow(db, updated_enr)
        sync_email_delivery_to_sqlite_shadow(db, delivery)
    except Exception:
        db.rollback()
        if delivery is not None:
            delete_email_delivery_from_sqlite_shadow(db, delivery.id)
            delete_email_delivery_doc(mongo_db, delivery.id)
        restore_enrollment_snapshot(mongo_db, enrollment)
        raise

    email_status = send_email_delivery(mongo_db, delivery, settings)
    latest_delivery = get_email_delivery_by_id(mongo_db, delivery.id)
    if latest_delivery is not None:
        sync_email_delivery_to_sqlite_shadow(db, latest_delivery)
    return EnrollmentDecisionResponse(
        enrollment_id=updated_enr.id,
        status=updated_enr.status,
        email_notification_status=email_status,
        email_delivery_id=delivery.id,
    )


@router.post(
    "/enrollments/{enrollment_id}/approve",
    response_model=EnrollmentDecisionResponse,
    summary="Approve a pending enrollment request",
)
def approve_enrollment(
    enrollment_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return _review_enrollment(
        enrollment_id,
        "approved",
        ENROLLMENT_APPROVED,
        current_user,
        mongo_db,
        db,
    )


@router.post(
    "/enrollments/{enrollment_id}/reject",
    response_model=EnrollmentDecisionResponse,
    summary="Reject a pending enrollment request",
)
def reject_enrollment(
    enrollment_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return _review_enrollment(
        enrollment_id,
        "rejected",
        ENROLLMENT_REJECTED,
        current_user,
        mongo_db,
        db,
    )


@router.get(
    "/courses/{course_id}/analytics",
    response_model=CourseAnalyticsResponse,
    summary="Get comprehensive course-level analytics",
)
def get_course_analytics_endpoint(
    course_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_course_analytics(mongo_db, course_id, current_user)


@router.get(
    "/courses/{course_id}/student-report",
    response_model=CourseStudentReportResponse,
    summary="Get course-level student roster performance report",
)
def get_course_student_report_endpoint(
    course_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_course_student_report(mongo_db, course_id, current_user)


@router.get(
    "/courses/{course_id}/student-report/csv",
    summary="Export course student performance report as CSV",
)
def export_course_student_report_csv_endpoint(
    course_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    csv_content = generate_student_report_csv(mongo_db, course_id, current_user)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="course_{course_id}_student_report.csv"'
        },
    )


@router.get(
    "/courses/{course_id}/students/{student_id}/progress",
    response_model=StudentDetailedProgressResponse,
    summary="Get comprehensive individual student progress across lessons, assignments, and quizzes",
)
def get_student_detailed_progress_endpoint(
    course_id: int,
    student_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_student_detailed_progress(mongo_db, course_id, student_id, current_user)


@router.get(
    "/courses",
    response_model=List[CourseResponse],
    summary="List courses created by the current instructor",
)
def get_my_courses(
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    instructor_id = None if current_user.role == "admin" else current_user.id
    return list_courses(mongo_db=mongo_db, instructor_id=instructor_id)


@router.post(
    "/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new course",
)
def create_new_course(
    course_in: CourseCreate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    course = create_course(mongo_db, course_in, instructor_id=current_user.id, sqlite_db=db)
    return enrich_course_response(mongo_db, course)


@router.put(
    "/courses/{course_id}",
    response_model=CourseResponse,
    summary="Update a course",
)
def update_existing_course(
    course_id: int,
    course_in: CourseUpdate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    updated = update_course(mongo_db, course, course_in, sqlite_db=db)
    return enrich_course_response(mongo_db, updated)


@router.delete(
    "/courses/{course_id}",
    response_model=MessageResponse,
    summary="Delete a course",
)
def delete_existing_course(
    course_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    delete_course_cascade_mongo(mongo_db, course_id)
    delete_course_from_sqlite_shadow(db, course_id)
    return MessageResponse(message="Course successfully deleted.")


@router.patch(
    "/courses/{course_id}/publish",
    response_model=CourseResponse,
    summary="Toggle course publication status",
)
def toggle_publish_course(
    course_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    updated = update_course_doc(mongo_db, course.id, {"is_published": not course.is_published})
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    try:
        sync_course_to_sqlite_shadow(db, updated)
    except Exception:
        restore_course_snapshot(mongo_db, course)
        raise
    return enrich_course_response(mongo_db, updated)


@router.get(
    "/courses/{course_id}/students",
    summary="View enrolled students and their progress for a specific course",
)
def get_course_students(
    course_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    enrollments = list_enrollments_for_courses(
        mongo_db,
        course_ids=[course_id],
        status_filter="approved",
        sort_asc=True,
    )
    student_map = get_users_by_ids(mongo_db, [e.student_id for e in enrollments])

    results = []
    for e in enrollments:
        student = student_map.get(e.student_id)
        if not student:
            continue
        results.append(
            {
                "enrollment_id": e.id,
                "student_id": student.id,
                "full_name": student.full_name,
                "email": student.email,
                "enrolled_at": e.enrolled_at.isoformat(),
                "completion_percentage": e.completion_percentage,
            }
        )
    return results


@router.post(
    "/courses/{course_id}/lessons",
    response_model=LessonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new lesson to a course",
)
def add_lesson(
    course_id: int,
    lesson_in: LessonCreate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    if lesson_in.section_id is not None:
        target_sec = get_section_by_id(mongo_db, lesson_in.section_id)
        if not target_sec or target_sec.course_id != course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Section does not exist or does not belong to this course.",
            )

    lesson = create_lesson_doc(
        mongo_db,
        course_id=course_id,
        section_id=lesson_in.section_id,
        title=lesson_in.title.strip(),
        content=lesson_in.content.strip(),
        video_url=lesson_in.video_url.strip() if lesson_in.video_url else None,
        order_index=lesson_in.order_index,
    )
    try:
        sync_lesson_to_sqlite_shadow(db, lesson)
    except Exception:
        delete_lesson_doc(mongo_db, lesson.id)
        raise

    return LessonResponse(
        id=lesson.id,
        course_id=lesson.course_id,
        section_id=lesson.section_id,
        title=lesson.title,
        content=lesson.content,
        video_url=lesson.video_url,
        order_index=lesson.order_index,
        is_completed=False,
        created_at=lesson.created_at,
        updated_at=lesson.updated_at,
    )


@router.put(
    "/lessons/{lesson_id}",
    response_model=LessonResponse,
    summary="Update an existing lesson",
)
def update_existing_lesson(
    lesson_id: int,
    lesson_in: LessonUpdate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    lesson = get_lesson_by_id(mongo_db, lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")
    course = get_course_by_id(mongo_db, lesson.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    updates: dict = {}
    if lesson_in.title is not None:
        updates["title"] = lesson_in.title.strip()
    if lesson_in.content is not None:
        updates["content"] = lesson_in.content.strip()
    if lesson_in.order_index is not None:
        updates["order_index"] = lesson_in.order_index
    if "video_url" in lesson_in.model_fields_set:
        updates["video_url"] = lesson_in.video_url.strip() if lesson_in.video_url else None
    if "section_id" in lesson_in.model_fields_set:
        if lesson_in.section_id is not None:
            target_sec = get_section_by_id(mongo_db, lesson_in.section_id)
            if not target_sec or target_sec.course_id != lesson.course_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Section does not exist or does not belong to this course.",
                )
        updates["section_id"] = lesson_in.section_id

    updated = update_lesson_doc(mongo_db, lesson.id, updates) if updates else lesson
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")
    try:
        sync_lesson_to_sqlite_shadow(db, updated)
    except Exception:
        restore_lesson_snapshot(mongo_db, lesson)
        raise

    return LessonResponse(
        id=updated.id,
        course_id=updated.course_id,
        section_id=updated.section_id,
        title=updated.title,
        content=updated.content,
        video_url=updated.video_url,
        order_index=updated.order_index,
        is_completed=False,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete(
    "/lessons/{lesson_id}",
    response_model=MessageResponse,
    summary="Delete a lesson",
)
def delete_existing_lesson(
    lesson_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    lesson = get_lesson_by_id(mongo_db, lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")
    course = get_course_by_id(mongo_db, lesson.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    delete_lesson_doc(mongo_db, lesson_id)
    delete_lesson_from_sqlite_shadow(db, lesson_id)
    return MessageResponse(message="Lesson successfully deleted.")


# ---------------------------------------------------------------------------
# Quiz and Assessment Management
# ---------------------------------------------------------------------------

@router.get(
    "/courses/{course_id}/quizzes",
    response_model=List[QuizDetail],
    summary="List all quizzes (draft and published) for an instructor's course",
)
def get_course_quizzes_instructor(
    course_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    return list_quizzes_for_course_instructor(mongo_db, course_id, current_user)


@router.get(
    "/quizzes/{quiz_id}",
    response_model=QuizDetail,
    summary="Get full quiz details including questions and answer keys for editing or preview",
)
def get_quiz_detail_instructor(
    quiz_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_quiz_detail_for_instructor(mongo_db, quiz_id, current_user)


@router.post(
    "/courses/{course_id}/quizzes",
    response_model=QuizDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a quiz with questions and answer options",
)
def create_quiz(
    course_id: int,
    quiz_in: QuizCreate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return create_instructor_quiz(mongo_db, course_id, quiz_in, current_user, sqlite_db=db)


@router.put(
    "/quizzes/{quiz_id}",
    response_model=QuizDetail,
    summary="Update quiz settings, title, time limit, attempt limit, or module association",
)
def update_quiz(
    quiz_id: int,
    quiz_in: QuizUpdate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return update_instructor_quiz(mongo_db, quiz_id, quiz_in, current_user, sqlite_db=db)


@router.patch(
    "/quizzes/{quiz_id}/publish",
    response_model=QuizDetail,
    summary="Toggle quiz published state (draft vs published)",
)
def toggle_quiz_publication(
    quiz_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return toggle_publish_quiz(mongo_db, quiz_id, current_user, sqlite_db=db)


@router.delete(
    "/quizzes/{quiz_id}",
    response_model=MessageResponse,
    summary="Delete a quiz safely",
)
def delete_quiz(
    quiz_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    delete_instructor_quiz(mongo_db, quiz_id, current_user, sqlite_db=db)
    return MessageResponse(message="Quiz successfully deleted.")


@router.post(
    "/quizzes/{quiz_id}/questions",
    response_model=QuestionDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new question with multiple-choice options to a quiz",
)
def add_question_to_quiz(
    quiz_id: int,
    question_in: QuestionCreate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return add_quiz_question(mongo_db, quiz_id, question_in, current_user, sqlite_db=db)


@router.put(
    "/questions/{question_id}",
    response_model=QuestionDetail,
    summary="Update a question and its answer options",
)
def update_question_in_quiz(
    question_id: int,
    question_in: QuestionCreate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return update_quiz_question(mongo_db, question_id, question_in, current_user, sqlite_db=db)


@router.delete(
    "/questions/{question_id}",
    response_model=MessageResponse,
    summary="Remove a question from a quiz",
)
def remove_question_from_quiz(
    question_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    delete_quiz_question(mongo_db, question_id, current_user, sqlite_db=db)
    return MessageResponse(message="Question successfully deleted.")


# ---------------------------------------------------------------------------
# Course Sections / Modules Management
# ---------------------------------------------------------------------------


@router.get(
    "/courses/{course_id}/sections",
    response_model=List[SectionDetailResponse],
    summary="List sections with lessons for a course",
)
def get_course_sections(
    course_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    sections = list_sections_for_course(mongo_db, course_id)
    lessons = list_lessons_for_course(mongo_db, course_id)
    lesson_map = {}
    for l in lessons:
        lesson_map.setdefault(l.section_id, []).append(
            LessonOutlineItem(
                id=l.id,
                course_id=l.course_id,
                section_id=l.section_id,
                title=l.title,
                order_index=l.order_index,
                is_completed=False,
            )
        )

    results = []
    for s in sections:
        sec_lessons = lesson_map.get(s.id, [])
        results.append(
            SectionDetailResponse(
                id=s.id,
                course_id=s.course_id,
                title=s.title,
                description=s.description,
                order_index=s.order_index,
                lesson_count=len(sec_lessons),
                created_at=s.created_at,
                updated_at=s.updated_at,
                lessons=sec_lessons,
            )
        )
    return results


@router.post(
    "/courses/{course_id}/sections",
    response_model=SectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new course section",
)
def create_course_section(
    course_id: int,
    section_in: SectionCreate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    section = create_section_doc(
        mongo_db,
        course_id=course_id,
        title=section_in.title.strip(),
        description=section_in.description.strip() if section_in.description else None,
        order_index=section_in.order_index,
    )
    try:
        sync_section_to_sqlite_shadow(db, section)
    except Exception:
        delete_section_doc(mongo_db, section.id)
        raise

    return SectionResponse(
        id=section.id,
        course_id=section.course_id,
        title=section.title,
        description=section.description,
        order_index=section.order_index,
        lesson_count=0,
        created_at=section.created_at,
        updated_at=section.updated_at,
    )


@router.put(
    "/sections/{section_id}",
    response_model=SectionResponse,
    summary="Update section details or display order",
)
def update_course_section(
    section_id: int,
    section_in: SectionUpdate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    section = get_section_by_id(mongo_db, section_id)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
    course = get_course_by_id(mongo_db, section.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    updates: dict = {}
    if section_in.title is not None:
        updates["title"] = section_in.title.strip()
    if section_in.description is not None:
        updates["description"] = section_in.description.strip() if section_in.description else None
    if section_in.order_index is not None:
        updates["order_index"] = section_in.order_index

    updated = update_section_doc(mongo_db, section.id, updates) if updates else section
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
    try:
        sync_section_to_sqlite_shadow(db, updated)
    except Exception:
        restore_section_snapshot(mongo_db, section)
        raise

    lesson_count = count_lessons_for_section(mongo_db, updated.id)
    return SectionResponse(
        id=updated.id,
        course_id=updated.course_id,
        title=updated.title,
        description=updated.description,
        order_index=updated.order_index,
        lesson_count=lesson_count,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete(
    "/sections/{section_id}",
    response_model=MessageResponse,
    summary="Safely delete a section",
)
def delete_course_section(
    section_id: int,
    reassign_to_section_id: Optional[int] = None,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    section = get_section_by_id(mongo_db, section_id)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
    course = get_course_by_id(mongo_db, section.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    lesson_count = count_lessons_for_section(mongo_db, section_id)
    if lesson_count > 0:
        if reassign_to_section_id is not None:
            if reassign_to_section_id == section_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot reassign lessons to the section being deleted.",
                )
            target_sec = get_section_by_id(mongo_db, reassign_to_section_id)
            if not target_sec or target_sec.course_id != section.course_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Target reassign section does not exist in this course.",
                )
            reassign_lessons_section(mongo_db, section_id, reassign_to_section_id)
            db.query(Lesson).filter(Lesson.section_id == section_id).update(
                {"section_id": reassign_to_section_id},
                synchronize_session="fetch",
            )
            db.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete section that contains lessons. Reassign or delete the lessons first, or specify reassign_to_section_id.",
            )

    delete_section_doc(mongo_db, section_id)
    delete_section_from_sqlite_shadow(db, section_id)
    return MessageResponse(message="Section successfully deleted.")


@router.post(
    "/courses/{course_id}/sections/reorder",
    response_model=MessageResponse,
    summary="Batch reorder course sections",
)
def reorder_course_sections(
    course_id: int,
    orders: List[SectionOrderUpdate],
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    order_map = {item.section_id: item.order_index for item in orders}
    reorder_sections_in_course(mongo_db, course_id, order_map)
    sections = db.query(CourseSection).filter(CourseSection.course_id == course_id).all()
    for s in sections:
        if s.id in order_map:
            s.order_index = order_map[s.id]
    db.commit()
    return MessageResponse(message="Section ordering updated successfully.")


@router.put(
    "/lessons/{lesson_id}/assign-section",
    response_model=LessonResponse,
    summary="Assign a lesson to a section or change its section assignment",
)
def assign_lesson_to_section(
    lesson_id: int,
    assignment: LessonAssignSection,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    lesson = get_lesson_by_id(mongo_db, lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")
    course = get_course_by_id(mongo_db, lesson.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    updates: dict = {}
    if assignment.section_id is not None:
        target_sec = get_section_by_id(mongo_db, assignment.section_id)
        if not target_sec or target_sec.course_id != lesson.course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Section does not exist or does not belong to this course.",
            )
        updates["section_id"] = assignment.section_id
    else:
        updates["section_id"] = None

    if assignment.order_index is not None:
        updates["order_index"] = assignment.order_index

    updated = update_lesson_doc(mongo_db, lesson.id, updates)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")
    try:
        sync_lesson_to_sqlite_shadow(db, updated)
    except Exception:
        restore_lesson_snapshot(mongo_db, lesson)
        raise

    return LessonResponse(
        id=updated.id,
        course_id=updated.course_id,
        section_id=updated.section_id,
        title=updated.title,
        content=updated.content,
        video_url=updated.video_url,
        order_index=updated.order_index,
        is_completed=False,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


# ---------------------------------------------------------------------------
# Course Assignment & Grading Management
# ---------------------------------------------------------------------------


@router.post(
    "/courses/{course_id}/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new assignment for a course",
)
def create_course_assignment(
    course_id: int,
    assignment_in: AssignmentCreate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return service_create_assignment(
        mongo_db,
        course_id,
        assignment_in,
        current_user,
        sqlite_db=db,
    )


@router.get(
    "/courses/{course_id}/assignments",
    response_model=List[AssignmentResponse],
    summary="List all assignments for a course (instructor management view)",
)
def get_instructor_assignments(
    course_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    return list_instructor_assignments(mongo_db, course_id, current_user)


@router.get(
    "/assignments/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Get assignment details for instructor",
)
def get_instructor_assignment_detail(
    assignment_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_assignment_for_instructor(mongo_db, assignment_id, current_user)


@router.put(
    "/assignments/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Update assignment configuration and instructions",
)
def update_course_assignment(
    assignment_id: int,
    assignment_in: AssignmentUpdate,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return service_update_assignment(
        mongo_db,
        assignment_id,
        assignment_in,
        current_user,
        sqlite_db=db,
    )


@router.patch(
    "/assignments/{assignment_id}/publish",
    response_model=AssignmentResponse,
    summary="Toggle assignment publication status",
)
def toggle_publish_assignment(
    assignment_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return toggle_assignment_status(
        mongo_db,
        assignment_id,
        "is_published",
        current_user,
        sqlite_db=db,
    )


@router.patch(
    "/assignments/{assignment_id}/close",
    response_model=AssignmentResponse,
    summary="Toggle assignment closed status",
)
def toggle_close_assignment(
    assignment_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return toggle_assignment_status(
        mongo_db,
        assignment_id,
        "is_closed",
        current_user,
        sqlite_db=db,
    )


@router.patch(
    "/assignments/{assignment_id}/archive",
    response_model=AssignmentResponse,
    summary="Toggle assignment archive status",
)
def toggle_archive_assignment(
    assignment_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return toggle_assignment_status(
        mongo_db,
        assignment_id,
        "is_archived",
        current_user,
        sqlite_db=db,
    )


@router.delete(
    "/assignments/{assignment_id}",
    summary="Safely delete or archive an assignment",
)
def delete_course_assignment(
    assignment_id: int,
    archive_if_submissions: bool = False,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return service_delete_assignment(
        mongo_db,
        assignment_id,
        current_user,
        archive_if_submissions=archive_if_submissions,
        sqlite_db=db,
    )


@router.get(
    "/assignments/{assignment_id}/submissions",
    response_model=List[SubmissionResponse],
    summary="View all student submissions for an assignment",
)
def get_assignment_submissions(
    assignment_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_assignment_submissions_for_instructor(mongo_db, assignment_id, current_user)


@router.get(
    "/submissions/{submission_id}",
    response_model=SubmissionResponse,
    summary="Get single submission detail for grading",
)
def get_submission_detail(
    submission_id: int,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_submission_detail_for_instructor(mongo_db, submission_id, current_user)


@router.put(
    "/submissions/{submission_id}/grade",
    response_model=SubmissionResponse,
    summary="Award marks and written feedback on a student submission",
)
def grade_student_submission(
    submission_id: int,
    grade_in: SubmissionGradePayload,
    current_user: MongoUser = Depends(require_instructor),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return service_grade_submission(
        mongo_db,
        submission_id,
        grade_in,
        current_user,
        sqlite_db=db,
    )
