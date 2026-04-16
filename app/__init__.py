from flask import Flask

def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = "dev"
    app.config["DATABASE"] = "instance/database.db"

    from .routes import main
    app.register_blueprint(main)

    return app