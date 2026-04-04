import os
from flask import Flask
from config import config


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(
        __name__,
        template_folder="web/templates",
        static_folder="web/static",
    )
    app.config.from_object(config[config_name])

    # Ensure scenarios directory exists
    app.config["SCENARIOS_DIR"].mkdir(exist_ok=True)

    # Initialise storage
    import storage.scenario_store as store
    store.init_store(app.config["SCENARIOS_DIR"])

    # Blueprints
    from routes.main import main_bp
    from routes.profile import profile_bp
    from routes.scenarios import scenarios_bp
    from routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(scenarios_bp)
    app.register_blueprint(api_bp)

    return app


if __name__ == "__main__":
    app = create_app("development")
    app.run(debug=True, port=5000)
