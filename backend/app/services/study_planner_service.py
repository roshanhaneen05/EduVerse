import math
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from app.models.ai_learning import (
    StudyDeadline,
    StudyNotification,
    StudyPlan,
    StudyPreference,
    StudyTask,
)
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson, LessonProgress
from app.models.quiz import Quiz, QuizAttempt
from app.schemas.ai_learning import (
    GeneratedStudyPlanPayload,
    StudyPlanGenerationRequest,
    StudyPreferenceResponse,
)
from app.services.structured_ai import (
    AIProviderError,
    AIProviderNotConfigured,
    AIProviderCredentialsInvalid,
    AIProviderRateLimited,
    request_structured_ai_json,
)


_TIME_WINDOWS = {
    "morning": (time(7, 0), time(12, 0)),
    "afternoon": (time(12, 0), time(17, 0)),
    "evening": (time(17, 0), time(22, 0)),
    "night": (time(21, 0), time(23, 59)),
}
logger = logging.getLogger(__name__)


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _preference_response(preference: Optional[StudyPreference]):
    if preference is None:
        return None
    return StudyPreferenceResponse(
        course_ids=preference.selected_course_ids or [],
        deadlines=preference.deadlines_json or [],
        available_hours_per_day=preference.available_hours_per_day,
        preferred_time=preference.preferred_time,
        time_zone=preference.time_zone,
        daily_duration_minutes=preference.daily_duration_minutes,
        target_completion_date=preference.target_completion_date,
    )


def _save_preferences(
    db: Session,
    student_id: int,
    request: StudyPlanGenerationRequest,
) -> StudyPreference:
    preference = (
        db.query(StudyPreference)
        .filter(StudyPreference.student_id == student_id)
        .first()
    )
    if preference is None:
        preference = StudyPreference(student_id=student_id)
        db.add(preference)
    preference.selected_course_ids = request.course_ids
    preference.deadlines_json = [
        {
            "course_id": item.course_id,
            "title": item.title,
            "deadline_type": item.deadline_type,
            "due_at": item.due_at.isoformat(),
        }
        for item in request.deadlines
    ]
    preference.available_hours_per_day = request.available_hours_per_day
    preference.preferred_time = request.preferred_time
    preference.time_zone = request.time_zone
    preference.daily_duration_minutes = request.daily_duration_minutes
    preference.target_completion_date = request.target_completion_date
    preference.updated_at = datetime.now(timezone.utc)
    return preference


def save_study_preferences(
    db: Session,
    student_id: int,
    request: StudyPlanGenerationRequest,
) -> StudyPreferenceResponse:
    _validate_selected_courses(db, student_id, request.course_ids)
    preference = _save_preferences(db, student_id, request)
    db.commit()
    db.refresh(preference)
    return _preference_response(preference)


def _validate_selected_courses(db: Session, student_id: int, course_ids: list[int]) -> list[Course]:
    enrollments = (
        db.query(CourseEnrollment.course_id)
        .filter(
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.status == "approved",
            CourseEnrollment.course_id.in_(course_ids),
        )
        .all()
    )
    enrolled_ids = {row[0] for row in enrollments}
    if enrolled_ids != set(course_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Every selected course must have an approved enrollment.",
        )
    return db.query(Course).filter(Course.id.in_(course_ids)).all()


