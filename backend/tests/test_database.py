import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base, check_db_connection, engine, SessionLocal
from app.models.ai import AIConversation, AIMessage
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson, LessonProgress
from app.models.quiz import (
    AnswerOption,
    Question,
    Quiz,
    QuizAttempt,
    QuizAttemptAnswer,
)
from app.models.user import User, UserRole


@pytest.fixture
def db_session():
    """Provides a transactional database session for each database test."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_database_connectivity(db_session):
    """Test 1: Verify database connectivity and query execution."""
    assert check_db_connection() is True


def test_create_user(db_session):
    """Test 2: Verify user creation with password_hash, role, and timestamps."""
    user = User(
        email="test.user@eduverse.io",
        full_name="Database Test User",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "test.user@eduverse.io"
    assert user.password_hash.startswith("$argon2id$")
    assert user.role == "student"
    assert user.is_active is True
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)


def test_unique_email_enforcement(db_session):
    """Test 3: Verify unique email constraint raises IntegrityError on duplication."""
    u1 = User(
        email="duplicate@eduverse.io",
        full_name="First User",
        password_hash="hash1",
        role=UserRole.STUDENT.value,
    )
    db_session.add(u1)
    db_session.commit()

    u2 = User(
        email="duplicate@eduverse.io",
        full_name="Second User",
        password_hash="hash2",
        role=UserRole.STUDENT.value,
    )
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_course_and_instructor_relationship(db_session):
    """Test 4: Verify course creation and bidirectional instructor relationship."""
    instructor = User(
        email="instructor.course@eduverse.io",
        full_name="Prof. Test",
        password_hash="hash_instructor",
        role=UserRole.INSTRUCTOR.value,
    )
    db_session.add(instructor)
    db_session.commit()

    course = Course(
        title="Distributed Systems with Python",
        description="Comprehensive course on distributed architectures.",
        category="Cloud Computing",
        difficulty="Advanced",
        is_published=True,
        instructor_id=instructor.id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    db_session.refresh(instructor)

    assert course.instructor.id == instructor.id
    assert course in instructor.courses


def test_student_enrollment(db_session):
    """Test 5: Verify student enrollment in a course."""
    student = User(
        email="enrolled.student@eduverse.io",
        full_name="Enrolled Student",
        password_hash="hash_student",
        role=UserRole.STUDENT.value,
    )
    instructor = User(
        email="inst.enroll@eduverse.io",
        full_name="Instructor Enroll",
        password_hash="hash_inst",
        role=UserRole.INSTRUCTOR.value,
    )
    db_session.add_all([student, instructor])
    db_session.commit()

    course = Course(
        title="Web Security Fundamentals",
        description="Security course description.",
        category="Security",
        difficulty="Beginner",
        instructor_id=instructor.id,
    )
    db_session.add(course)
    db_session.commit()

    enrollment = CourseEnrollment(
        student_id=student.id,
        course_id=course.id,
        completion_percentage=25.0,
    )
    db_session.add(enrollment)
    db_session.commit()
    db_session.refresh(enrollment)

    assert enrollment.id is not None
    assert enrollment.student.id == student.id
    assert enrollment.course.id == course.id
    assert enrollment.completion_percentage == 25.0


def test_prevent_duplicate_enrollment(db_session):
    """Test 6: Verify a student cannot enroll in the same course twice."""
    student = User(
        email="dup.student@eduverse.io",
        full_name="Duplicate Student",
        password_hash="hash",
        role=UserRole.STUDENT.value,
    )
    instructor = User(
        email="dup.inst@eduverse.io",
        full_name="Instructor",
        password_hash="hash",
        role=UserRole.INSTRUCTOR.value,
    )
    db_session.add_all([student, instructor])
    db_session.commit()

    course = Course(
        title="Duplicate Enrollment Test Course",
        description="Test desc.",
        category="DevOps",
        instructor_id=instructor.id,
    )
    db_session.add(course)
    db_session.commit()

    e1 = CourseEnrollment(student_id=student.id, course_id=course.id)
    db_session.add(e1)
    db_session.commit()

    e2 = CourseEnrollment(student_id=student.id, course_id=course.id)
    db_session.add(e2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_lesson_progress_uniqueness(db_session):
    """Test 7: Verify unique lesson progress per student and lesson."""
    student = User(
        email="prog.student@eduverse.io",
        full_name="Progress Student",
        password_hash="hash",
        role=UserRole.STUDENT.value,
    )
    instructor = User(
        email="prog.inst@eduverse.io",
        full_name="Progress Instructor",
        password_hash="hash",
        role=UserRole.INSTRUCTOR.value,
    )
    db_session.add_all([student, instructor])
    db_session.commit()

    course = Course(
        title="Progress Test Course",
        description="Test desc.",
        category="Web Development",
        instructor_id=instructor.id,
    )
    db_session.add(course)
    db_session.commit()

    lesson = Lesson(
        course_id=course.id,
        title="Lesson 1: Intro",
        content="Intro content here.",
        order_index=1,
    )
    db_session.add(lesson)
    db_session.commit()

    p1 = LessonProgress(student_id=student.id, lesson_id=lesson.id, is_completed=True)
    db_session.add(p1)
    db_session.commit()

    p2 = LessonProgress(student_id=student.id, lesson_id=lesson.id, is_completed=True)
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_quiz_and_question_relationships(db_session):
    """Test 8: Verify quiz, question, and answer option cascading relationships."""
    instructor = User(
        email="quiz.inst@eduverse.io",
        full_name="Quiz Instructor",
        password_hash="hash",
        role=UserRole.INSTRUCTOR.value,
    )
    db_session.add(instructor)
    db_session.commit()

    course = Course(
        title="Quiz Master Course",
        description="Course with quizzes.",
        category="General",
        instructor_id=instructor.id,
    )
    db_session.add(course)
    db_session.commit()

    quiz = Quiz(
        course_id=course.id,
        title="Module 1 Quiz",
        passing_score=80,
    )
    db_session.add(quiz)
    db_session.commit()

    q1 = Question(
        quiz_id=quiz.id,
        question_text="What is 2 + 2?",
        order_index=1,
        points=5,
    )
    db_session.add(q1)
    db_session.commit()

    opt1 = AnswerOption(question_id=q1.id, option_text="3", is_correct=False)
    opt2 = AnswerOption(question_id=q1.id, option_text="4", is_correct=True)
    db_session.add_all([opt1, opt2])
    db_session.commit()

    db_session.refresh(quiz)
    assert len(quiz.questions) == 1
    assert quiz.questions[0].points == 5
    assert len(quiz.questions[0].options) == 2
    assert any(opt.is_correct for opt in quiz.questions[0].options)


def test_quiz_attempt_relationships(db_session):
    """Test 9: Verify quiz attempt and attempt answers relationships."""
    student = User(
        email="attempt.student@eduverse.io",
        full_name="Attempt Student",
        password_hash="hash",
        role=UserRole.STUDENT.value,
    )
    instructor = User(
        email="attempt.inst@eduverse.io",
        full_name="Attempt Instructor",
        password_hash="hash",
        role=UserRole.INSTRUCTOR.value,
    )
    db_session.add_all([student, instructor])
    db_session.commit()

    course = Course(
        title="Attempt Course",
        description="Desc",
        category="Testing",
        instructor_id=instructor.id,
    )
    db_session.add(course)
    db_session.commit()

    quiz = Quiz(course_id=course.id, title="Assessment", passing_score=70)
    db_session.add(quiz)
    db_session.commit()

    question = Question(quiz_id=quiz.id, question_text="Question 1", points=10)
    db_session.add(question)
    db_session.commit()

    option = AnswerOption(question_id=question.id, option_text="Answer A", is_correct=True)
    db_session.add(option)
    db_session.commit()

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        student_id=student.id,
        score=100.0,
        total_points=10,
        passed=True,
    )
    db_session.add(attempt)
    db_session.commit()

    attempt_answer = QuizAttemptAnswer(
        attempt_id=attempt.id,
        question_id=question.id,
        selected_option_id=option.id,
        is_correct=True,
        awarded_points=10,
    )
    db_session.add(attempt_answer)
    db_session.commit()

    db_session.refresh(attempt)
    assert len(attempt.answers) == 1
    assert attempt.answers[0].awarded_points == 10
    assert attempt.answers[0].is_correct is True


def test_foreign_key_enforcement(db_session):
    """Test 10: Verify SQLite foreign key pragma enforces referential integrity."""
    # Attempting to create a course with an invalid instructor_id must raise IntegrityError
    invalid_course = Course(
        title="Orphan Course",
        description="Course without valid instructor.",
        category="Testing",
        instructor_id=999999,  # Non-existent ID
    )
    db_session.add(invalid_course)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

