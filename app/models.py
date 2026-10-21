"""Database models."""
from datetime import date, datetime, timezone

from . import db

STATUSES = ("todo", "in_progress", "completed")
PRIORITIES = ("low", "medium", "high")
STATUS_LABELS = {"todo": "To Do", "in_progress": "In Progress", "completed": "Completed"}
PRIORITY_LABELS = {"low": "Low", "medium": "Medium", "high": "High"}


def utcnow():
    return datetime.now(timezone.utc)


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="todo", index=True)
    priority = db.Column(db.String(10), nullable=False, default="medium", index=True)
    due_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    @property
    def is_overdue(self) -> bool:
        """A task is overdue when its due date has passed and it is not completed."""
        return self.due_date is not None and self.due_date < date.today() and self.status != "completed"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "status_label": STATUS_LABELS[self.status],
            "priority": self.priority,
            "priority_label": PRIORITY_LABELS[self.priority],
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "is_overdue": self.is_overdue,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