def _collect_progress(db: Session, student_id: int, courses: list[Course]) -> tuple[list[dict], list[dict]]:
    course_ids = [course.id for course in courses]
    lessons = (
        db.query(Lesson)
        .options(joinedload(Lesson.section))
        .filter(Lesson.course_id.in_(course_ids))
        .order_by(Lesson.course_id.asc(), Lesson.order_index.asc(), Lesson.id.asc())
        .all()
    )
    lesson_ids = [lesson.id for lesson in lessons]
    completed_ids = {
        row[0]
        for row in db.query(LessonProgress.lesson_id)
        .filter(
            LessonProgress.student_id == student_id,
            LessonProgress.lesson_id.in_(lesson_ids) if lesson_ids else False,
            LessonProgress.is_completed.is_(True),
        )
        .all()
    }

    lesson_by_course: dict[int, list[Lesson]] = {}
    for lesson in lessons:
        lesson_by_course.setdefault(lesson.course_id, []).append(lesson)

    quiz_attempts = (
        db.query(QuizAttempt, Quiz.course_id)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .filter(
            QuizAttempt.student_id == student_id,
            QuizAttempt.is_completed.is_(True),
            Quiz.course_id.in_(course_ids),
        )
        .all()
    )
    quiz_scores: dict[int, list[float]] = {}
    for attempt, course_id in quiz_attempts:
        if attempt.total_points:
            quiz_scores.setdefault(course_id, []).append(attempt.score)

    assignment_rows = (
        db.query(Assignment, Course.title)
        .join(Course, Course.id == Assignment.course_id)
        .filter(
            Assignment.course_id.in_(course_ids),
            Assignment.is_published.is_(True),
            Assignment.due_date.is_not(None),
        )
        .all()
    )
    submitted_assignment_ids = {
        row[0]
        for row in db.query(AssignmentSubmission.assignment_id)
        .filter(
            AssignmentSubmission.student_id == student_id,
            AssignmentSubmission.assignment_id.in_([item.id for item, _ in assignment_rows])
            if assignment_rows
            else False,
        )
        .all()
    }
    now = datetime.now(timezone.utc)
    assignments_by_course: dict[int, list[dict]] = {}
    for assignment, course_title in assignment_rows:
        due_at = _utc(assignment.due_date)
        if assignment.id not in submitted_assignment_ids and due_at and due_at > now:
            assignments_by_course.setdefault(assignment.course_id, []).append(
                {
                    "title": assignment.title,
                    "due_at": due_at.isoformat(),
                    "course_title": course_title,
                }
            )

    course_progress = []
    pending_lessons = []
    for course in courses:
        course_lessons = lesson_by_course.get(course.id, [])
        completed_count = sum(1 for lesson in course_lessons if lesson.id in completed_ids)
        course_progress.append(
            {
                "course_id": course.id,
                "course_title": course.title,
                "total_lessons": len(course_lessons),
                "completed_lessons": completed_count,
                "completion_percentage": (
                    round(completed_count / len(course_lessons) * 100, 1) if course_lessons else 0
                ),
                "average_quiz_score": (
                    round(sum(quiz_scores[course.id]) / len(quiz_scores[course.id]), 1)
                    if quiz_scores.get(course.id)
                    else None
                ),
                "upcoming_assignments": assignments_by_course.get(course.id, []),
            }
        )
        for lesson in course_lessons:
            if lesson.id not in completed_ids:
                pending_lessons.append(
                    {
                        "id": lesson.id,
                        "course_id": course.id,
                        "course_title": course.title,
                        "section_id": lesson.section_id,
                        "section_title": lesson.section.title if lesson.section else None,
                        "title": lesson.title,
                    }
                )
    return course_progress, pending_lessons


