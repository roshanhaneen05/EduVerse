import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from html import escape

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import update
from sqlalchemy.orm import Session, joinedload

from app.config import Settings
from app.models.course import Course
from app.models.email_delivery import EmailDelivery
from app.models.enrollment import CourseEnrollment
from app.models.user import User

logger = logging.getLogger(__name__)

ENROLLMENT_REQUEST = "enrollment_request"
ENROLLMENT_APPROVED = "enrollment_approved"
ENROLLMENT_REJECTED = "enrollment_rejected"


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
    _validate_email_address(settings.EMAIL_HOST_USER, "EMAIL_HOST_USER")
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
    recipient_email: str | None = None,
) -> EmailMessage:
    return _build_branded_email(
        recipient=recipient_email or instructor.email,
        recipient_field="Instructor email",
        subject="New Course Enrollment Request - EduVerse",
        greeting=f"Hello {instructor.full_name},",
        introduction="A student has requested to enroll in your course.",
        details=[
            ("Student name", student.full_name),
            ("Student email", student.email),
            ("Course", course.title),
            ("Enrollment date", format_datetime(enrollment.enrolled_at)),
            ("Request status", "Pending"),
        ],
        closing="Please sign in to your instructor dashboard to review this request.",
        settings=settings,
    )


def build_approval_email(
    enrollment: CourseEnrollment,
    student: User,
    course: Course,
    instructor: User,
    settings: Settings,
    recipient_email: str | None = None,
) -> EmailMessage:
    return _build_branded_email(
        recipient=recipient_email or student.email,
        recipient_field="Student email",
        subject="Your Enrollment Has Been Approved - EduVerse",
        greeting=f"Hello {student.full_name},",
        introduction=f"Your enrollment in {course.title} has been approved.",
        details=[("Course", course.title), ("Instructor", instructor.full_name)],
        closing="You can now sign in to EduVerse and access your course lessons and materials.",
        settings=settings,
    )


def build_rejection_email(
    enrollment: CourseEnrollment,
    student: User,
    course: Course,
    instructor: User,
    settings: Settings,
    recipient_email: str | None = None,
) -> EmailMessage:
    return _build_branded_email(
        recipient=recipient_email or student.email,
        recipient_field="Student email",
        subject="Your Course Enrollment Request - EduVerse",
        greeting=f"Hello {student.full_name},",
        introduction=f"Your request to enroll in {course.title} was not approved.",
        details=[("Course", course.title), ("Instructor", instructor.full_name), ("Status", "Rejected")],
        closing="Please contact the instructor if you have questions about this decision.",
        settings=settings,
    )


def send_enrollment_email(
    enrollment: CourseEnrollment,
    student: User,
    course: Course,
    instructor: User,
    settings: Settings,
) -> None:
    _send_smtp_message(
        build_enrollment_email(enrollment, student, course, instructor, settings),
        settings,
    )


def build_instructor_password_email(
    instructor: User,
    profile,
    setup_link: str,
    settings: Settings,
    purpose: str,
) -> EmailMessage:
    is_reset = purpose == "reset"
    return _build_branded_email(
        recipient=instructor.email,
        recipient_field="Instructor email",
        subject=(
            "Reset Your EduVerse Instructor Password"
            if is_reset
            else "Welcome to the EduVerse Faculty - Set Up Your Account"
        ),
        greeting=f"Hello {instructor.full_name},",
        introduction=(
            "An administrator requested a password reset for your EduVerse instructor account. "
            "Use the secure link below to choose a new password."
            if is_reset
            else "An administrator has registered you as an EduVerse instructor. "
            "Use the secure link below to set your password."
        ),
        details=[
            ("Instructor ID", profile.instructor_id),
            ("Login email", instructor.email),
            ("Login page", f"{settings.FRONTEND_BASE_URL.rstrip('/')}/instructor/login"),
        ],
        closing="This one-time password link expires in 24 hours.",
        settings=settings,
        action_url=setup_link,
        action_label="Set your password",
    )


