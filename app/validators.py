"""Server-side validation. Never trust data sent by the browser."""
from datetime import date

from .models import PRIORITIES, STATUSES

TITLE_MAX = 120
DESCRIPTION_MAX = 1000


def validate_task(data: dict, partial: bool = False):
    """Return (clean_data, errors). `errors` maps field name -> message.

    partial=False: used for create/update, so a title is required.
    partial=True: only validate the fields that are present.
    """
    clean, errors = {}, {}

    if not partial or "title" in data:
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            errors["title"] = "Enter a title for the task."
        elif len(title.strip()) > TITLE_MAX:
            errors["title"] = f"Title must be {TITLE_MAX} characters or fewer."
        else:
            clean["title"] = title.strip()

    if "description" in data or not partial:
        description = data.get("description") or ""
        if not isinstance(description, str):
            errors["description"] = "Description must be text."
        elif len(description.strip()) > DESCRIPTION_MAX:
            errors["description"] = f"Description must be {DESCRIPTION_MAX} characters or fewer."
        else:
            clean["description"] = description.strip()

    if "status" in data or not partial:
        status = data.get("status", "todo")
        if status not in STATUSES:
            errors["status"] = "Choose To Do, In Progress or Completed."
        else:
            clean["status"] = status

    if "priority" in data or not partial:
        priority = data.get("priority", "medium")
        if priority not in PRIORITIES:
            errors["priority"] = "Choose Low, Medium or High."
        else:
            clean["priority"] = priority

    if "due_date" in data or not partial:
        raw = data.get("due_date")
        if raw in (None, ""):
            clean["due_date"] = None
        elif not isinstance(raw, str):
            errors["due_date"] = "Enter the date as YYYY-MM-DD."
        else:
            try:
                clean["due_date"] = date.fromisoformat(raw)
            except ValueError:
                errors["due_date"] = "Enter a valid date (YYYY-MM-DD)."

    return clean, errors