def _make_schedule(
    request: StudyPlanGenerationRequest,
    generated: GeneratedStudyPlanPayload,
    lessons_by_id: dict[int, dict],
) -> list[dict]:
    ordered_ids = [item.lesson_id for item in generated.tasks]
    if len(set(ordered_ids)) != len(ordered_ids) or set(ordered_ids) != set(lessons_by_id):
        raise HTTPException(
            status_code=502,
            detail="The AI provider returned an incomplete or invalid study plan. Please try again.",
        )

    start_clock, end_clock = _TIME_WINDOWS[request.preferred_time]
    daily_capacity = math.floor(request.available_hours_per_day * 60)
    session_capacity = min(request.daily_duration_minutes, daily_capacity)
    if session_capacity < 15:
        raise HTTPException(status_code=422, detail="Available daily study time must be at least 15 minutes.")

    zone = ZoneInfo(request.time_zone)
    local_now = datetime.now(zone)
    first_date = local_now.date()
    first_start = datetime.combine(first_date, start_clock, tzinfo=zone)
    if first_start <= local_now:
        first_date += timedelta(days=1)
    available_days = max(1, (request.target_completion_date - first_date).days + 1)
    spread_days = min(7, available_days, max(1, len(generated.tasks)))
    desired_sessions_per_day = max(1, math.ceil(len(generated.tasks) / spread_days))
    sessions_per_day = min(
        desired_sessions_per_day,
        max(1, daily_capacity // session_capacity),
    )
    cursor_date = first_date
    cursor = datetime.combine(cursor_date, start_clock, tzinfo=zone)
    used_today = 0
    sessions_today = 0
    scheduled = []
    for generated_task in generated.tasks:
        if generated_task.duration_minutes > session_capacity:
            raise HTTPException(
                status_code=502,
                detail="The AI provider returned a task longer than the available study session.",
            )
        while True:
            if cursor_date > request.target_completion_date:
                raise HTTPException(
                    status_code=422,
                    detail="There is not enough study time before the target date. Increase daily study time or choose a later date.",
                )
            window_end = datetime.combine(cursor_date, end_clock, tzinfo=zone)
            task_end = cursor + timedelta(minutes=generated_task.duration_minutes)
            if (
                used_today + generated_task.duration_minutes <= daily_capacity
                and sessions_today < sessions_per_day
                and task_end <= window_end
            ):
                break
            cursor_date += timedelta(days=1)
            cursor = datetime.combine(cursor_date, start_clock, tzinfo=zone)
            used_today = 0
            sessions_today = 0

        task_end = cursor + timedelta(minutes=generated_task.duration_minutes)
        lesson = lessons_by_id[generated_task.lesson_id]
        scheduled.append(
            {
                **lesson,
                "starts_at": cursor.astimezone(timezone.utc),
                "duration_minutes": generated_task.duration_minutes,
                "priority": generated_task.priority,
                "rationale": generated_task.rationale,
            }
        )
        used_today += generated_task.duration_minutes
        sessions_today += 1
        cursor = task_end + timedelta(minutes=10)
    return scheduled


def _rule_based_plan(
    request: StudyPlanGenerationRequest,
    course_progress: list[dict],
    pending_lessons: list[dict],
    prior_tasks: list[StudyTask],
) -> GeneratedStudyPlanPayload:
    progress_by_id = {course["course_id"]: course for course in course_progress}
    lesson_attempts: dict[int, list[str]] = {}
    for task in prior_tasks:
        lesson_attempts.setdefault(task.lesson_id, []).append(task.status)

    def lesson_deadline(lesson: dict) -> Optional[datetime]:
        deadlines = []
        course = progress_by_id.get(lesson["course_id"], {})
        for item in course.get("upcoming_assignments", []):
            try:
                deadlines.append(datetime.fromisoformat(item["due_at"]))
            except (KeyError, TypeError, ValueError):
                continue
        for item in request.deadlines:
            if item.course_id == lesson["course_id"]:
                due_at = item.due_at
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=timezone.utc)
                deadlines.append(due_at)
        return min(deadlines, key=_utc) if deadlines else None

    ranked_lessons = []
    now = datetime.now(timezone.utc)
    for lesson in pending_lessons:
        course = progress_by_id.get(lesson["course_id"], {})
        due_at = lesson_deadline(lesson)
        days_until_due = ((_utc(due_at) - now).total_seconds() / 86400) if due_at else None
        score = course.get("average_quiz_score")
        missed_before = "missed" in lesson_attempts.get(lesson["id"], [])
        if (days_until_due is not None and days_until_due <= 7) or (score is not None and score < 60) or missed_before:
            priority = "high"
        elif (days_until_due is not None and days_until_due <= 14) or (score is not None and score < 75):
            priority = "medium"
        else:
            priority = "low"
        rationale_parts = []
        if due_at:
            due_description = (
                "an upcoming exam" if any(
                    item.course_id == lesson["course_id"] and item.deadline_type == "exam"
                    and _utc(item.due_at) == _utc(due_at)
                    for item in request.deadlines
                ) else "an upcoming assignment or deadline"
            )
            rationale_parts.append(f"Prioritized for {course.get('course_title', 'this course')} because of {due_description}.")
        if score is not None and score < 75:
            rationale_parts.append(f"The recorded average quiz score is {score}%.")
        if missed_before:
            rationale_parts.append("A previous study session for this lesson was missed.")
        if not rationale_parts:
            rationale_parts.append("This lesson is incomplete in the course progress records.")
        ranked_lessons.append(
            (
                (
                    0 if priority == "high" else 1 if priority == "medium" else 2,
                    days_until_due if days_until_due is not None else float("inf"),
                    score if score is not None else 100,
                ),
                lesson,
                priority,
                " ".join(rationale_parts),
            )
        )
    ranked_lessons.sort(key=lambda item: item[0])

    available_minutes = min(
        request.daily_duration_minutes,
        math.floor(request.available_hours_per_day * 60),
    )
    if available_minutes < 15 and ranked_lessons:
        raise HTTPException(status_code=422, detail="Available daily study time must be at least 15 minutes.")
    tasks = [
        {
            "lesson_id": lesson["id"],
            "duration_minutes": max(15, available_minutes),
            "priority": priority,
            "rationale": rationale,
        }
        for _rank, lesson, priority, rationale in ranked_lessons
    ]

    recommendations = []
    low_score_courses = [
        course for course in course_progress
        if course.get("average_quiz_score") is not None and course["average_quiz_score"] < 60
    ]
    for course in low_score_courses[:3]:
        recommendations.append(
            f"Your recorded average quiz score in {course['course_title']} is "
            f"{course['average_quiz_score']}%; prioritize its remaining lessons."
        )
    upcoming = []
    for course in course_progress:
        upcoming.extend(
            (item["due_at"], course["course_title"], item["title"])
            for item in course.get("upcoming_assignments", [])
        )
    upcoming.extend(
        (item.due_at.isoformat(), progress_by_id[item.course_id]["course_title"], item.title)
        for item in request.deadlines
        if item.course_id in progress_by_id
    )
    upcoming.sort(key=lambda item: item[0])
    if upcoming and len(recommendations) < 5:
        _due_at, course_title, title = upcoming[0]
        recommendations.append(f"Prioritize {course_title} before the upcoming assessment or deadline: {title}.")
    if pending_lessons and len(recommendations) < 5:
        by_course: dict[str, int] = {}
        for lesson in pending_lessons:
            by_course[lesson["course_title"]] = by_course.get(lesson["course_title"], 0) + 1
        course_title, count = max(by_course.items(), key=lambda item: item[1])
        recommendations.append(f"You have {count} incomplete lesson(s) in {course_title}; schedule them before your target date.")
    if not recommendations:
        completed_count = sum(course["completed_lessons"] for course in course_progress)
        lesson_count = sum(course["total_lessons"] for course in course_progress)
        recommendations.append(
            f"You have completed {completed_count} of {lesson_count} lessons across the selected courses."
        )
    return GeneratedStudyPlanPayload(tasks=tasks, recommendations=recommendations[:5])


