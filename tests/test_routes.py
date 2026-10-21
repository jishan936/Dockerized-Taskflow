from datetime import date, timedelta

TODAY = date.today()
YESTERDAY = (TODAY - timedelta(days=1)).isoformat()
TOMORROW = (TODAY + timedelta(days=1)).isoformat()


def titles(client, query=""):
    return [t["title"] for t in client.get(f"/api/tasks{query}").get_json()["tasks"]]


# ---------- Pages ----------

def test_dashboard_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Welcome back, Tester" in response.data
    assert b"Add New Task" in response.data


def test_dashboard_views_and_unknown_view(client):
    assert client.get("/?view=high").status_code == 200
    assert client.get("/?view=nonsense").status_code == 200  # falls back to the dashboard


def test_about_and_health(client):
    assert client.get("/about").status_code == 200
    assert client.get("/health").get_json() == {"status": "ok"}


def test_unknown_page_and_api_404(client):
    assert client.get("/nope").status_code == 404
    response = client.get("/api/tasks/999")
    assert response.status_code == 404
    assert "error" in response.get_json()


# ---------- Create ----------

def test_create_task(client):
    response = client.post("/api/tasks", json={
        "title": "  Learn Docker  ", "description": "Compose basics",
        "status": "in_progress", "priority": "high", "due_date": TOMORROW,
    })
    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Learn Docker"  # whitespace trimmed
    assert task["status"] == "in_progress" and task["priority"] == "high"
    assert task["due_date"] == TOMORROW
    assert task["created_at"] and task["updated_at"]
    assert client.get(f"/api/tasks/{task['id']}").status_code == 200  # really saved


def test_create_uses_defaults(client):
    task = client.post("/api/tasks", json={"title": "Only a title"}).get_json()
    assert task["status"] == "todo" and task["priority"] == "medium" and task["due_date"] is None


# ---------- Validation ----------

def test_missing_title_rejected(client):
    response = client.post("/api/tasks", json={"description": "no title"})
    assert response.status_code == 422
    assert "title" in response.get_json()["errors"]
    assert titles(client) == []


def test_blank_title_rejected(client):
    assert client.post("/api/tasks", json={"title": "   "}).status_code == 422


def test_invalid_fields_rejected(client):
    response = client.post("/api/tasks", json={
        "title": "x" * 121, "description": "d" * 1001,
        "status": "done", "priority": "urgent", "due_date": "31/12/2026",
    })
    assert response.status_code == 422
    assert set(response.get_json()["errors"]) == {"title", "description", "status", "priority", "due_date"}


def test_non_text_title_rejected(client):
    assert client.post("/api/tasks", json={"title": 123}).status_code == 422


def test_non_json_body_rejected(client):
    assert client.post("/api/tasks", data="title=hello").status_code == 400
    assert client.post("/api/tasks", json=["not", "an", "object"]).status_code == 400


# ---------- Edit ----------

def test_edit_task(client, make_task):
    task = make_task(title="Old title")
    response = client.put(f"/api/tasks/{task['id']}", json={
        "title": "New title", "description": "Updated", "status": "completed",
        "priority": "low", "due_date": TOMORROW,
    })
    assert response.status_code == 200
    updated = response.get_json()
    assert updated["title"] == "New title" and updated["status"] == "completed"
    assert updated["priority"] == "low" and updated["due_date"] == TOMORROW
    assert titles(client) == ["New title"]


def test_edit_validation_and_404(client, make_task):
    task = make_task()
    assert client.put(f"/api/tasks/{task['id']}", json={"title": ""}).status_code == 422
    assert client.get(f"/api/tasks/{task['id']}").get_json()["title"] == "Sample task"  # unchanged
    assert client.put("/api/tasks/999", json={"title": "x"}).status_code == 404


# ---------- Delete ----------

def test_delete_task(client, make_task):
    task = make_task(title="Delete me")
    keep = make_task(title="Keep me")
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 200
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404
    assert titles(client) == [keep["title"]]


def test_delete_missing_task(client):
    assert client.delete("/api/tasks/12345").status_code == 404


# ---------- Status ----------

