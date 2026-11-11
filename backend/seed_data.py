"""Idempotently add EduVerse demo data to the existing SQLite database."""

from __future__ import annotations

import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypeVar

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import (
    AIConversation,
    AIMessage,
    AnswerOption,
    Assignment,
    AssignmentSubmission,
    Course,
    CourseAnnouncement,
    CourseDiscussion,
    CourseEnrollment,
    CourseSection,
    DiscussionReply,
    LearningMaterial,
    Lesson,
    Question,
    Quiz,
    QuizAttempt,
    QuizAttemptAnswer,
    User,
)
from app.security.password import hash_password, validate_password_strength
from app.services.storage import get_storage_provider


BACKEND_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BACKEND_DIR / "data" / "eduverse.db"
ModelT = TypeVar("ModelT", bound=Base)

STUDENTS = (
    ("Alex Rivera", "alex.rivera@eduverse.io"),
    ("Priya Patel", "priya.patel@eduverse.io"),
    ("Jordan Taylor", "jordan.taylor@eduverse.io"),
    ("Amina Okafor", "amina.okafor@eduverse.io"),
    ("Leo Martinez", "leo.martinez@eduverse.io"),
)
INSTRUCTORS = (
    ("Dr. Sarah Chen", "sarah.chen@eduverse.io"),
    ("Marcus Vance", "marcus.vance@eduverse.io"),
)