def _add_study_notification(
    db: Session,
    *,
    student_id: int,
    key: str,
    notification_type: str,
    message: str,
    remind_at: datetime,
    task_id: Optional[int] = None,
    deadline_id: Optional[int] = None,
) -> None:
    existing = (
        db.query(StudyNotification.id)
        .filter(StudyNotification.notification_key == key)
        .first()
    )
    if existing is None:
        db.add(
            StudyNotification(
                student_id=student_id,
                task_id=task_id,
                deadline_id=deadline_id,
                notification_key=key,
                notification_type=notification_type,
                message=message,
                remind_at=remind_at,
            )
        )


def generate_study_plan(
    db: Session,
    student_id: int,
    request: StudyPlanGenerationRequest,
) -> StudyPlan:
    courses = _validate_selected_courses(db, student_id, request.course_ids)
    course_progress, pending_lessons = _collect_progress(db, student_id, courses)
    lessons_by_id = {lesson["id"]: lesson for lesson in pending_lessons}

    prior_tasks = (
        db.query(StudyTask)
        .filter(StudyTask.student_id == student_id, StudyTask.course_id.in_(request.course_ids))
        .order_by(StudyTask.created_at.desc())
        .limit(100)
        .all()
    )
    prompt = (
        "Create a personalized study timetable from the supplied real EduVerse progress data. "
        "Return a JSON object with tasks and recommendations. Include every pending lesson exactly once, "
        "and no completed or unknown lesson. Rank lessons using upcoming assessment deadlines, low quiz "
        "scores, completion progress, and previous task completion/missed history. Return each task with "
        "lesson_id, duration_minutes (15 through the provided daily session limit), priority "
        "(high, medium, low), and a short data-based rationale. Return at least one specific, actionable "
        "recommendation based only on the supplied data. If there are no pending lessons, return an empty "
        "tasks array and recommendations describing the student's actual progress. Do not invent scores, "
        "deadlines, lessons, or course details."
    )
    user_payload = {
        "preferences": {
            "available_hours_per_day": request.available_hours_per_day,
            "preferred_time": request.preferred_time,
            "time_zone": request.time_zone,
            "daily_duration_minutes": request.daily_duration_minutes,
            "target_completion_date": request.target_completion_date.isoformat(),
        },
        "course_progress": course_progress,
        "pending_lessons": pending_lessons,
        "student_deadlines": [
            {
                "course_id": item.course_id,
                "title": item.title,
                "deadline_type": item.deadline_type,
                "due_at": item.due_at.isoformat(),
            }
            for item in request.deadlines
        ],
        "previous_study_tasks": [
            {
                "course_id": item.course_id,
                "lesson_id": item.lesson_id,
                "status": item.status,
                "scheduled_at": item.starts_at.isoformat(),
                "priority": item.priority,
            }
            for item in prior_tasks[:50]
        ],
    }
    generation_mode = "ai"
    try:
        response_data = request_structured_ai_json(prompt, user_payload)
        generated = GeneratedStudyPlanPayload.model_validate(response_data)
        scheduled = _make_schedule(request, generated, lessons_by_id)
    except (AIProviderNotConfigured, AIProviderCredentialsInvalid, AIProviderRateLimited, AIProviderError) as exc:
        logger.info("Using rule-based study plan because the AI provider is unavailable: %s", exc)
        generation_mode = "rules"
        generated = _rule_based_plan(request, course_progress, pending_lessons, prior_tasks)
        scheduled = _make_schedule(request, generated, lessons_by_id)
    except ValidationError as exc:
        logger.warning("Using rule-based study plan after invalid AI output.")
        generation_mode = "rules"
        generated = _rule_based_plan(request, course_progress, pending_lessons, prior_tasks)
        scheduled = _make_schedule(request, generated, lessons_by_id)
    except HTTPException as exc:
        if exc.status_code != 502:
            raise
        logger.warning("Using rule-based study plan after invalid AI schedule.")
        generation_mode = "rules"
        generated = _rule_based_plan(request, course_progress, pending_lessons, prior_tasks)
        scheduled = _make_schedule(request, generated, lessons_by_id)
    now = datetime.now(timezone.utc)
    plan = StudyPlan(
        student_id=student_id,
        selected_course_ids=request.course_ids,
        target_completion_date=request.target_completion_date,
        available_hours_per_day=request.available_hours_per_day,
        preferred_time=request.preferred_time,
        time_zone=request.time_zone,
        daily_duration_minutes=request.daily_duration_minutes,
        recommendations_json=generated.recommendations,
        generation_mode=generation_mode,
        is_active=True,
        generated_at=now,
    )
    _save_preferences(db, student_id, request)
    old_active_plans = (
        db.query(StudyPlan)
        .filter(StudyPlan.student_id == student_id, StudyPlan.is_active.is_(True))
        .all()
    )
    old_task_ids = [
        task_id
        for (task_id,) in db.query(StudyTask.id)
        .filter(StudyTask.plan_id.in_([item.id for item in old_active_plans]))
        .all()
    ] if old_active_plans else []
    old_deadline_ids = [
        deadline_id
        for (deadline_id,) in db.query(StudyDeadline.id)
        .filter(StudyDeadline.plan_id.in_([item.id for item in old_active_plans]))
        .all()
    ] if old_active_plans else []
    if old_task_ids:
        db.query(StudyNotification).filter(
            StudyNotification.student_id == student_id,
            StudyNotification.task_id.in_(old_task_ids),
            StudyNotification.is_read.is_(False),
        ).update({StudyNotification.is_read: True}, synchronize_session=False)
    if old_deadline_ids:
        db.query(StudyNotification).filter(
            StudyNotification.student_id == student_id,
            StudyNotification.deadline_id.in_(old_deadline_ids),
            StudyNotification.is_read.is_(False),
        ).update({StudyNotification.is_read: True}, synchronize_session=False)
    db.query(StudyPlan).filter(
        StudyPlan.student_id == student_id,
        StudyPlan.is_active.is_(True),
    ).update({StudyPlan.is_active: False}, synchronize_session=False)
    db.add(plan)
    db.flush()

    for deadline in request.deadlines:
        due_at = _utc(deadline.due_at)
        if due_at is None:
            continue
        db_deadline = StudyDeadline(
            plan_id=plan.id,
            student_id=student_id,
            course_id=deadline.course_id,
            title=deadline.title,
            deadline_type=deadline.deadline_type,
            due_at=due_at,
        )
        db.add(db_deadline)

    future_assignment_rows = (
        db.query(Assignment, Course.title)
        .join(Course, Course.id == Assignment.course_id)
        .filter(
            Assignment.course_id.in_(request.course_ids),
            Assignment.is_published.is_(True),
            Assignment.due_date.is_not(None),
        )
        .all()
    )
    submitted_assignment_ids = {
        row[0]
        for row in db.query(AssignmentSubmission.assignment_id)
        .filter(
            AssignmentSubmission.student_id == student_id,
            AssignmentSubmission.assignment_id.in_([item.id for item, _ in future_assignment_rows])
            if future_assignment_rows
            else False,
        )
        .all()
    }
    for assignment, _course_title in future_assignment_rows:
        due_at = _utc(assignment.due_date)
        already_added = any(
            item.course_id == assignment.course_id and item.title.casefold() == assignment.title.casefold()
            for item in request.deadlines
        )
        if (
            assignment.id not in submitted_assignment_ids
            and due_at is not None
            and due_at > now
            and not already_added
        ):
            db.add(
                StudyDeadline(
                    plan_id=plan.id,
                    student_id=student_id,
                    course_id=assignment.course_id,
                    title=assignment.title,
                    deadline_type="deadline",
                    due_at=due_at,
                )
            )

    for task_data in scheduled:
        task = StudyTask(
            plan_id=plan.id,
            student_id=student_id,
            course_id=task_data["course_id"],
            section_id=task_data["section_id"],
            lesson_id=task_data["id"],
            starts_at=task_data["starts_at"],
            duration_minutes=task_data["duration_minutes"],
            priority=task_data["priority"],
            status="pending",
            rationale=task_data["rationale"],
        )
        db.add(task)
        db.flush()
        _add_study_notification(
            db,
            student_id=student_id,
            key=f"task-upcoming-{task.id}",
            notification_type="upcoming_session",
            message=f"Upcoming study session: {task_data['course_title']} — {task_data['title']}.",
            remind_at=task.starts_at - timedelta(minutes=30),
            task_id=task.id,
        )

    db.flush()
    plan_deadlines = (
        db.query(StudyDeadline)
        .filter(StudyDeadline.plan_id == plan.id)
        .all()
    )
    for deadline in plan_deadlines:
        _add_study_notification(
            db,
            student_id=student_id,
            key=f"deadline-{deadline.id}",
            notification_type="approaching_deadline",
            message=f"{deadline.deadline_type.title()} approaching: {deadline.title}.",
            remind_at=max(now, _utc(deadline.due_at) - timedelta(days=1)),
            deadline_id=deadline.id,
        )
    db.commit()
    db.refresh(plan)
    return plan


