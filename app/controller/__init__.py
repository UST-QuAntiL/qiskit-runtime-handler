from app.controller import qiskit_runtime

MODULES = (qiskit_runtime,)


def register_blueprints(api):
    """Initialize application with all modules"""
    for module in MODULES:
        api.register_blueprint(module.blp)