COURSES = (
    {
        "title": "Python Programming",
        "category": "Programming",
        "difficulty": "Beginner",
        "description": "Build a practical foundation in Python, from readable syntax and data structures to reusable functions and small applications.",
        "sections": (
            (
                "Python foundations",
                "Learn the language's core syntax and data types.",
                (
                    ("Getting started with Python", "Install Python, run a script, and use the interactive interpreter. Practice variables, expressions, and clear output."),
                    ("Strings, numbers, and collections", "Work with strings, numeric values, lists, tuples, and dictionaries. Choose a suitable collection for each problem."),
                ),
            ),
            (
                "Writing useful programs",
                "Organize code and handle common application tasks.",
                (
                    ("Decisions and iteration", "Use conditional expressions and loops to control program flow. Trace each branch with small examples."),
                    ("Functions and files", "Create functions with clear inputs and outputs, then read and write text files safely."),
                ),
            ),
        ),
        "quiz": (
            ("Python fundamentals check", "Check your understanding of everyday Python concepts."),
            (
                ("Which Python collection stores values as key-value pairs?", (("List", False), ("Dictionary", True), ("Tuple", False), ("Set", False))),
                ("What does a function's return statement do?", (("Repeats the function", False), ("Sends a result back to its caller", True), ("Imports a module", False), ("Creates a loop", False))),
                ("Which keyword starts a conditional branch in Python?", (("when", False), ("if", True), ("select", False), ("case", False))),
            ),
        ),
        "discussion": ("What are you building with Python?", "Share a small automation or application idea and the first step you would take to build it."),
        "material": "A concise Python reference covering variables, collections, functions, loops, and file handling, with short practice prompts.",
        "ai_prompt": "How can I break a small Python project into functions?",
        "ai_answer": "Start by listing the distinct tasks, give each task a clear function name, and pass data explicitly between functions. Keep the entry point small, then test each function with a representative input.",
    },
    {
        "title": "Java Programming",
        "category": "Programming",
        "difficulty": "Beginner",
        "description": "Learn Java fundamentals and object-oriented design while building small, testable command-line programs.",
        "sections": (
            (
                "Java essentials",
                "Understand the Java toolchain and basic language constructs.",
                (
                    ("Your first Java program", "Compile and run a Java class. Explore the role of the main method and how source files relate to classes."),
                    ("Types and control flow", "Use primitive and reference types, expressions, conditions, and loops to represent common tasks."),
                ),
            ),
            (
                "Object-oriented programming",
                "Model application concepts with classes and reusable behavior.",
                (
                    ("Classes, objects, and constructors", "Define classes with fields and methods, then create instances with constructors that preserve valid state."),
                    ("Collections and exceptions", "Use lists and maps to manage groups of values, and handle expected errors with focused exception handling."),
                ),
            ),
        ),
        "quiz": (
            ("Java essentials check", "Review core syntax and object-oriented Java."),
            (
                ("Which method is the conventional entry point of a Java application?", (("start()", False), ("main()", True), ("runApp()", False), ("init()", False))),
                ("What is an instance of a class?", (("A package", False), ("An object created from that class", True), ("A compiler flag", False), ("A comment", False))),
                ("Which collection is designed to store key-value mappings?", (("ArrayList", False), ("HashMap", True), ("HashSet", False), ("Queue", False))),
            ),
        ),
        "discussion": ("When would you create a class?", "Describe a real-world concept that could be modeled as a Java class, including one field and one useful method."),
        "material": "A Java study sheet on classes, constructors, primitive types, collections, and exception handling.",
        "ai_prompt": "Can you explain the difference between a class and an object?",
        "ai_answer": "A class is a definition describing data and behavior; an object is a particular instance created from that definition, with its own state.",
    },
    {
        "title": "Web Development",
        "category": "Web Development",
        "difficulty": "Beginner",
        "description": "Create accessible, responsive web pages and understand how browser interfaces communicate with web services.",
        "sections": (
            (
                "The browser platform",
                "Build semantic page structure and present it clearly.",
                (
                    ("Semantic HTML", "Choose elements that describe page structure and meaning. Build a simple article page with headings, navigation, and landmarks."),
                    ("CSS layout and responsive design", "Use the box model, flexible layouts, and media queries to make pages work across screen sizes."),
                ),
            ),
            (
                "Interactive web applications",
                "Add behavior and connect a user interface to HTTP services.",
                (
                    ("JavaScript and the DOM", "Respond to user actions, update the document, and keep interface behavior predictable."),
                    ("HTTP APIs and accessibility", "Read JSON from an HTTP endpoint and provide keyboard-friendly controls and useful labels."),
                ),
            ),
        ),
        "quiz": (
            ("Web development foundations", "Check knowledge of browser markup, styles, and requests."),
            (
                ("Which HTML element represents the main content of a page?", (("aside", False), ("main", True), ("footer", False), ("meta", False))),
                ("What does a CSS media query commonly enable?", (("Database indexing", False), ("Responsive styles for different viewport conditions", True), ("JavaScript compilation", False), ("Image compression", False))),
                ("Which HTTP method is commonly used to retrieve a resource?", (("GET", True), ("PATCH", False), ("DELETE", False), ("TRACE", False))),
            ),
        ),
        "discussion": ("How do you make a page easier to use?", "Share one accessibility or responsive-design improvement you would add to a course website."),
        "material": "A web development checklist for semantic markup, responsive CSS, accessible forms, and JSON API requests.",
        "ai_prompt": "What is a good starting checklist for an accessible form?",
        "ai_answer": "Associate every input with a visible label, group related controls, expose validation errors in text, preserve keyboard access, and test the form without a mouse.",
    },
    {
        "title": "Cloud Computing",
        "category": "Cloud Computing",
        "difficulty": "Intermediate",
        "description": "Explore cloud service models, resilient architecture, identity controls, and the operational trade-offs of running applications in the cloud.",
        "sections": (
            (
                "Cloud concepts",
                "Understand service models and design for failure.",
                (
                    ("Cloud service models", "Compare infrastructure, platform, and software services and identify who operates each layer."),
                    ("Regions, availability, and resilience", "Learn how regions and availability zones affect reliability, latency, and recovery planning."),
                ),
            ),
            (
                "Operating cloud workloads",
                "Apply basic security, scaling, and observability practices.",
                (
                    ("Identity and least privilege", "Grant workload identities only the permissions needed for their tasks and review access regularly."),
                    ("Scaling and monitoring", "Use health signals, logs, and metrics to understand demand and choose an appropriate scaling strategy."),
                ),
            ),
        ),
        "quiz": (
            ("Cloud architecture check", "Review service models, availability, and identity principles."),
            (
                ("What is a primary goal of least-privilege access?", (("Give every service administrator rights", False), ("Grant only the permissions required for a task", True), ("Disable authentication", False), ("Share one account across teams", False))),
                ("Why distribute workloads across availability zones?", (("To avoid using networks", False), ("To reduce dependence on a single failure domain", True), ("To remove the need for backups", False), ("To make credentials public", False))),
                ("Which signal is especially useful for diagnosing a request failure?", (("A correlated application log and trace", True), ("The desktop wallpaper", False), ("A local browser bookmark", False), ("A source-code filename alone", False))),
            ),
        ),
        "discussion": ("Planning for a cloud outage", "Which user-facing feature should remain available during a partial service outage, and how could the system degrade gracefully?"),
        "material": "A cloud architecture guide to service models, availability zones, least privilege, monitoring, and recovery objectives.",
        "ai_prompt": "How should I choose a recovery objective for a small service?",
        "ai_answer": "Start with the business impact of downtime and data loss, agree on acceptable recovery time and recovery point with stakeholders, then validate those objectives with tested backups and recovery exercises.",
    },
    {
        "title": "DevOps Engineering",
        "category": "DevOps",
        "difficulty": "Intermediate",
        "description": "Connect development and operations with versioned infrastructure, automated delivery, observability, and continuous improvement.",
        "sections": (
            (
                "Delivery foundations",
                "Make changes repeatable from source control through deployment.",
                (
                    ("Version control and collaboration", "Use small reviewable changes, branches, and clear commit history to collaborate safely."),
                    ("Continuous integration", "Automate linting and tests so that each proposed change receives fast, repeatable feedback."),
                ),
            ),
            (
                "Reliable operations",
                "Improve deployment safety and learn from production signals.",
                (
                    ("Deployment strategies", "Compare rolling, blue-green, and canary releases, including how to detect and reverse a bad rollout."),
                    ("Observability and incident learning", "Use metrics, logs, and traces to diagnose issues and turn incident findings into concrete improvements."),
                ),
            ),
        ),
        "quiz": (
            ("DevOps practices check", "Assess understanding of delivery automation and reliable operations."),
            (
                ("What is a key benefit of continuous integration?", (("It eliminates the need for testing", False), ("It gives frequent automated feedback on changes", True), ("It prevents code review", False), ("It requires manual releases for every commit", False))),
                ("What is a canary deployment?", (("A release to a small subset of traffic before wider rollout", True), ("A database backup format", False), ("A permanent development branch", False), ("A type of code formatter", False))),
                ("Which practice helps teams learn after an incident?", (("A blameless review focused on system improvements", True), ("Deleting monitoring data", False), ("Avoiding written timelines", False), ("Disabling alerts permanently", False))),
            ),
        ),
        "discussion": ("A useful CI pipeline", "Which fast automated checks should run on every change, and which slower checks can run later?"),
        "material": "A DevOps delivery checklist covering reviewable changes, CI gates, deployment strategies, and production observability.",
        "ai_prompt": "Which checks should run first in a continuous integration pipeline?",
        "ai_answer": "Run quick deterministic checks first, such as formatting, static analysis, and focused unit tests. Follow with integration and broader acceptance tests, and publish clear results for every stage.",
    },
    {
        "title": "Artificial Intelligence",
        "category": "Artificial Intelligence",
        "difficulty": "Intermediate",
        "description": "Study core AI and machine-learning ideas, evaluate model quality, and consider responsible ways to use data-driven systems.",
        "sections": (
            (
                "AI and machine-learning basics",
                "Understand learning tasks, data, and model evaluation.",
                (
                    ("AI problem types", "Distinguish classification, regression, clustering, and generative tasks by their inputs and desired outputs."),
                    ("Data preparation and splits", "Prepare representative data and separate training, validation, and test sets to reduce misleading evaluation."),
                ),
            ),
            (
                "Evaluation and responsible use",
                "Interpret model performance and identify risks.",
                (
                    ("Metrics and model errors", "Compare precision, recall, and accuracy, and examine how different error types affect users."),
                    ("Responsible AI practice", "Consider privacy, bias, explainability, and human oversight throughout the model lifecycle."),
                ),
            ),
        ),
        "quiz": (
            ("AI foundations check", "Review learning tasks, evaluation data, and responsible AI."),
            (
                ("Which task predicts a category such as a product type?", (("Classification", True), ("Regression", False), ("Sorting", False), ("Compression", False))),
                ("Why keep a separate test set?", (("To tune the model repeatedly", False), ("To estimate performance on data not used during training", True), ("To replace data validation", False), ("To increase the number of labels", False))),
                ("What can a large accuracy score hide on an imbalanced dataset?", (("Poor performance on a minority class", True), ("A missing file extension", False), ("A faster network connection", False), ("A lower database size", False))),
            ),
        ),
        "discussion": ("Evaluating an AI feature", "What user impact should be measured in addition to model accuracy before launching an AI-powered feature?"),
        "material": "An AI study guide covering learning tasks, data splits, evaluation metrics, privacy, and bias checks.",
        "ai_prompt": "Why can accuracy be misleading for an imbalanced dataset?",
        "ai_answer": "A model can predict the majority class most of the time and still miss nearly every minority example. Review per-class precision and recall, confusion matrices, and the costs of each error.",
    },
)