def build_instructor_status_email(
    instructor: User,
    profile,
    settings: Settings,
) -> EmailMessage:
    active = instructor.is_active
    return _build_branded_email(
        recipient=instructor.email,
        recipient_field="Instructor email",
        subject=f"EduVerse Instructor Account {'Activated' if active else 'Deactivated'}",
        greeting=f"Hello {instructor.full_name},",
        introduction=(
            "Your EduVerse instructor account has been activated."
            if active
            else "Your EduVerse instructor account has been deactivated. You can no longer sign in."
        ),
        details=[
            ("Instructor ID", profile.instructor_id),
            ("Account status", "Active" if active else "Deactivated"),
        ],
        closing="Contact your institution administrator if you have questions.",
        settings=settings,
    )


def send_instructor_password_email(
    instructor: User,
    profile,
    setup_link: str,
    settings: Settings,
    purpose: str,
) -> None:
    _send_smtp_message(
        build_instructor_password_email(instructor, profile, setup_link, settings, purpose),
        settings,
    )


def send_instructor_status_email(instructor: User, profile, settings: Settings) -> None:
    _send_smtp_message(build_instructor_status_email(instructor, profile, settings), settings)


def _build_branded_email(
    recipient: str,
    recipient_field: str,
    subject: str,
    greeting: str,
    introduction: str,
    details: list[tuple[str, str]],
    closing: str,
    settings: Settings,
    action_url: str | None = None,
    action_label: str | None = None,
) -> EmailMessage:
    sender = _validate_smtp_configuration(settings)
    recipient = _validate_email_address(recipient, recipient_field)
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    plain_details = "\n".join(f"- {label}: {value}" for label, value in details)
    message.set_content(
        f"""{greeting}

{introduction}

{plain_details}

{closing}

{f'{action_label}: {action_url}' if action_url and action_label else ''}

Warm regards,
EduVerse Team
"""
    )
    action_button = ""
    if action_url and action_label:
        safe_url = escape(action_url, quote=True)
        action_button = (
            f'<p style="margin:24px 0 0;text-align:center;">'
            f'<a href="{safe_url}" style="display:inline-block;padding:12px 20px;'
            f'background:#e83e8c;color:#ffffff;text-decoration:none;border-radius:8px;'
            f'font-weight:bold;">{escape(action_label)}</a></p>'
        )
    detail_rows = "".join(
        f"""<tr>
          <td class="detail-label">{escape(label)}</td>
          <td class="detail-value">{escape(value)}</td>
        </tr>"""
        for label, value in details
    )
    message.add_alternative(
        f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(subject)}</title>
  <style>
    @media only screen and (max-width: 600px) {{
      .email-shell {{ padding: 18px 10px !important; }}
      .detail-label, .detail-value {{ display: block !important; width: auto !important; }}
      .detail-label {{ padding-bottom: 4px !important; }}
      .detail-value {{ padding-top: 0 !important; }}
    }}
  </style>
</head>
<body style="margin:0;background:#fff5f8;color:#352b30;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#fff5f8;">
    <tr>
      <td align="center" class="email-shell" style="padding:40px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
          style="max-width:600px;background:#ffffff;border:1px solid #f4dce6;border-radius:16px;overflow:hidden;">
          <tr>
            <td style="padding:25px 32px;background:#e83e8c;color:#ffffff;">
              <div style="font-size:13px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;">EduVerse</div>
              <div style="margin-top:8px;font-size:24px;font-weight:bold;">{escape(subject)}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              <p style="margin:0 0 14px;font-size:17px;">{escape(greeting)}</p>
              <p style="margin:0 0 24px;color:#62545b;line-height:1.6;">
                {escape(introduction)}
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                style="border-collapse:collapse;border:1px solid #f4dce6;border-radius:10px;">
                <tr>
                  <td colspan="2" style="padding:14px 16px;background:#fff0f6;color:#a91f61;font-weight:bold;">
                    EduVerse details
                  </td>
                </tr>
                {detail_rows}
              </table>
              <p style="margin:24px 0 0;color:#62545b;line-height:1.6;">
                {escape(closing)}
              </p>
              {action_button}
              <p style="margin:24px 0 0;color:#62545b;line-height:1.6;">Warm regards,<br><strong style="color:#a91f61;">EduVerse Team</strong></p>
            </td>
          </tr>
        </table>
        <p style="margin:18px 0 0;color:#8c7c84;font-size:12px;">Learning together, with EduVerse.</p>
      </td>
    </tr>
  </table>
