from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, text

from app.database import Base


class EmailDelivery(Base):
    __tablename__ = "email_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    enrollment_id = Column(
        Integer,
        ForeignKey("course_enrollments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(40), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    status = Column(String(20), default="pending", server_default=text("'pending'"), nullable=False)
    attempts = Column(Integer, default=0, server_default=text("0"), nullable=False)
    last_error = Column(String(100), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "enrollment_id",
            "event_type",
            name="uq_email_delivery_enrollment_event",
        ),
    )
