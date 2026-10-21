"""Pytest setup. Tests use their own database and never touch development data."""
import pytest

from app import create_app, db
from config import Config, TestConfig


@pytest.fixture
def app():
    # Safety net: refuse to run if the test database is the development database.
    if TestConfig.SQLALCHEMY_DATABASE_URI == Config.SQLALCHEMY_DATABASE_URI:
        pytest.exit("TEST_DATABASE_URL must not point at your development database.")

    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_task(client):
    """Create a task through the API and return its JSON."""
    def _make(**overrides):
        payload = {"title": "Sample task", "description": "", "status": "todo", "priority": "medium", "due_date": None}
        payload.update(overrides)
        response = client.post("/api/tasks", json=payload)
        assert response.status_code == 201, response.get_json()
        return response.get_json()
    return _make
