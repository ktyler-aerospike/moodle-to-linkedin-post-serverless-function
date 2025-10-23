import functions_framework
from flask import Request
from werkzeug.wrappers.response import Response

from app import app as flask_app

@functions_framework.http
def linkedinposter(request: Request):
    """
    Adapter that forwards the incoming Cloud Run (functions-framework) HTTP request
    into your existing Flask application.
    """
    # Use Werkzeug's Response helper to call the WSGI app with the incoming environ
    return Response.from_app(flask_app.wsgi_app, request.environ)
