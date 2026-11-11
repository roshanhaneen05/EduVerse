import smtplib
import ssl
from email.message import EmailMessage
from email.utils import format_datetime

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.config import Settings
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.user import User


class EmailNotConfiguredError(RuntimeError):
    pass


class InvalidEmailAddressError(ValueError):
    pass


_email_validator = TypeAdapter(EmailStr)


def _validate_email_address(address: str, field_name: str) -> str:
    try:
        return str(_email_validator.validate_python(address))
    except ValidationError as exc:
        raise InvalidEmailAddressError(f"{field_name} is not a valid email address.") from exc


def _validate_smtp_configuration(settings: Settings) -> str:
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        raise EmailNotConfiguredError(
            "EMAIL_HOST_USER and EMAIL_HOST_PASSWORD must be configured."
        )
    if not settings.DEFAULT_FROM_EMAIL:
        raise EmailNotConfiguredError("DEFAULT_FROM_EMAIL must be configured.")
    if not settings.EMAIL_USE_TLS:
        raise EmailNotConfiguredError("Gmail SMTP requires EMAIL_USE_TLS=true.")
    if not 1 <= settings.EMAIL_PORT <= 65535:
        raise EmailNotConfiguredError("EMAIL_PORT must be between 1 and 65535.")
    return _validate_email_address(settings.DEFAULT_FROM_EMAIL, "DEFAULT_FROM_EMAIL")


def _send_smtp_message(message: EmailMessage, settings: Settings) -> None:
    with smtplib.SMTP(
        settings.EMAIL_HOST,
        settings.EMAIL_PORT,
        timeout=settings.EMAIL_TIMEOUT_SECONDS,
    ) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        refused_recipients = smtp.send_message(message)
        if refused_recipients:
            raise smtplib.SMTPRecipientsRefused(refused_recipients)


def build_enrollment_email(
    enrollment: CourseEnrollment,
    student: User,
    course: Course,
    instructor: User,
    settings: Settings,
) -> EmailMessage:
    sender = _validate_smtp_configuration(settings)
    recipient = _validate_email_address(instructor.email, "Instructor email")

    message = EmailMessage()
    message["Subject"] = f"New Student Enrollment - {course.title}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"""Hello {instructor.full_name},

Good news! A new student has enrolled in your course on EduVerse.

Student Details:

- Student Name: {student.full_name}
- Student Email: {student.email}
- Course Name: {course.title}
- Enrollment Date: {format_datetime(enrollment.enrolled_at)}

A new student has selected your course and is ready to begin learning.

Please log in to your EduVerse instructor dashboard to view the enrollment details.

Best Regards,
EduVerse Team
"""
    )
    return message


def send_enrollment_email(
    enrollment: CourseEnrollment,
    student: User,
    course: Course,
    instructor: User,
    settings: Settings,
) -> None:
    message = build_enrollment_email(enrollment, student, course, instructor, settings)
    _send_smtp_message(message, settings)


def send_test_email(recipient_email: str, settings: Settings) -> None:
    sender = _validate_smtp_configuration(settings)
    recipient = _validate_email_address(recipient_email, "Test recipient email")
    message = EmailMessage()
    message["Subject"] = "EduVerse SMTP configuration test"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "This test message confirms that the EduVerse backend successfully "
        "authenticated with its configured SMTP server."
    )

    _send_smtp_message(message, settings)
