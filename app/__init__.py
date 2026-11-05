from flask import Flask, jsonify, redirect, request, url_for
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, CSRFError

from .config import Config
from .models import db, User

csrf = CSRFProtect()
login_manager = LoginManager()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if app.config["ENV_NAME"] == "production" and app.config["SECRET_KEY"] in ("", None, "dev-only-change-me"):
        raise RuntimeError("Set a strong SECRET_KEY environment variable in production.")

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify(error="Please log in again."), 401
        return redirect(url_for("auth.login"))

    from .auth import bp as auth_bp
    from .api import bp as api_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        return jsonify(error="Security check failed. Refresh the page and try again."), 400

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found"), 404
        return "Page not found", 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify(error="Request too large"), 413

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data:; frame-ancestors 'none'")
        if app.config["ENV_NAME"] == "production":
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.path.startswith(("/api/", "/app")):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    with app.app_context():
        db.create_all()
    return app