def serialize_study_task(task: StudyTask) -> dict:
    local_start = _utc(task.starts_at).astimezone(ZoneInfo(task.plan.time_zone))
    ends_at = local_start + timedelta(minutes=task.duration_minutes)
    return {
        "id": task.id,
        "course_id": task.course_id,
        "course_name": task.course.title,
        "section_name": task.section.title if task.section else None,
        "lesson_id": task.lesson_id,
        "lesson_name": task.lesson.title,
        "scheduled_at": local_start,
        "scheduled_date": local_start.date(),
        "start_time": local_start.strftime("%H:%M"),
        "end_time": ends_at.strftime("%H:%M"),
        "duration_minutes": task.duration_minutes,
        "priority": task.priority,
        "status": task.status,
        "rationale": task.rationale,
        "completed_at": task.completed_at,
    }


def _refresh_missed_tasks(db: Session, student_id: int, plan: StudyPlan) -> None:
    now = datetime.now(timezone.utc)
    tasks = (
        db.query(StudyTask)
        .filter(
            StudyTask.plan_id == plan.id,
            StudyTask.student_id == student_id,
            StudyTask.status == "pending",
        )
        .all()
    )
    for task in tasks:
        ends_at = _utc(task.starts_at) + timedelta(minutes=task.duration_minutes)
        if ends_at < now:
            task.status = "missed"
            _add_study_notification(
                db,
                student_id=student_id,
                key=f"task-missed-{task.id}",
                notification_type="missed_task",
                message=f"Missed study task: {task.lesson.title} in {task.course.title}. Reschedule it when ready.",
                remind_at=now,
                task_id=task.id,
            )


