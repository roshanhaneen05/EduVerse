from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_instructor
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.course import Course
from app.models.section import CourseSection
from app.models.enrollment import CourseEnrollment
from app.models.email_delivery import EmailDelivery
from app.models.lesson import Lesson
from app.services.file_validator import validate_upload_content
from app.services.storage import get_storage_provider
from app.models.quiz import (
    AnswerOption,
    Question,
    Quiz,
)
from app.models.user import User
from app.schemas.admin import InstructorDashboardStats
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
    get_assignment_submissions_for_instructor,
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


def check_course_ownership(course: Course, user: User):
    """Ensure that the instructor owns this course (or is an administrator)."""
    if user.role != "admin" and course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this course.",
        )


@router.get(
    "/dashboard",
    response_model=EnhancedInstructorDashboardStats,
    summary="Get instructor dashboard statistics and recent enrollments",
)
def get_instructor_stats(
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return get_instructor_dashboard_analytics(db, current_user)


@router.get(
    "/enrollments",
    response_model=List[InstructorEnrollmentResponse],
    summary="List enrollments for courses managed by the authenticated instructor",
)
def get_instructor_enrollments(
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    query = (
        db.query(CourseEnrollment)
        .join(Course, Course.id == CourseEnrollment.course_id)
        .options(
            joinedload(CourseEnrollment.student),
            joinedload(CourseEnrollment.course),
        )
    )
    if current_user.role != "admin":
        query = query.filter(Course.instructor_id == current_user.id)

    enrollments = query.order_by(CourseEnrollment.enrolled_at.desc()).all()
    return [
        InstructorEnrollmentResponse(
            enrollment_id=enrollment.id,
            student_id=enrollment.student_id,
            student_name=enrollment.student.full_name,
            student_email=enrollment.student.email,
            course_id=enrollment.course_id,
            course_name=enrollment.course.title,
            instructor_id=enrollment.course.instructor_id,
            enrolled_at=enrollment.enrolled_at,
            status=enrollment.status,
            reviewed_at=enrollment.reviewed_at,
        )
        for enrollment in enrollments
    ]


@router.get(
    "/enrollment-requests",
    response_model=List[InstructorEnrollmentResponse],
    summary="List pending enrollment requests for the authenticated instructor",
)
def get_enrollment_requests(
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    if current_user.role != "instructor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned instructor can review enrollment requests.",
        )

    requests = (
        db.query(CourseEnrollment)
        .join(Course, Course.id == CourseEnrollment.course_id)
        .options(
            joinedload(CourseEnrollment.student),
            joinedload(CourseEnrollment.course),
        )
        .filter(
            Course.instructor_id == current_user.id,
            CourseEnrollment.status == "pending",
        )
        .order_by(CourseEnrollment.enrolled_at.asc())
        .all()
    )
    return [
        InstructorEnrollmentResponse(
            enrollment_id=enrollment.id,
            student_id=enrollment.student_id,
            student_name=enrollment.student.full_name,
            student_email=enrollment.student.email,
            course_id=enrollment.course_id,
            course_name=enrollment.course.title,
            instructor_id=current_user.id,
            enrolled_at=enrollment.enrolled_at,
            status=enrollment.status,
            reviewed_at=enrollment.reviewed_at,
        )
        for enrollment in requests
    ]


def _review_enrollment(
    enrollment_id: int,
    decision: str,
    event_type: str,
    current_user: User,
    db: Session,
) -> EnrollmentDecisionResponse:
    if current_user.role != "instructor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned instructor can review enrollment requests.",
        )

    enrollment = (
        db.query(CourseEnrollment)
        .options(
            joinedload(CourseEnrollment.course),
            joinedload(CourseEnrollment.student),
        )
        .filter(CourseEnrollment.id == enrollment_id)
        .with_for_update()
        .first()
    )
    if not enrollment or not enrollment.course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment request not found.")
    if enrollment.course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only review requests for your assigned courses.",
        )
    if enrollment.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This enrollment request has already been reviewed.",
        )

    enrollment.status = decision
    enrollment.reviewed_at = datetime.now(timezone.utc)
    enrollment.reviewed_by_instructor_id = current_user.id
    delivery = EmailDelivery(
        enrollment_id=enrollment.id,
        event_type=event_type,
        recipient_email=enrollment.student.email,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)

    email_status = send_email_delivery(db, delivery, settings)
    return EnrollmentDecisionResponse(
        enrollment_id=enrollment.id,
        status=enrollment.status,
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
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return _review_enrollment(
        enrollment_id,
        "approved",
        ENROLLMENT_APPROVED,
        current_user,
        db,
    )


@router.post(
    "/enrollments/{enrollment_id}/reject",
    response_model=EnrollmentDecisionResponse,
    summary="Reject a pending enrollment request",
)
def reject_enrollment(
    enrollment_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return _review_enrollment(
        enrollment_id,
        "rejected",
        ENROLLMENT_REJECTED,
        current_user,
        db,
    )


@router.get(
    "/courses/{course_id}/analytics",
    response_model=CourseAnalyticsResponse,
    summary="Get comprehensive course-level analytics",
)
def get_course_analytics_endpoint(
    course_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return get_course_analytics(db, course_id, current_user)


@router.get(
    "/courses/{course_id}/student-report",
    response_model=CourseStudentReportResponse,
    summary="Get course-level student roster performance report",
)
def get_course_student_report_endpoint(
    course_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return get_course_student_report(db, course_id, current_user)


@router.get(
    "/courses/{course_id}/student-report/csv",
    summary="Export course student performance report as CSV",
)
def export_course_student_report_csv_endpoint(
    course_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    csv_content = generate_student_report_csv(db, course_id, current_user)
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
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return get_student_detailed_progress(db, course_id, student_id, current_user)


@router.get(
    "/courses",
    response_model=List[CourseResponse],
    summary="List courses created by the current instructor",
)
def get_my_courses(
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    instructor_id = None if current_user.role == "admin" else current_user.id
    return list_courses(db=db, instructor_id=instructor_id)


@router.post(
    "/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new course",
)
def create_new_course(
    course_in: CourseCreate,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    course = create_course(db, course_in, instructor_id=current_user.id)
    return enrich_course_response(db, course)


@router.put(
    "/courses/{course_id}",
    response_model=CourseResponse,
    summary="Update a course",
)
def update_existing_course(
    course_id: int,
    course_in: CourseUpdate,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    updated = update_course(db, course, course_in)
    return enrich_course_response(db, updated)


@router.delete(
    "/courses/{course_id}",
    response_model=MessageResponse,
    summary="Delete a course",
)
def delete_existing_course(
    course_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    db.delete(course)
    db.commit()
    return MessageResponse(message="Course successfully deleted.")


@router.patch(
    "/courses/{course_id}/publish",
    response_model=CourseResponse,
    summary="Toggle course publication status",
)
def toggle_publish_course(
    course_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    course.is_published = not course.is_published
    db.commit()
    db.refresh(course)
    return enrich_course_response(db, course)


@router.get(
    "/courses/{course_id}/students",
    summary="View enrolled students and their progress for a specific course",
)
def get_course_students(
    course_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    enrollments = (
        db.query(CourseEnrollment)
        .options(joinedload(CourseEnrollment.student))
        .filter(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.status == "approved",
        )
        .all()
    )

    return [
        {
            "enrollment_id": e.id,
            "student_id": e.student.id,
            "full_name": e.student.full_name,
            "email": e.student.email,
            "enrolled_at": e.enrolled_at.isoformat(),
            "completion_percentage": e.completion_percentage,
        }
        for e in enrollments
        if e.student
    ]


@router.post(
    "/courses/{course_id}/lessons",
    response_model=LessonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new lesson to a course",
)
def add_lesson(
    course_id: int,
    lesson_in: LessonCreate,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    lesson = Lesson(
        course_id=course_id,
        section_id=lesson_in.section_id,
        title=lesson_in.title.strip(),
        content=lesson_in.content.strip(),
        video_url=lesson_in.video_url.strip() if lesson_in.video_url else None,
        order_index=lesson_in.order_index,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)

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
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")
    course = db.query(Course).filter(Course.id == lesson.course_id).first()
    check_course_ownership(course, current_user)

    if lesson_in.title is not None:
        lesson.title = lesson_in.title.strip()
    if lesson_in.content is not None:
        lesson.content = lesson_in.content.strip()
    if lesson_in.order_index is not None:
        lesson.order_index = lesson_in.order_index
    if "section_id" in lesson_in.model_fields_set:
        lesson.section_id = lesson_in.section_id

    db.commit()
    db.refresh(lesson)

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


@router.delete(
    "/lessons/{lesson_id}",
    response_model=MessageResponse,
    summary="Delete a lesson",
)
def delete_existing_lesson(
    lesson_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")
    course = db.query(Course).filter(Course.id == lesson.course_id).first()
    check_course_ownership(course, current_user)

    db.delete(lesson)
    db.commit()
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
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return list_quizzes_for_course_instructor(db, course_id, current_user)


@router.get(
    "/quizzes/{quiz_id}",
    response_model=QuizDetail,
    summary="Get full quiz details including questions and answer keys for editing or preview",
)
def get_quiz_detail_instructor(
    quiz_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return get_quiz_detail_for_instructor(db, quiz_id, current_user)


@router.post(
    "/courses/{course_id}/quizzes",
    response_model=QuizDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a quiz with questions and answer options",
)
def create_quiz(
    course_id: int,
    quiz_in: QuizCreate,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return create_instructor_quiz(db, course_id, quiz_in, current_user)


@router.put(
    "/quizzes/{quiz_id}",
    response_model=QuizDetail,
    summary="Update quiz settings, title, time limit, attempt limit, or module association",
)
def update_quiz(
    quiz_id: int,
    quiz_in: QuizUpdate,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return update_instructor_quiz(db, quiz_id, quiz_in, current_user)


@router.patch(
    "/quizzes/{quiz_id}/publish",
    response_model=QuizDetail,
    summary="Toggle quiz published state (draft vs published)",
)
def toggle_quiz_publication(
    quiz_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return toggle_publish_quiz(db, quiz_id, current_user)


@router.delete(
    "/quizzes/{quiz_id}",
    response_model=MessageResponse,
    summary="Delete a quiz safely",
)
def delete_quiz(
    quiz_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    delete_instructor_quiz(db, quiz_id, current_user)
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
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return add_quiz_question(db, quiz_id, question_in, current_user)


@router.put(
    "/questions/{question_id}",
    response_model=QuestionDetail,
    summary="Update a question and its answer options",
)
def update_question_in_quiz(
    question_id: int,
    question_in: QuestionCreate,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return update_quiz_question(db, question_id, question_in, current_user)


@router.delete(
    "/questions/{question_id}",
    response_model=MessageResponse,
    summary="Remove a question from a quiz",
)
def remove_question_from_quiz(
    question_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    delete_quiz_question(db, question_id, current_user)
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
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    sections = (
        db.query(CourseSection)
        .filter(CourseSection.course_id == course_id)
        .order_by(CourseSection.order_index.asc())
        .all()
    )
    lessons = (
        db.query(Lesson)
        .filter(Lesson.course_id == course_id)
        .order_by(Lesson.order_index.asc())
        .all()
    )
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
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    section = CourseSection(
        course_id=course_id,
        title=section_in.title.strip(),
        description=section_in.description.strip() if section_in.description else None,
        order_index=section_in.order_index,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
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
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
    course = db.query(Course).filter(Course.id == section.course_id).first()
    check_course_ownership(course, current_user)

    if section_in.title is not None:
        section.title = section_in.title.strip()
    if section_in.description is not None:
        section.description = section_in.description.strip() if section_in.description else None
    if section_in.order_index is not None:
        section.order_index = section_in.order_index

    db.commit()
    db.refresh(section)

    lesson_count = db.query(Lesson).filter(Lesson.section_id == section.id).count()
    return SectionResponse(
        id=section.id,
        course_id=section.course_id,
        title=section.title,
        description=section.description,
        order_index=section.order_index,
        lesson_count=lesson_count,
        created_at=section.created_at,
        updated_at=section.updated_at,
    )


@router.delete(
    "/sections/{section_id}",
    response_model=MessageResponse,
    summary="Safely delete a section",
)
def delete_course_section(
    section_id: int,
    reassign_to_section_id: Optional[int] = None,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
    course = db.query(Course).filter(Course.id == section.course_id).first()
    check_course_ownership(course, current_user)

    lesson_count = db.query(Lesson).filter(Lesson.section_id == section_id).count()
    if lesson_count > 0:
        if reassign_to_section_id is not None:
            if reassign_to_section_id == section_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot reassign lessons to the section being deleted.",
                )
            target_sec = (
                db.query(CourseSection)
                .filter(
                    CourseSection.id == reassign_to_section_id,
                    CourseSection.course_id == section.course_id,
                )
                .first()
            )
            if not target_sec:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Target reassign section does not exist in this course.",
                )
            db.query(Lesson).filter(Lesson.section_id == section_id).update(
                {"section_id": reassign_to_section_id},
                synchronize_session="fetch",
            )
            db.flush()
            db.expire_all()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete section that contains lessons. Reassign or delete the lessons first, or specify reassign_to_section_id.",
            )

    db.delete(section)
    db.commit()
    return MessageResponse(message="Section successfully deleted.")


@router.post(
    "/courses/{course_id}/sections/reorder",
    response_model=MessageResponse,
    summary="Batch reorder course sections",
)
def reorder_course_sections(
    course_id: int,
    orders: List[SectionOrderUpdate],
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    order_map = {item.section_id: item.order_index for item in orders}
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
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")
    course = db.query(Course).filter(Course.id == lesson.course_id).first()
    check_course_ownership(course, current_user)

    if assignment.section_id is not None:
        target_sec = (
            db.query(CourseSection)
            .filter(
                CourseSection.id == assignment.section_id,
                CourseSection.course_id == lesson.course_id,
            )
            .first()
        )
        if not target_sec:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Section does not exist or does not belong to this course.",
            )
        lesson.section_id = assignment.section_id
    else:
        lesson.section_id = None

    if assignment.order_index is not None:
        lesson.order_index = assignment.order_index

    db.commit()
    db.refresh(lesson)

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
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return service_create_assignment(db, course_id, assignment_in, current_user)


@router.get(
    "/courses/{course_id}/assignments",
    response_model=List[AssignmentResponse],
    summary="List all assignments for a course (instructor management view)",
)
def get_instructor_assignments(
    course_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return list_instructor_assignments(db, course_id, current_user)


@router.get(
    "/assignments/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Get assignment details for instructor",
)
def get_instructor_assignment_detail(
    assignment_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    course = db.query(Course).filter(Course.id == assignment.course_id).first()
    check_course_ownership(course, current_user)

    sub_count = db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == assignment.id).count()
    graded_count = (
        db.query(AssignmentSubmission)
        .filter(AssignmentSubmission.assignment_id == assignment.id, AssignmentSubmission.grade.isnot(None))
        .count()
    )

    return AssignmentResponse(
        id=assignment.id,
        course_id=assignment.course_id,
        section_id=assignment.section_id,
        title=assignment.title,
        description=assignment.description,
        instructions=assignment.instructions,
        max_marks=assignment.max_marks,
        due_date=assignment.due_date,
        is_published=assignment.is_published,
        is_closed=assignment.is_closed,
        allow_resubmission=assignment.allow_resubmission,
        is_archived=assignment.is_archived,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        submission_count=sub_count,
        graded_count=graded_count,
    )


@router.put(
    "/assignments/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Update assignment configuration and instructions",
)
def update_course_assignment(
    assignment_id: int,
    assignment_in: AssignmentUpdate,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return service_update_assignment(db, assignment_id, assignment_in, current_user)


@router.patch(
    "/assignments/{assignment_id}/publish",
    response_model=AssignmentResponse,
    summary="Toggle assignment publication status",
)
def toggle_publish_assignment(
    assignment_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return toggle_assignment_status(db, assignment_id, "is_published", current_user)


@router.patch(
    "/assignments/{assignment_id}/close",
    response_model=AssignmentResponse,
    summary="Toggle assignment closed status",
)
def toggle_close_assignment(
    assignment_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return toggle_assignment_status(db, assignment_id, "is_closed", current_user)


@router.patch(
    "/assignments/{assignment_id}/archive",
    response_model=AssignmentResponse,
    summary="Toggle assignment archive status",
)
def toggle_archive_assignment(
    assignment_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return toggle_assignment_status(db, assignment_id, "is_archived", current_user)


@router.delete(
    "/assignments/{assignment_id}",
    summary="Safely delete or archive an assignment",
)
def delete_course_assignment(
    assignment_id: int,
    archive_if_submissions: bool = False,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return service_delete_assignment(db, assignment_id, current_user, archive_if_submissions=archive_if_submissions)


@router.get(
    "/assignments/{assignment_id}/submissions",
    response_model=List[SubmissionResponse],
    summary="View all student submissions for an assignment",
)
def get_assignment_submissions(
    assignment_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return get_assignment_submissions_for_instructor(db, assignment_id, current_user)


@router.get(
    "/submissions/{submission_id}",
    response_model=SubmissionResponse,
    summary="Get single submission detail for grading",
)
def get_submission_detail(
    submission_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    submission = (
        db.query(AssignmentSubmission)
        .options(joinedload(AssignmentSubmission.assignment), joinedload(AssignmentSubmission.student))
        .filter(AssignmentSubmission.id == submission_id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    course = db.query(Course).filter(Course.id == submission.assignment.course_id).first()
    check_course_ownership(course, current_user)

    return SubmissionResponse(
        id=submission.id,
        assignment_id=submission.assignment_id,
        student_id=submission.student_id,
        student=StudentSummary(
            id=submission.student.id,
            full_name=submission.student.full_name,
            email=submission.student.email,
        )
        if submission.student
        else None,
        submission_text=submission.submission_text,
        attachments_json=submission.attachments_json,
        status=submission.status,
        is_late=submission.is_late,
        submitted_at=submission.submitted_at,
        updated_at=submission.updated_at,
        grade=submission.grade,
        feedback=submission.feedback,
        graded_by_id=submission.graded_by_id,
        graded_at=submission.graded_at,
        assignment_title=submission.assignment.title,
        max_marks=submission.assignment.max_marks,
    )


@router.put(
    "/submissions/{submission_id}/grade",
    response_model=SubmissionResponse,
    summary="Award marks and written feedback on a student submission",
)
def grade_student_submission(
    submission_id: int,
    grade_in: SubmissionGradePayload,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return service_grade_submission(db, submission_id, grade_in, current_user)
