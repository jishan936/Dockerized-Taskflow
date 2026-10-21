"""Application factory: builds and configures the Flask app."""
import time

import click
from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError

from config import Config

db = SQLAlchemy()


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY is not set. Copy .env.example to .env and set a value."
        )

    db.init_app(app)

    from . import models  # noqa: F401  (registers the Task table with SQLAlchemy)
    from .routes import bp

    app.register_blueprint(bp)
    register_error_handlers(app)
    register_cli(app)
    return app


def register_error_handlers(app):
    def respond(status, message):
        if request.path.startswith("/api/"):
            return jsonify({"error": message}), status
        return render_template("error.html", code=status, message=message), status

    @app.errorhandler(404)
    def not_found(_):
        return respond(404, "We could not find what you were looking for.")

    @app.errorhandler(405)
    def method_not_allowed(_):
        return respond(405, "That action is not allowed here.")

    @app.errorhandler(500)
    def server_error(_):
        db.session.rollback()
        return respond(500, "Something went wrong on our side. Please try again.")


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create database tables (safe to run repeatedly; keeps existing data)."""
        attempts = 10
        for attempt in range(1, attempts + 1):
            try:
                db.create_all()
                click.echo("Database tables are ready.")
                return
            except OperationalError:
                click.echo(f"Database not ready yet (attempt {attempt}/{attempts}). Retrying...")
                time.sleep(3)
        raise SystemExit("Could not connect to the database. Check your .env settings.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Add a few sample tasks for a demo (only if the table is empty)."""
        from datetime import date, timedelta

        from .models import Task

        if Task.query.count() > 0:
            click.echo("Tasks already exist. Nothing added.")
            return
        today = date.today()
        samples = [
            ("Prepare viva presentation", "Slides on Docker, Compose and CI.", "in_progress", "high", today + timedelta(days=2)),
            ("Write project README", "Add screenshots and run instructions.", "todo", "medium", today + timedelta(days=5)),
            ("Push code to GitHub", "Create the repository and check the Actions tab.", "completed", "medium", today - timedelta(days=1)),
            ("Revise PostgreSQL basics", "Tables, primary keys, SELECT and JOIN.", "todo", "low", None),
            ("Fix overdue lab record", "Submit the DevOps lab record.", "todo", "high", today - timedelta(days=3)),
        ]
        for title, desc, status, priority, due in samples:
            db.session.add(Task(title=title, description=desc, status=status, priority=priority, due_date=due))
        db.session.commit()
        click.echo(f"Added {len(samples)} sample tasks.")