def test_change_status(client, make_task):
    task = make_task()
    for status in ("in_progress", "completed", "todo"):
        response = client.patch(f"/api/tasks/{task['id']}/status", json={"status": status})
        assert response.status_code == 200
        assert response.get_json()["status"] == status


def test_invalid_status_change(client, make_task):
    task = make_task()
    assert client.patch(f"/api/tasks/{task['id']}/status", json={"status": "later"}).status_code == 422
    assert client.patch(f"/api/tasks/{task['id']}/status", json={}).status_code == 422
    assert client.patch("/api/tasks/999/status", json={"status": "todo"}).status_code == 404


# ---------- Search, filter, sort ----------

def test_search_title_and_description(client, make_task):
    make_task(title="Write report", description="for the lab")
    make_task(title="Buy milk", description="remember the DOCKER book")
    assert titles(client, "?q=report") == ["Write report"]
    assert titles(client, "?q=docker") == ["Buy milk"]  # case-insensitive, matches description
    assert titles(client, "?q=zzz") == []


def test_search_treats_percent_literally(client, make_task):
    make_task(title="100% done")
    make_task(title="Other")
    assert titles(client, "?q=%25") == ["100% done"]


def test_filter_status_and_priority(client, make_task):
    make_task(title="A", status="todo", priority="high")
    make_task(title="B", status="completed", priority="high")
    make_task(title="C", status="todo", priority="low")
    assert sorted(titles(client, "?status=todo")) == ["A", "C"]
    assert sorted(titles(client, "?priority=high")) == ["A", "B"]
    assert titles(client, "?status=todo&priority=high") == ["A"]


def test_invalid_filters_rejected(client):
    for query in ("?status=x", "?priority=x", "?due=x", "?sort=x"):
        assert client.get(f"/api/tasks{query}").status_code == 400


def test_due_filters_and_overdue_flag(client, make_task):
    make_task(title="late", due_date=YESTERDAY)
    make_task(title="late but done", due_date=YESTERDAY, status="completed")
    make_task(title="soon", due_date=TOMORROW)
    make_task(title="whenever")
    assert titles(client, "?due=overdue") == ["late"]
    assert titles(client, "?due=none") == ["whenever"]
    assert titles(client, "?due=week") == ["soon"]
    tasks = {t["title"]: t for t in client.get("/api/tasks").get_json()["tasks"]}
    assert tasks["late"]["is_overdue"] is True
    assert tasks["late but done"]["is_overdue"] is False
    assert tasks["soon"]["is_overdue"] is False


def test_sorting(client, make_task):
    make_task(title="first", due_date=TOMORROW)
    make_task(title="second", due_date=YESTERDAY)
    make_task(title="third")  # no due date
    assert titles(client, "?sort=created_asc") == ["first", "second", "third"]
    assert titles(client, "?sort=created_desc") == ["third", "second", "first"]
    assert titles(client, "?sort=due_asc") == ["second", "first", "third"]  # no date goes last
    assert titles(client, "?sort=due_desc") == ["first", "second", "third"]


# ---------- Statistics ----------

def test_stats_empty(client):
    stats = client.get("/api/stats").get_json()
    assert stats == {"total": 0, "todo": 0, "in_progress": 0, "completed": 0,
                     "overdue": 0, "high_priority": 0, "completion_percent": 0}


def test_stats_with_data(client, make_task):
    make_task(status="todo", priority="high", due_date=YESTERDAY)
    make_task(status="todo")
    make_task(status="in_progress", priority="high")
    make_task(status="completed", priority="high", due_date=YESTERDAY)
    stats = client.get("/api/stats").get_json()
    assert stats["total"] == 4
    assert (stats["todo"], stats["in_progress"], stats["completed"]) == (2, 1, 1)
    assert stats["overdue"] == 1          # the completed late task does not count
    assert stats["high_priority"] == 2    # open high-priority tasks only
    assert stats["completion_percent"] == 25


def test_stats_update_after_changes(client, make_task):
    task = make_task()
    client.patch(f"/api/tasks/{task['id']}/status", json={"status": "completed"})
    assert client.get("/api/stats").get_json()["completion_percent"] == 100
    client.delete(f"/api/tasks/{task['id']}")
    assert client.get("/api/stats").get_json()["total"] == 0
