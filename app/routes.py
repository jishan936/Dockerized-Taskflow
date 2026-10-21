"""Page routes and the JSON API used by static/js/app.js."""
from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, render_template, request
from sqlalchemy import func, or_

from . import db
from .models import PRIORITIES, PRIORITY_LABELS, STATUS_LABELS, STATUSES, Task
from .validators import validate_task

bp = Blueprint("main", __name__)

# Sidebar views: each one is the same page with a preset filter.
VIEWS = {
    "dashboard": {"title": "Dashboard", "status": "", "priority": ""},
    "all": {"title": "All tasks", "status": "", "priority": ""},
    "todo": {"title": "To do", "status": "todo", "priority": ""},
    "in_progress": {"title": "In progress", "status": "in_progress", "priority": ""},
    "completed": {"title": "Completed", "status": "completed", "priority": ""},
    "high": {"title": "High priority", "status": "", "priority": "high"},
}

DUE_FILTERS = ("overdue", "today", "week", "none")


def _sort_clauses(sort: str):
    # Tasks without a due date always go last when sorting by due date.
    no_due_last = Task.due_date.is_(None)
    return {
        "created_desc": [Task.created_at.desc(), Task.id.desc()],
        "created_asc": [Task.created_at.asc(), Task.id.asc()],
        "due_asc": [no_due_last, Task.due_date.asc(), Task.id.desc()],
        "due_desc": [no_due_last, Task.due_date.desc(), Task.id.desc()],
    }.get(sort)


# ---------- Pages ----------

@bp.get("/")
def dashboard():
    view = request.args.get("view", "dashboard")
    if view not in VIEWS:
        view = "dashboard"
    return render_template(
        "dashboard.html",
        active_view=view,
        view=VIEWS[view],
        user_name=current_app.config["APP_USER_NAME"],
        statuses=[(s, STATUS_LABELS[s]) for s in STATUSES],
        priorities=[(p, PRIORITY_LABELS[p]) for p in PRIORITIES],
    )


@bp.get("/about")
def about():
    return render_template("about.html", active_view="about")


@bp.get("/health")
def health():
    """Used by the Docker HEALTHCHECK. Also confirms the database answers."""
    db.session.execute(db.text("SELECT 1"))
    return jsonify({"status": "ok"})


# ---------- JSON API ----------

def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _bad_request(message):
    return jsonify({"error": message}), 400


@bp.get("/api/tasks")
def list_tasks():
    args = request.args
    query = Task.query

    q = args.get("q", "").strip()
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        query = query.filter(or_(Task.title.ilike(like, escape="\\"), Task.description.ilike(like, escape="\\")))

    status = args.get("status", "")
    if status:
        if status not in STATUSES:
            return _bad_request("Unknown status filter.")
        query = query.filter(Task.status == status)

    priority = args.get("priority", "")
    if priority:
        if priority not in PRIORITIES:
            return _bad_request("Unknown priority filter.")
        query = query.filter(Task.priority == priority)

    due = args.get("due", "")
    if due:
        if due not in DUE_FILTERS:
            return _bad_request("Unknown due-date filter.")
        today = date.today()
        if due == "overdue":
            query = query.filter(Task.due_date < today, Task.status != "completed")
        elif due == "today":
            query = query.filter(Task.due_date == today)
        elif due == "week":
            query = query.filter(Task.due_date >= today, Task.due_date <= today + timedelta(days=7))
        else:
            query = query.filter(Task.due_date.is_(None))

    clauses = _sort_clauses(args.get("sort", "created_desc"))
    if clauses is None:
        return _bad_request("Unknown sort option.")
    tasks = query.order_by(*clauses).all()
    return jsonify({"tasks": [t.to_dict() for t in tasks], "count": len(tasks)})


@bp.post("/api/tasks")
def create_task():
    data = _json_body()
    if data is None:
        return _bad_request("Send the task as JSON.")
    clean, errors = validate_task(data)
    if errors:
        return jsonify({"error": "Please fix the highlighted fields.", "errors": errors}), 422
    task = Task(**clean)
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@bp.get("/api/tasks/<int:task_id>")
def get_task(task_id):
    return jsonify(db.get_or_404(Task, task_id).to_dict())


@bp.put("/api/tasks/<int:task_id>")
def update_task(task_id):
    task = db.get_or_404(Task, task_id)
    data = _json_body()
    if data is None:
        return _bad_request("Send the task as JSON.")
    clean, errors = validate_task(data)
    if errors:
        return jsonify({"error": "Please fix the highlighted fields.", "errors": errors}), 422
    for field, value in clean.items():
        setattr(task, field, value)
    db.session.commit()
    return jsonify(task.to_dict())


@bp.patch("/api/tasks/<int:task_id>/status")
def change_status(task_id):
    task = db.get_or_404(Task, task_id)
    data = _json_body()
    if data is None:
        return _bad_request("Send the status as JSON.")
    clean, errors = validate_task({"status": data.get("status")}, partial=True)
    if errors:
        return jsonify({"error": errors["status"], "errors": errors}), 422
    task.status = clean["status"]
    db.session.commit()
    return jsonify(task.to_dict())


@bp.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    task = db.get_or_404(Task, task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted.", "id": task_id})


@bp.get("/api/stats")
def stats():
    """All numbers come from the database; nothing is hardcoded."""
    rows = db.session.query(Task.status, func.count(Task.id)).group_by(Task.status).all()
    counts = {status: 0 for status in STATUSES}
    counts.update(dict(rows))
    total = sum(counts.values())
    today = date.today()
    overdue = Task.query.filter(Task.due_date < today, Task.status != "completed").count()
    high_open = Task.query.filter(Task.priority == "high", Task.status != "completed").count()
    return jsonify({
        "total": total,
        "todo": counts["todo"],
        "in_progress": counts["in_progress"],
        "completed": counts["completed"],
        "overdue": overdue,
        "high_priority": high_open,
        "completion_percent": round(counts["completed"] * 100 / total) if total else 0,
    })
