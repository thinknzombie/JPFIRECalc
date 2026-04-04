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

    # Jinja2 filters
    _SCENARIO_COLORS = ["#5b6af0", "#e8b84b", "#34c77b", "#e05252", "#a78bfa"]

    @app.template_filter("scenario_color")
    def scenario_color(index: int) -> str:
        """Map 1-based loop index to a chart colour."""
        return _SCENARIO_COLORS[(index - 1) % len(_SCENARIO_COLORS)]

    # Blueprints
    from routes.main import main_bp
    from routes.profile import profile_bp
    from routes.scenarios import scenarios_bp
    from routes.api import api_bp
    from routes.compare import compare_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(scenarios_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(compare_bp)

    return app


if __name__ == "__main__":
    app = create_app("development")
    app.run(debug=True, port=5000)