def _course_progress(db: Session, student_id: int, course_ids: list[int]) -> list[dict]:
    if not course_ids:
        return []
    courses = db.query(Course).filter(Course.id.in_(course_ids)).order_by(Course.title.asc()).all()
    rows = []
    for course in courses:
        total = db.query(Lesson.id).filter(Lesson.course_id == course.id).count()
        completed = (
            db.query(LessonProgress.id)
            .join(Lesson, Lesson.id == LessonProgress.lesson_id)
            .filter(
                Lesson.course_id == course.id,
                LessonProgress.student_id == student_id,
                LessonProgress.is_completed.is_(True),
            )
            .count()
        )
        rows.append(
            {
                "course_id": course.id,
                "course_name": course.title,
                "total_lessons": total,
                "completed_lessons": completed,
                "completion_percentage": round(completed / total * 100, 1) if total else 0,
            }
        )
    return rows


def get_planner_dashboard(db: Session, student_id: int) -> dict:
    preference = (
        db.query(StudyPreference)
        .filter(StudyPreference.student_id == student_id)
        .first()
    )
    plan = (
        db.query(StudyPlan)
        .options(
            joinedload(StudyPlan.tasks).joinedload(StudyTask.course),
            joinedload(StudyPlan.tasks).joinedload(StudyTask.section),
            joinedload(StudyPlan.tasks).joinedload(StudyTask.lesson),
        )
        .filter(StudyPlan.student_id == student_id, StudyPlan.is_active.is_(True))
        .order_by(StudyPlan.generated_at.desc())
        .first()
    )
    if plan is None:
        return {
            "preferences": _preference_response(preference),
            "plan_id": None,
            "generation_mode": None,
            "target_completion_date": preference.target_completion_date if preference else None,
            "tasks": [],
            "deadlines": (preference.deadlines_json or []) if preference else [],
            "course_progress": [],
            "recommendations": [],
            "reminders": [],
            "overall_progress": 0.0,
        }

    _refresh_missed_tasks(db, student_id, plan)
    task_rows = (
        db.query(StudyTask)
        .options(
            joinedload(StudyTask.course),
            joinedload(StudyTask.section),
            joinedload(StudyTask.lesson),
        )
        .filter(StudyTask.plan_id == plan.id, StudyTask.student_id == student_id)
        .order_by(StudyTask.starts_at.asc())
        .all()
    )
    db.flush()
    reminders = (
        db.query(StudyNotification)
        .filter(
            StudyNotification.student_id == student_id,
            StudyNotification.is_read.is_(False),
            StudyNotification.remind_at <= datetime.now(timezone.utc) + timedelta(days=7),
        )
        .order_by(StudyNotification.remind_at.asc())
        .limit(100)
        .all()
    )
    progress = _course_progress(db, student_id, plan.selected_course_ids or [])
    deadline_rows = (
        db.query(StudyDeadline)
        .filter(StudyDeadline.plan_id == plan.id, StudyDeadline.student_id == student_id)
        .order_by(StudyDeadline.due_at.asc())
        .all()
    )
    total_lessons = sum(item["total_lessons"] for item in progress)
    completed_lessons = sum(item["completed_lessons"] for item in progress)
    tasks = [serialize_study_task(task) for task in task_rows]
    db.commit()
    return {
        "preferences": _preference_response(preference),
        "plan_id": plan.id,
        "generation_mode": plan.generation_mode,
        "target_completion_date": plan.target_completion_date,
        "tasks": tasks,
        "deadlines": [
            {
                "id": item.id,
                "course_id": item.course_id,
                "title": item.title,
                "deadline_type": item.deadline_type,
                "due_at": item.due_at,
            }
            for item in deadline_rows
        ],
        "course_progress": progress,
        "recommendations": plan.recommendations_json or [],
        "reminders": [
            {
                "id": reminder.id,
                "notification_type": reminder.notification_type,
                "message": reminder.message,
                "remind_at": reminder.remind_at,
                "is_read": reminder.is_read,
                "task_id": reminder.task_id,
                "deadline_id": reminder.deadline_id,
            }
            for reminder in reminders
        ],
        "overall_progress": round(completed_lessons / total_lessons * 100, 1) if total_lessons else 0.0,
    }


