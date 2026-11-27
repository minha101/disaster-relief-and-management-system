def register_blueprints(app):
    from . import auth, main, crud, gis, sos, tasks, intel, reports
    for m in (auth, main, crud, gis, sos, tasks, intel, reports):
        app.register_blueprint(m.bp)
