"""Entry point. Gunicorn loads `run:app`; `python run.py` starts the dev server."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # 0.0.0.0 = listen on all network interfaces (required inside a container).
    app.run(host="0.0.0.0", port=5000, debug=False)