def update_study_task_status(
    db: Session,
    student_id: int,
    task_id: int,
) -> StudyTask:
    task = _get_owned_task(db, student_id, task_id)
    if task.status == "completed":
        raise HTTPException(status_code=409, detail="This study task is already completed.")
    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    db.query(StudyNotification).filter(
        StudyNotification.task_id == task.id,
        StudyNotification.student_id == student_id,
        StudyNotification.is_read.is_(False),
    ).update({StudyNotification.is_read: True}, synchronize_session=False)
    db.commit()
    db.refresh(task)
    return task


def _get_owned_task(db: Session, student_id: int, task_id: int) -> StudyTask:
    task = (
        db.query(StudyTask)
        .options(
            joinedload(StudyTask.plan),
            joinedload(StudyTask.course),
            joinedload(StudyTask.section),
            joinedload(StudyTask.lesson),
        )
        .filter(StudyTask.id == task_id, StudyTask.student_id == student_id)
        .first()
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Study task not found.")
    return task


def reschedule_study_task(
    db: Session,
    student_id: int,
    task_id: int,
    scheduled_at: datetime,
) -> StudyTask:
    task = _get_owned_task(db, student_id, task_id)
    if not task.plan.is_active:
        raise HTTPException(status_code=409, detail="Only tasks in the active plan can be rescheduled.")
    if task.status == "completed":
        raise HTTPException(status_code=409, detail="Completed study tasks cannot be rescheduled.")
    starts_at = _utc(scheduled_at)
    now = datetime.now(timezone.utc)
    if starts_at is None or starts_at <= now:
        raise HTTPException(status_code=422, detail="Choose a future time before the plan target date.")
    local_start = starts_at.astimezone(ZoneInfo(task.plan.time_zone))
    if local_start.date() > task.plan.target_completion_date:
        raise HTTPException(status_code=422, detail="Choose a future time before the plan target date.")
    start_clock, end_clock = _TIME_WINDOWS[task.plan.preferred_time]
    if local_start.time().replace(tzinfo=None) < start_clock or local_start.time().replace(tzinfo=None) >= end_clock:
        raise HTTPException(status_code=422, detail="Reschedule within your preferred study time.")

    new_end = local_start + timedelta(minutes=task.duration_minutes)
    if new_end.time().replace(tzinfo=None) > end_clock:
        raise HTTPException(status_code=422, detail="The study task must finish within your preferred study time.")
    other_tasks = (
        db.query(StudyTask)
        .filter(
            StudyTask.plan_id == task.plan_id,
            StudyTask.student_id == student_id,
            StudyTask.id != task.id,
            StudyTask.status == "pending",
        )
        .all()
    )
    for other in other_tasks:
        other_start = _utc(other.starts_at)
        other_end = other_start + timedelta(minutes=other.duration_minutes)
        if starts_at < other_end and other_start < new_end:
            raise HTTPException(status_code=409, detail="This time overlaps another pending study task.")
    daily_limit = math.floor(task.plan.available_hours_per_day * 60)
    same_day_minutes = sum(
        other.duration_minutes
        for other in other_tasks
        if _utc(other.starts_at).date() == starts_at.date()
    )
    if same_day_minutes + task.duration_minutes > daily_limit:
        raise HTTPException(status_code=409, detail="This would exceed your available study time for that day.")

    task.starts_at = starts_at
    task.status = "pending"
    task.completed_at = None
    db.query(StudyNotification).filter(
        StudyNotification.task_id == task.id,
        StudyNotification.student_id == student_id,
        StudyNotification.notification_type == "missed_task",
        StudyNotification.is_read.is_(False),
    ).update({StudyNotification.is_read: True}, synchronize_session=False)
    upcoming = (
        db.query(StudyNotification)
        .filter(
            StudyNotification.task_id == task.id,
            StudyNotification.student_id == student_id,
            StudyNotification.notification_type == "upcoming_session",
        )
        .first()
    )
    if upcoming:
        upcoming.remind_at = starts_at - timedelta(minutes=30)
        upcoming.is_read = False
    else:
        _add_study_notification(
            db,
            student_id=student_id,
            key=f"task-upcoming-{task.id}",
            notification_type="upcoming_session",
            message=f"Upcoming study session: {task.course.title} — {task.lesson.title}.",
            remind_at=starts_at - timedelta(minutes=30),
            task_id=task.id,
        )
    db.commit()
    db.refresh(task)
    return task


def delete_study_task(db: Session, student_id: int, task_id: int) -> None:
    task = _get_owned_task(db, student_id, task_id)
    if not task.plan.is_active:
        raise HTTPException(status_code=409, detail="Only tasks in the active plan can be deleted.")
    db.delete(task)
    db.commit()


def mark_study_reminder_read(db: Session, student_id: int, reminder_id: int) -> StudyNotification:
    reminder = (
        db.query(StudyNotification)
        .filter(
            StudyNotification.id == reminder_id,
            StudyNotification.student_id == student_id,
        )
        .first()
    )
    if reminder is None:
        raise HTTPException(status_code=404, detail="Study reminder not found.")
    reminder.is_read = True
    db.commit()
    db.refresh(reminder)
    return reminder