</body>
</html>
""",
        subtype="html",
    )
    return message


def send_email_delivery(
    db: Session,
    delivery: EmailDelivery,
    settings: Settings,
) -> str:
    if delivery.status == "sent":
        return "sent"

    enrollment = (
        db.query(CourseEnrollment)
        .options(
            joinedload(CourseEnrollment.student),
            joinedload(CourseEnrollment.course).joinedload(Course.instructor),
        )
        .filter(CourseEnrollment.id == delivery.enrollment_id)
        .first()
    )
    if not enrollment or not enrollment.student or not enrollment.course:
        delivery.status = "failed"
        delivery.last_error = "EnrollmentDataUnavailable"
        db.commit()
        return "failed"

    instructor_id = (
        enrollment.course.instructor_id
        if delivery.event_type == ENROLLMENT_REQUEST
        else enrollment.reviewed_by_instructor_id or enrollment.course.instructor_id
    )
    instructor = db.query(User).filter(User.id == instructor_id).first()
    if not instructor:
        delivery.status = "failed"
        delivery.last_error = "InstructorUnavailable"
        db.commit()
        return "failed"

    claimed = db.execute(
        update(EmailDelivery)
        .where(
            EmailDelivery.id == delivery.id,
            EmailDelivery.status.in_(("pending", "failed")),
        )
        .values(
            status="sending",
            attempts=EmailDelivery.attempts + 1,
            last_error=None,
            updated_at=datetime.now(timezone.utc),
        )
    ).rowcount
    db.commit()
    if not claimed:
        db.refresh(delivery)
        return "sent" if delivery.status == "sent" else "failed"
    db.refresh(delivery)

    try:
        if delivery.event_type == ENROLLMENT_REQUEST:
            message = build_enrollment_email(
                enrollment,
                enrollment.student,
                enrollment.course,
                instructor,
                settings,
                delivery.recipient_email,
            )
        elif delivery.event_type == ENROLLMENT_APPROVED:
            if enrollment.status != "approved":
                raise ValueError("Approval notification no longer matches enrollment status.")
            message = build_approval_email(
                enrollment,
                enrollment.student,
                enrollment.course,
                instructor,
                settings,
                delivery.recipient_email,
            )
        elif delivery.event_type == ENROLLMENT_REJECTED:
            if enrollment.status != "rejected":
                raise ValueError("Rejection notification no longer matches enrollment status.")
            message = build_rejection_email(
                enrollment,
                enrollment.student,
                enrollment.course,
                instructor,
                settings,
                delivery.recipient_email,
            )
        else:
            raise ValueError("Unknown enrollment email event.")

        _send_smtp_message(message, settings)
    except EmailNotConfiguredError as exc:
        delivery.status = "failed"
        delivery.last_error = type(exc).__name__
        db.commit()
        logger.warning(
            "Email delivery %s (%s) is not configured; retry after SMTP configuration.",
            delivery.id,
            delivery.event_type,
        )
        return "not_configured"
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        delivery.status = "failed"
        delivery.last_error = type(exc).__name__
        db.commit()
        logger.error(
            "Email delivery %s (%s) failed with %s.",
            delivery.id,
            delivery.event_type,
            type(exc).__name__,
        )
        return "failed"

    delivery.status = "sent"
    delivery.sent_at = datetime.now(timezone.utc)
    db.commit()
    return "sent"


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