def _get_or_create(
    db: Session,
    model: type[ModelT],
    table_name: str,
    identity: dict[str, object],
    values: dict[str, object],
    inserted: Counter[str],
) -> tuple[ModelT, bool]:
    record = db.query(model).filter_by(**identity).first()
    if record is not None:
        return record, False

    record = model(**identity, **values)
    db.add(record)
    db.flush()
    inserted[table_name] += 1
    return record, True


def _database_engine() -> Engine:
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Existing EduVerse database was not found: {DATABASE_PATH}")

    seed_engine = create_engine(
        URL.create("sqlite", database=str(DATABASE_PATH)),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(seed_engine, "connect")
    def enable_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return seed_engine


def _table_counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            table_name: int(
                connection.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar_one()
            )
            for table_name in inspect(engine).get_table_names()
        }


def _foreign_key_violations(engine: Engine) -> list[tuple[object, ...]]:
    with engine.connect() as connection:
        return [tuple(row) for row in connection.execute(text("PRAGMA foreign_key_check"))]


def seed_database() -> None:
    demo_password = os.getenv("DEMO_PASSWORD", "EduVerseDemo2026!")
    password_is_valid, password_error = validate_password_strength(demo_password)
    if not password_is_valid:
        raise ValueError(f"DEMO_PASSWORD does not meet the application's password rules: {password_error}")

    engine = _database_engine()
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    inserted: Counter[str] = Counter()
    storage = get_storage_provider()
    now = datetime.now(timezone.utc)

    try:
        before_counts = _table_counts(engine)
        if not before_counts:
            raise RuntimeError("The existing database contains no tables; refusing to create or initialize a database.")
        initial_violations = _foreign_key_violations(engine)
        if initial_violations:
            raise RuntimeError(f"Existing database has foreign-key violations: {initial_violations}")

        with session_factory() as db:
            try:
                seeded_users: dict[str, User] = {}
                user_data = (
                    ("EduVerse Administrator", "admin@eduverse.io", "admin"),
                    *((name, email, "instructor") for name, email in INSTRUCTORS),
                    *((name, email, "student") for name, email in STUDENTS),
                )
                for full_name, email, role in user_data:
                    user = db.query(User).filter_by(email=email).first()
                    if user is None:
                        user = User(
                            full_name=full_name,
                            email=email,
                            password_hash=hash_password(demo_password),
                            role=role,
                            is_active=True,
                        )
                        db.add(user)
                        db.flush()
                        inserted["users"] += 1
                    elif user.role != role:
                        raise ValueError(
                            f"Existing account {email} has role {user.role!r}; expected {role!r}. "
                            "No account data was changed."
                        )
                    seeded_users[email] = user

                students = [seeded_users[email] for _name, email in STUDENTS]
                instructors = [seeded_users[email] for _name, email in INSTRUCTORS]
                course_records: list[Course] = []
                course_lessons: dict[int, list[Lesson]] = {}
                course_quiz_data: dict[int, tuple[Quiz, list[tuple[Question, AnswerOption, AnswerOption]]]] = {}

                for course_index, data in enumerate(COURSES):
                    instructor = instructors[course_index % len(instructors)]
                    course, _ = _get_or_create(
                        db,
                        Course,
                        "courses",
                        {"title": data["title"]},
                        {
                            "description": data["description"],
                            "category": data["category"],
                            "difficulty": data["difficulty"],
                            "is_published": True,
                            "instructor_id": instructor.id,
                        },
                        inserted,
                    )
                    course_records.append(course)

                    lessons: list[Lesson] = []
                    for section_index, (section_title, section_description, lesson_data) in enumerate(
                        data["sections"], start=1
                    ):
                        section, _ = _get_or_create(
                            db,
                            CourseSection,
                            "course_sections",
                            {"course_id": course.id, "title": section_title},
                            {"description": section_description, "order_index": section_index},
                            inserted,
                        )
                        for lesson_index, (lesson_title, lesson_content) in enumerate(lesson_data, start=1):
                            lesson, _ = _get_or_create(
                                db,
                                Lesson,
                                "lessons",
                                {"course_id": course.id, "title": lesson_title},
                                {
                                    "section_id": section.id,
                                    "content": lesson_content,
                                    "order_index": lesson_index,
                                },
                                inserted,
                            )
                            lessons.append(lesson)
                    course_lessons[course.id] = lessons

                    material_content = (
                        f"# {course.title} - study guide\n\n"
                        f"{data['material']}\n\n"
                        "Use this guide alongside the course lessons and practice exercises.\n"
                    ).encode("utf-8")
                    slug = re.sub(r"[^a-z0-9]+", "-", course.title.lower()).strip("-")
                    storage_key = f"eduverse-demo-{slug}-study-guide.md"
                    if storage.file_exists(storage_key):
                        stored_content = storage.get_file_bytes(storage_key)
                    else:
                        storage.save_file(storage_key, material_content)
                        stored_content = material_content
                    _get_or_create(
                        db,
                        LearningMaterial,
                        "learning_materials",
                        {"storage_key": storage_key},
                        {
                            "title": f"{course.title} study guide",
                            "description": data["material"],
                            "original_filename": f"{slug}-study-guide.md",
                            "mime_type": "text/markdown",
                            "file_size": len(stored_content),
                            "uploader_id": instructor.id,
                            "course_id": course.id,
                            "section_id": course.sections[0].id if course.sections else None,
                            "lesson_id": lessons[0].id if lessons else None,
                        },
                        inserted,
                    )

                    quiz_title, quiz_description = data["quiz"][0]
                    quiz, _ = _get_or_create(
                        db,
                        Quiz,
                        "quizzes",
                        {"course_id": course.id, "title": quiz_title},
                        {
                            "section_id": course.sections[0].id if course.sections else None,
                            "lesson_id": lessons[0].id if lessons else None,
                            "description": quiz_description,
                            "passing_score": 70,
                            "is_published": True,
                            "time_limit_minutes": 20,
                            "max_attempts": 3,
                        },
                        inserted,
                    )
                    question_options: list[tuple[Question, AnswerOption, AnswerOption]] = []
                    for question_index, (question_text, option_data) in enumerate(data["quiz"][1], start=1):
                        question, _ = _get_or_create(
                            db,
                            Question,
                            "questions",
                            {"quiz_id": quiz.id, "question_text": question_text},
                            {"order_index": question_index, "points": 1},
                            inserted,
                        )
                        correct_option: AnswerOption | None = None
                        incorrect_option: AnswerOption | None = None
                        for option_index, (option_text, is_correct) in enumerate(option_data, start=1):
                            option, _ = _get_or_create(
                                db,
                                AnswerOption,
                                "answer_options",
                                {"question_id": question.id, "option_text": option_text},
                                {"is_correct": is_correct, "order_index": option_index},
                                inserted,
                            )
                            if is_correct:
                                correct_option = option
                            elif incorrect_option is None:
                                incorrect_option = option
                        if correct_option is None or incorrect_option is None:
                            raise RuntimeError(f"Quiz question {question.id} needs correct and incorrect options.")
                        question_options.append((question, correct_option, incorrect_option))
                    course_quiz_data[course.id] = (quiz, question_options)

                    announcement_title = f"Welcome to {course.title}"
                    _get_or_create(
                        db,
                        CourseAnnouncement,
                        "course_announcements",
                        {"course_id": course.id, "title": announcement_title},
                        {
                            "instructor_id": instructor.id,
                            "content": (
                                f"Welcome! Start with the first section, introduce yourself in the discussion, "
                                f"and use the study guide to plan your practice for {course.title}."
                            ),
                            "is_published": True,
                        },
                        inserted,
                    )

                    discussion_title, discussion_content = data["discussion"]
                    thread_author = students[course_index % len(students)]
                    thread, _ = _get_or_create(
                        db,
                        CourseDiscussion,
                        "course_discussions",
                        {"course_id": course.id, "title": discussion_title},
                        {
                            "user_id": thread_author.id,
                            "content": discussion_content,
                            "is_pinned": course_index == 0,
                            "is_deleted": False,
                        },
                        inserted,
                    )
                    instructor_reply_text = (
                        f"Great question. Try the related lesson in {course.title}, then share one example "
                        "from your practice so classmates can compare approaches."
                    )
                    instructor_reply, _ = _get_or_create(
                        db,
                        DiscussionReply,
                        "discussion_replies",
                        {
                            "thread_id": thread.id,
                            "user_id": instructor.id,
                            "content": instructor_reply_text,
                        },
                        {"parent_reply_id": None, "is_deleted": False},
                        inserted,
                    )
                    student_reply_text = (
                        f"I tried this with the first exercise in {course.title}; writing down the steps "
                        "made the idea much clearer."
                    )
                    _get_or_create(
                        db,
                        DiscussionReply,
                        "discussion_replies",
                        {
                            "thread_id": thread.id,
                            "user_id": students[(course_index + 1) % len(students)].id,
                            "content": student_reply_text,
                        },
                        {"parent_reply_id": instructor_reply.id, "is_deleted": False},
                        inserted,
                    )

                    conversation_user = students[course_index % len(students)]
                    conversation_title = f"Study help: {course.title}"
                    conversation, _ = _get_or_create(
                        db,
                        AIConversation,
                        "ai_conversations",
                        {"user_id": conversation_user.id, "title": conversation_title},
                        {"course_id": course.id},
                        inserted,
                    )
                    messages = (
                        ("user", data["ai_prompt"]),
                        ("assistant", data["ai_answer"]),
                        ("user", "Thanks. I will apply that to the next course exercise."),
                    )
                    for role, content in messages:
                        _get_or_create(
                            db,
                            AIMessage,
                            "ai_messages",
                            {"conversation_id": conversation.id, "role": role, "content": content},
                            {},
                            inserted,
                        )

                for course_index, course in enumerate(course_records):
                    instructor = instructors[course_index % len(instructors)]
                    quiz, question_options = course_quiz_data[course.id]
                    assignment_title = f"{course.title}: applied project"
                    assignment, _ = _get_or_create(
                        db,
                        Assignment,
                        "assignments",
                        {"course_id": course.id, "title": assignment_title},
                        {
                            "section_id": course.sections[-1].id if course.sections else None,
                            "description": f"Apply the main ideas from {course.title} to a small, clearly documented project.",
                            "instructions": (
                                "Submit a short project or worked example. Include your approach, the decisions "
                                "you made, and one reflection on what you would improve next."
                            ),
                            "max_marks": 100,
                            "due_date": now + timedelta(days=21),
                            "is_published": True,
                            "is_closed": False,
                            "allow_resubmission": True,
                            "is_archived": False,
                        },
                        inserted,
                    )

                    for student_index, student in enumerate(students):
                        completion = float(((student_index * 17 + course_index * 13) % 6) * 20)
                        _get_or_create(
                            db,
                            CourseEnrollment,
                            "course_enrollments",
                            {"student_id": student.id, "course_id": course.id},
                            {
                                "enrolled_at": now - timedelta(days=student_index + course_index + 1),
                                "completion_percentage": completion,
                            },
                            inserted,
                        )

                        grade = float(72 + ((student_index * 7 + course_index * 3) % 29))
                        submission_text = (
                            f"My {course.title} project applies the course concepts to a small practical example. "
                            "I documented the approach, tested the main behavior, and noted one improvement."
                        )
                        _get_or_create(
                            db,
                            AssignmentSubmission,
                            "assignment_submissions",
                            {"assignment_id": assignment.id, "student_id": student.id},
                            {
                                "submission_text": submission_text,
                                "attachments_json": None,
                                "status": "graded",
                                "is_late": False,
                                "submitted_at": now - timedelta(days=student_index + 1),
                                "grade": grade,
                                "feedback": "Clear explanation and a thoughtful practical example. Continue refining the tests and edge cases.",
                                "graded_by_id": instructor.id,
                                "graded_at": now,
                            },
                            inserted,
                        )

                        correct_count = 3 if (student_index + course_index) % 3 == 0 else 2
                        score = correct_count / len(question_options) * 100
                        attempt, _ = _get_or_create(
                            db,
                            QuizAttempt,
                            "quiz_attempts",
                            {
                                "quiz_id": quiz.id,
                                "student_id": student.id,
                                "attempt_number": 1,
                            },
                            {
                                "score": score,
                                "total_points": len(question_options),
                                "passed": score >= quiz.passing_score,
                                "is_completed": True,
                                "started_at": now - timedelta(days=student_index + 1, minutes=20),
                                "submitted_at": now - timedelta(days=student_index + 1),
                            },
                            inserted,
                        )
                        for question_index, (question, correct_option, incorrect_option) in enumerate(
                            question_options
                        ):
                            is_correct = question_index < correct_count
                            selected_option = correct_option if is_correct else incorrect_option
                            _get_or_create(
                                db,
                                QuizAttemptAnswer,
                                "quiz_attempt_answers",
                                {"attempt_id": attempt.id, "question_id": question.id},
                                {
                                    "selected_option_id": selected_option.id,
                                    "is_correct": is_correct,
                                    "awarded_points": question.points if is_correct else 0,
                                },
                                inserted,
                            )

                db.commit()
            except Exception:
                db.rollback()
                raise

        after_counts = _table_counts(engine)
        if any(after_counts.get(table, 0) < count for table, count in before_counts.items()):
            raise RuntimeError("A table has fewer records after seeding; existing data may not have been preserved.")
        violations = _foreign_key_violations(engine)
        if violations:
            raise RuntimeError(f"Foreign-key integrity check failed after seeding: {violations}")

        print(f"Seeded existing database: {DATABASE_PATH}")
        print("\nRecords inserted by this run:")
        for table_name in sorted(after_counts):
            print(f"  {table_name}: {inserted[table_name]}")
        print("\nTotal records in every database table:")
        for table_name, count in sorted(after_counts.items()):
            original_count = before_counts.get(table_name, 0)
            print(f"  {table_name}: {count} (before: {original_count})")
        print("\nForeign-key integrity: OK")
        print("Existing records preserved: the seeder issues inserts only, and all prior table counts remain present.")
        print("Demo user password: DEMO_PASSWORD or the default EduVerseDemo2026!")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        seed_database()
    except Exception as error:
        print(f"Seed failed: {error}", file=sys.stderr)
        sys.exit(1)
