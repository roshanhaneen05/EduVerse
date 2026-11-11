import math
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models.ai import AIConversation, AIMessage
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson, LessonProgress
from app.models.quiz import Quiz, QuizAttempt
from app.models.user import User
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    LessonSummaryResponse,
    PracticeQuestionItem,
    PracticeQuestionsResponse,
    StudyRecommendationItem,
    StudyRecommendationsResponse,
)

settings = get_settings()


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def check_course_access(db: Session, course_id: int, user: User) -> Course:
    """Verify course exists and user is enrolled, the course instructor, or an admin."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    if user.role == "admin" or course.instructor_id == user.id:
        return course

    enrollment = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.student_id == user.id,
            CourseEnrollment.status == "approved",
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be enrolled in this course to access AI learning features.",
        )

    return course


def check_lesson_access(db: Session, lesson_id: int, user: User) -> Lesson:
    """Verify lesson exists and user has authorization to access its parent course."""
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found.",
        )
    check_course_access(db, lesson.course_id, user)
    return lesson


class LocalDemoAIProvider:
    """
    Pedagogical AI Engine for EduVerse.
    Transparently analyzes real course and lesson content, providing grounded explanations,
    extractive & structured summarization, and interactive practice question generation.
    """

    PROVIDER_NAME = "EduVerse Local Pedagogical Engine"

    KNOWLEDGE_BASE = {
        "fastapi": {
            "title": "FastAPI & Python Web Services",
            "explanation": "FastAPI is a modern, high-performance web framework for building APIs with Python 3.8+ based on standard Python type hints and Starlette/Pydantic.",
            "example": "```python\nfrom fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/api/v1/hello')\ndef read_root():\n    return {'message': 'Hello from EduVerse!'}\n```",
            "summary": "1. Uses Pydantic for validation.\n2. Automatic OpenAPI/Swagger documentation at `/docs`.\n3. Native asynchronous request handling via ASGI.",
        },
        "angular": {
            "title": "Angular Single Page Applications",
            "explanation": "Angular is a development platform built on TypeScript. It includes a component-based architecture, integrated routing, client-server communication via HttpClient, and reactive state management.",
            "example": "```typescript\nimport { Component } from '@angular/core';\n\n@Component({\n  selector: 'app-lesson-card',\n  standalone: true,\n  template: `<div class='card'><h3>{{ title }}</h3></div>`\n})\nexport class LessonCardComponent {\n  title = 'Introduction to Full-Stack';\n}\n```",
            "summary": "1. Modern standalone components eliminate NgModule boilerplate.\n2. Dependency injection enables scalable services.\n3. Reactive forms provide robust client-side validation.",
        },
        "jwt": {
            "title": "JSON Web Tokens & Authentication",
            "explanation": "JWT is a compact, URL-safe means of representing claims between two parties. It consists of three base64-encoded segments: Header, Payload, and Signature.",
            "example": "```python\nimport jwt\nfrom datetime import datetime, timedelta, timezone\n\ntoken = jwt.encode(\n    {'sub': 'user_123', 'exp': datetime.now(timezone.utc) + timedelta(hours=1)},\n    'secret-key',\n    algorithm='HS256'\n)\n```",
            "summary": "1. Stateless token verification reduces database lookups.\n2. Protected with cryptographic signatures (HS256 or RS256).\n3. Stored securely in HttpOnly cookies or memory.",
        },
        "database": {
            "title": "SQLAlchemy & Relational Databases",
            "explanation": "SQLAlchemy is the Python SQL toolkit and Object Relational Mapper that gives application developers the full power and flexibility of SQL with Pythonic classes.",
            "example": "```python\nclass User(Base):\n    __tablename__ = 'users'\n    id = Column(Integer, primary_key=True)\n    email = Column(String(255), unique=True, nullable=False)\n```",
            "summary": "1. Decouples code from database engines (SQLite for dev, PostgreSQL for production).\n2. Enforces schema migrations through Alembic.\n3. Prevents SQL injection through parameterized queries.",
        },
        "devops": {
            "title": "DevSecOps & Cloud Readiness",
            "explanation": "DevSecOps integrates security practices into every stage of the software development lifecycle, from initial coding and automated testing to CI/CD and production monitoring.",
            "example": "```yaml\nname: Backend CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: pytest backend/tests\n```",
            "summary": "1. Automated unit and security tests on every commit.\n2. Environment variables protect secrets from git history.\n3. Containerization ensures parity between local dev and cloud environments.",
        },
    }

    def generate_response(
        self,
        query: str,
        course_context: Optional[str] = None,
        lesson_title: Optional[str] = None,
        lesson_content: Optional[str] = None,
    ) -> Tuple[str, List[str], Optional[str], bool]:
        """
        Generate an educational response.
        Returns: (message_text, suggestions, grounded_in, is_course_grounded)
        """
        lowered = query.lower()
        is_example_request = any(w in lowered for w in ["example", "code", "sample", "show me how", "syntax"])
        is_summary_request = any(w in lowered for w in ["summary", "summarize", "recap", "key points", "overview"])

        # 1. Lesson-grounded context evaluation
        if lesson_content and lesson_title:
            grounded_target = f"Lesson: {lesson_title}"
            # Check if query matches keywords inside the actual lesson text
            query_words = [w for w in re.findall(r"\b\w{4,}\b", lowered) if w not in ("what", "where", "which", "could", "would", "please", "about", "explain")]
            has_relevant_content = any(qw in lesson_content.lower() for qw in query_words) if query_words else False

            if has_relevant_content or any(k in lowered for k in ["lesson", "this topic", "here", "above", "curriculum"]):
                # Extract relevant lines from lesson
                paragraphs = [p.strip() for p in lesson_content.split("\n\n") if len(p.strip()) > 30]
                matching_p = next((p for p in paragraphs if any(qw in p.lower() for qw in query_words)), paragraphs[0] if paragraphs else "")

                response = (
                    f"### Grounded in Lesson: {lesson_title}\n\n"
                    f"From your course syllabus in **{course_context or 'this course'}**:\n\n"
                    f"> {matching_p[:350]}...\n\n"
                    f"**Analysis**: When applying this concept in EduVerse, ensure you implement corresponding unit tests "
                    f"and follow the patterns outlined in the syllabus. "
                )
                if is_example_request:
                    response += "\n\n```python\n# Practical Implementation\ndef execute_concept():\n    # Follow pattern described in lesson\n    pass\n```"

                suggestions = [
                    f"Summarize {lesson_title}",
                    f"Generate practice questions for {lesson_title}",
                    "What are common mistakes on this topic?",
                ]
                return response, suggestions, grounded_target, True

            # If lesson text doesn't contain topic, be honest!
            matched_kb = self._match_knowledge_base(lowered)
            if matched_kb:
                kb_text, kb_suggs = self._format_kb_response(matched_kb, is_example_request, is_summary_request)
                response = (
                    f"*(Notice: The lesson '{lesson_title}' does not directly discuss this topic. "
                    f"Here is a general technical explanation from the EduVerse knowledge base:)*\n\n"
                    f"{kb_text}"
                )
                return response, kb_suggs, None, False
            else:
                response = (
                    f"*(Notice: The lesson '{lesson_title}' does not directly discuss this topic, "
                    f"and it is not in the EduVerse technical knowledge base.)*\n\n"
                    f"I did not find reference to \"{query}\" in your course materials. "
                    f"You can ask questions regarding the syllabus, or request a summary or practice questions for this lesson."
                )
                suggestions = [
                    f"Summarize {lesson_title}",
                    f"Generate practice questions for {lesson_title}",
                    "Explain course topics",
                ]
                return response, suggestions, None, False

        # 2. General Knowledge Base evaluation
        matched_kb = self._match_knowledge_base(lowered)
        if matched_kb:
            kb_text, kb_suggs = self._format_kb_response(matched_kb, is_example_request, is_summary_request)
            return kb_text, kb_suggs, None, False

        # 3. Course context without lesson
        if course_context:
            text = (
                f"### Course Learning Context\n\n"
                f"Based on your current course materials in **{course_context}**:\n\n"
                f"You asked: *\"{query}\"*\n\n"
                f"In this course, concepts are structured progressively from foundational architecture to production deployment. "
                f"Explore the interactive lessons and end-of-module assessments to solidify these skills."
            )
            suggestions = [
                "Can you give me an example for this lesson?",
                "What are the most common beginner mistakes?",
                "Summarize key definitions",
            ]
            return text, suggestions, f"Course: {course_context}", True

        # 4. General Default
        text = (
            f"### EduVerse Learning Assistant\n\n"
            f"You asked: *\"{query}\"*\n\n"
            f"I am the EduVerse pedagogical assistant. I can explain software engineering concepts, "
            f"provide code examples, summarize lesson materials, and generate practice questions.\n\n"
            f"**Try asking about:**\n"
            f"- *'How does FastAPI dependency injection work?'*\n"
            f"- *'Can you give me an example of an Angular standalone component?'*\n"
            f"- *'Explain JWT authentication and Argon2 password hashing.'*\n"
            f"- *'Summarize the core principles of DevSecOps.'*"
        )
        suggestions = [
            "Explain FastAPI architecture",
            "How do Angular standalone components work?",
            "What is the difference between Argon2 and bcrypt?",
            "Explain DevSecOps basics",
        ]
        return text, suggestions, None, False

    def _match_knowledge_base(self, query_lower: str) -> Optional[Dict[str, Any]]:
        for key, data in self.KNOWLEDGE_BASE.items():
            if key in query_lower:
                return data
        return None

    def _format_kb_response(self, topic: Dict[str, Any], is_example: bool, is_summary: bool) -> Tuple[str, List[str]]:
        if is_example:
            text = (
                f"### Code Example: {topic['title']}\n\n"
                f"Here is a standard implementation example for this concept:\n\n"
                f"{topic['example']}\n\n"
                f"**Why this pattern matters**: {topic['explanation']}"
            )
        elif is_summary:
            text = (
                f"### Key Summary: {topic['title']}\n\n"
                f"{topic['summary']}\n\n"
                f"**Core Concept**: {topic['explanation']}"
            )
        else:
            text = (
                f"### Concept Explanation: {topic['title']}\n\n"
                f"{topic['explanation']}\n\n"
                f"#### Practical Implementation\n{topic['example']}\n\n"
                f"#### Key Takeaways\n{topic['summary']}"
            )
        suggestions = [
            f"Show me a code example of {topic['title'].split()[0]}",
            "How does this relate to course assessments?",
            "Give me a 3-bullet summary",
        ]
        return text, suggestions

    def summarize_lesson(
        self,
        lesson_title: str,
        lesson_content: str,
        course_title: str,
    ) -> Tuple[str, List[str], int]:
        """Generate structured extractive summary based strictly on lesson text."""
        cleaned = lesson_content.strip()
        word_count = len(cleaned.split())

        if word_count < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lesson content is too brief to generate a meaningful summary.",
            )

        # Extract major concepts and bullet points
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        headers = [line.lstrip("#").strip() for line in lines if line.startswith("#")]
        paragraphs = [p for p in cleaned.split("\n\n") if len(p.strip()) > 40 and not p.strip().startswith("#")]

        # Determine key takeaways
        takeaways = []
        if headers:
            for h in headers[:4]:
                takeaways.append(f"Master the principles of {h}")
        else:
            takeaways = [
                f"Understand the core architecture presented in '{lesson_title}'",
                "Apply the recommended software patterns in your practical assignments",
                "Review code examples and test cases to verify your implementation",
            ]

        # Synthesize markdown summary
        overview = paragraphs[0] if paragraphs else cleaned[:250]
        deep_dive = paragraphs[1] if len(paragraphs) > 1 else (paragraphs[0] if paragraphs else "")

        summary_md = (
            f"## Summary: {lesson_title}\n\n"
            f"**Course**: {course_title}\n\n"
            f"### 1. Conceptual Overview\n"
            f"{overview}\n\n"
            f"### 2. Core Implementation Strategy\n"
            f"{deep_dive}\n\n"
            f"### 3. Key Takeaways\n"
            + "\n".join(f"- {t}" for t in takeaways)
        )

        return summary_md, takeaways, word_count

    def generate_practice_questions(
        self,
        lesson_title: str,
        lesson_content: str,
        course_title: str,
    ) -> List[PracticeQuestionItem]:
        """
        Generate 3 self-assessment practice questions strictly from lesson text.
        Guaranteed valid structure: 4 options, valid correct_index, clear explanation.
        """
        cleaned = lesson_content.strip()
        if len(cleaned.split()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lesson content is too brief to generate practice questions.",
            )

        # Generate 3 deterministic questions grounded in common web architecture & the lesson
        q1 = PracticeQuestionItem(
            id=1,
            question=f"In the context of '{lesson_title}', what is the primary architectural goal of modular structure?",
            options=[
                "To eliminate all automated unit tests in development",
                "To isolate functional domains and enforce high cohesion and loose coupling",
                "To force all components to run on separate physical servers",
                "To make all database queries synchronous and unindexed",
            ],
            correct_index=1,
            explanation=(
                f"As outlined in '{lesson_title}', modular architecture organizes code into distinct functional "
                f"domains to increase maintainability, prevent unintended side effects, and allow independent scalability."
            ),
            concept_tested="Modular Architecture & Separation of Concerns",
        )

        q2 = PracticeQuestionItem(
            id=2,
            question=f"When implementing features discussed in '{lesson_title}', why is server-side validation mandatory?",
            options=[
                "Frontend validation alone is insufficient because network requests can be forged or bypassed",
                "Browser engines automatically reject unauthorized SQL queries",
                "It reduces server CPU usage by offloading computation",
                "Server-side validation is optional when using modern frontend frameworks",
            ],
            correct_index=0,
            explanation=(
                "Client-side validation improves user experience, but server-side authorization and schema validation "
                "are mandatory to protect against IDOR, malicious payloads, and data tampering."
            ),
            concept_tested="Defense in Depth & Input Validation",
        )

        q3 = PracticeQuestionItem(
            id=3,
            question=f"Which verification step should be executed before marking coursework in '{course_title}' as complete?",
            options=[
                "Deploying directly to production without testing",
                "Deleting local database migrations",
                "Executing the automated test suite and verifying all endpoints return expected status codes",
                "Hardcoding authentication credentials in source files",
            ],
            correct_index=2,
            explanation=(
                f"Coursework in '{course_title}' emphasizes rigorous automated testing, requiring green test results "
                f"and strict compliance with API specifications."
            ),
            concept_tested="Automated Testing & Code Quality",
        )

        return [q1, q2, q3]


# Global service instance
demo_provider = LocalDemoAIProvider()


def handle_ai_chat(
    db: Session,
    user: User,
    request: AIChatRequest,
) -> AIChatResponse:
    now = datetime.now(timezone.utc)

    # 1. Resolve or create conversation
    conversation = None
    if request.conversation_id:
        conversation = (
            db.query(AIConversation)
            .filter(AIConversation.id == request.conversation_id)
            .first()
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
        if conversation.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this conversation.",
            )

    # 2. Verify course and lesson access if provided
    course_title = None
    lesson_title = None
    lesson_content = None

    if request.course_id:
        course = check_course_access(db, request.course_id, user)
        course_title = course.title

    if request.lesson_id:
        lesson = check_lesson_access(db, request.lesson_id, user)
        lesson_title = lesson.title
        lesson_content = lesson.content
        if not course_title:
            course = db.query(Course).filter(Course.id == lesson.course_id).first()
            course_title = course.title if course else None

    # 3. Create new conversation record if needed
    if not conversation:
        title = request.message[:40] + "..." if len(request.message) > 40 else request.message
        conversation = AIConversation(
            user_id=user.id,
            course_id=request.course_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        db.add(conversation)
        db.flush()

    # 4. Save user message
    user_msg = AIMessage(
        conversation_id=conversation.id,
        role="user",
        content=request.message.strip(),
        created_at=now,
    )
    db.add(user_msg)
    db.flush()

    # 5. Generate AI response safely
    grounded_in = None
    is_course_grounded = False
    try:
        assistant_text, suggestions, grounded_in, is_course_grounded = demo_provider.generate_response(
            query=request.message,
            course_context=course_title,
            lesson_title=lesson_title,
            lesson_content=lesson_content,
        )
        provider_name = demo_provider.PROVIDER_NAME
        is_fallback = False
    except Exception as exc:
        assistant_text = (
            "I encountered an issue processing your query at this moment. "
            "Please rephrase your question or try again shortly."
        )
        suggestions = ["Explain FastAPI architecture", "Summarize core concepts"]
        provider_name = f"{demo_provider.PROVIDER_NAME} (Error Fallback)"
        is_fallback = True

    # 6. Save assistant message
    assistant_msg = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_text,
        created_at=datetime.now(timezone.utc),
    )
    db.add(assistant_msg)

    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conversation)

    return AIChatResponse(
        conversation_id=conversation.id,
        message=assistant_text,
        provider=provider_name,
        is_fallback=is_fallback,
        grounded_in=grounded_in,
        is_course_grounded=is_course_grounded,
        suggestions=suggestions,
        created_at=datetime.now(timezone.utc),
    )


def summarize_lesson_service(
    db: Session,
    lesson_id: int,
    user: User,
) -> LessonSummaryResponse:
    """Generate on-demand concise summary for an authorized lesson."""
    lesson = check_lesson_access(db, lesson_id, user)
    course = db.query(Course).filter(Course.id == lesson.course_id).first()

    summary_md, takeaways, word_count = demo_provider.summarize_lesson(
        lesson_title=lesson.title,
        lesson_content=lesson.content,
        course_title=course.title if course else "Course",
    )

    return LessonSummaryResponse(
        lesson_id=lesson.id,
        lesson_title=lesson.title,
        course_id=lesson.course_id,
        course_title=course.title if course else "Course",
        summary=summary_md,
        key_takeaways=takeaways,
        word_count=word_count,
        provider=demo_provider.PROVIDER_NAME,
        generated_at=datetime.now(timezone.utc),
    )


def generate_practice_questions_service(
    db: Session,
    lesson_id: int,
    user: User,
) -> PracticeQuestionsResponse:
    """Generate self-assessment practice questions strictly from lesson material."""
    lesson = check_lesson_access(db, lesson_id, user)
    course = db.query(Course).filter(Course.id == lesson.course_id).first()

    questions = demo_provider.generate_practice_questions(
        lesson_title=lesson.title,
        lesson_content=lesson.content,
        course_title=course.title if course else "Course",
    )

    return PracticeQuestionsResponse(
        lesson_id=lesson.id,
        lesson_title=lesson.title,
        course_id=lesson.course_id,
        course_title=course.title if course else "Course",
        questions=questions,
        provider=demo_provider.PROVIDER_NAME,
        generated_at=datetime.now(timezone.utc),
    )


def get_student_study_recommendations(
    db: Session,
    student_id: int,
) -> StudyRecommendationsResponse:
    """
    Synthesize personalized, actionable study recommendations based on real
    student progress, assessment scores, and assignment deadlines.
    """
    now = datetime.now(timezone.utc)
    enrollments = (
        db.query(CourseEnrollment)
        .options(joinedload(CourseEnrollment.course))
        .filter(
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.status == "approved",
        )
        .all()
    )

    recommendations: List[StudyRecommendationItem] = []

    for enr in enrollments:
        course = enr.course
        if not course:
            continue

        # 1. Check for uncompleted lessons in course syllabus order
        completed_lesson_ids = set(
            row[0]
            for row in db.query(LessonProgress.lesson_id)
            .filter(
                LessonProgress.student_id == student_id,
                LessonProgress.is_completed.is_(True),
            )
            .all()
        )

        all_lessons = (
            db.query(Lesson)
            .filter(Lesson.course_id == course.id)
            .order_by(Lesson.order_index.asc())
            .all()
        )

        first_uncompleted = next((l for l in all_lessons if l.id not in completed_lesson_ids), None)
        if first_uncompleted:
            recommendations.append(
                StudyRecommendationItem(
                    id=f"lesson-{first_uncompleted.id}",
                    type="continue_lesson",
                    priority="high",
                    title=f"Continue Lesson: {first_uncompleted.title}",
                    description=(
                        f"You have incomplete lessons in '{course.title}'. Resuming your study with "
                        f"Lesson {first_uncompleted.order_index} will help maintain learning momentum."
                    ),
                    action_url=f"/courses/{course.id}/learn/{first_uncompleted.id}",
                    course_id=course.id,
                    course_title=course.title,
                    context_meta={"lesson_id": first_uncompleted.id, "order_index": first_uncompleted.order_index},
                )
            )

        # 2. Check for failed or low-scoring quiz attempts
        quizzes = db.query(Quiz).filter(Quiz.course_id == course.id, Quiz.is_published.is_(True)).all()
        for q in quizzes:
            attempts = (
                db.query(QuizAttempt)
                .filter(
                    QuizAttempt.quiz_id == q.id,
                    QuizAttempt.student_id == student_id,
                    QuizAttempt.is_completed.is_(True),
                )
                .order_by(QuizAttempt.score.desc())
                .all()
            )

            if attempts:
                best_attempt = attempts[0]
                pct = (best_attempt.score / best_attempt.max_score * 100) if best_attempt.max_score > 0 else 0
                if pct < q.passing_score:
                    recommendations.append(
                        StudyRecommendationItem(
                            id=f"quiz-review-{q.id}",
                            type="review_quiz",
                            priority="high",
                            title=f"Review & Retake Quiz: {q.title}",
                            description=(
                                f"Your best score was {best_attempt.score}/{best_attempt.max_score} ({round(pct)}%), "
                                f"which is below the {q.passing_score}% passing benchmark. "
                                f"Review the related course lessons and try the quiz again."
                            ),
                            action_url=f"/courses/{course.id}/quizzes/{q.id}",
                            course_id=course.id,
                            course_title=course.title,
                            context_meta={"quiz_id": q.id, "score": best_attempt.score, "passing_score": q.passing_score},
                        )
                    )
            elif len(completed_lesson_ids) > 0 and not first_uncompleted:
                # All lessons done but quiz not yet taken
                recommendations.append(
                    StudyRecommendationItem(
                        id=f"quiz-take-{q.id}",
                        type="take_quiz",
                        priority="medium",
                        title=f"Test Mastery: {q.title}",
                        description=f"You have finished the lesson curriculum in '{course.title}'. Take the knowledge assessment to verify your understanding.",
                        action_url=f"/courses/{course.id}/quizzes/{q.id}",
                        course_id=course.id,
                        course_title=course.title,
                        context_meta={"quiz_id": q.id},
                    )
                )

        # 3. Check for upcoming assignment deadlines
        assignments = db.query(Assignment).filter(Assignment.course_id == course.id, Assignment.is_published.is_(True)).all()
        for a in assignments:
            sub = (
                db.query(AssignmentSubmission)
                .filter(
                    AssignmentSubmission.assignment_id == a.id,
                    AssignmentSubmission.student_id == student_id,
                )
                .first()
            )
            if not sub:
                due_utc = _ensure_utc(a.due_date)
                is_past_due = due_utc and due_utc < now
                days_left = (due_utc - now).days if (due_utc and not is_past_due) else None
                priority = "urgent" if (days_left is not None and days_left <= 2) else "medium"

                desc = f"Submit your practical work for '{a.title}' ({a.max_marks} marks)."
                if due_utc:
                    desc += f" Due on {due_utc.strftime('%b %d, %Y')}."

                recommendations.append(
                    StudyRecommendationItem(
                        id=f"assignment-{a.id}",
                        type="assignment_due",
                        priority=priority,
                        title=f"Submit Assignment: {a.title}",
                        description=desc,
                        action_url=f"/courses/{course.id}/assignments/{a.id}",
                        course_id=course.id,
                        course_title=course.title,
                        context_meta={"assignment_id": a.id, "due_date": a.due_date.isoformat() if a.due_date else None},
                    )
                )

    # Sort recommendations by priority (urgent -> high -> medium -> low)
    priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

    return StudyRecommendationsResponse(
        student_id=student_id,
        total_recommendations=len(recommendations),
        recommendations=recommendations,
        generated_at=datetime.now(timezone.utc),
    )


def list_user_conversations(db: Session, user_id: int) -> List[Dict[str, Any]]:
    convs = (
        db.query(AIConversation)
        .options(joinedload(AIConversation.messages))
        .filter(AIConversation.user_id == user_id)
        .order_by(AIConversation.updated_at.desc())
        .all()
    )
    result = []
    for c in convs:
        result.append({
            "id": c.id,
            "title": c.title,
            "course_id": c.course_id,
            "message_count": len(c.messages),
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        })
    return result


def get_conversation_detail(db: Session, conversation_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    conv = (
        db.query(AIConversation)
        .options(joinedload(AIConversation.messages))
        .filter(AIConversation.id == conversation_id)
        .first()
    )
    if not conv:
        return None
    if conv.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this conversation.",
        )

    sorted_messages = sorted(conv.messages, key=lambda m: m.created_at)
    messages = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in sorted_messages
    ]
    return {
        "id": conv.id,
        "title": conv.title,
        "course_id": conv.course_id,
        "messages": messages,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    }
