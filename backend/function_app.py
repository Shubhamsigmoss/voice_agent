"""
Azure Functions entry point.

Azure Functions runs the same FastAPI app (app/main.py) through the ASGI adapter, so local runs
(uvicorn app.main:app) and Azure behave the same. All routes (/api/chat, /api/stt, /api/outlets,
/api/health) are served by FastAPI; host.json sets routePrefix to "" so Azure does not add a second "/api".

Settings come from the Function App's Application settings (environment variables), not from .env.
"""
import azure.functions as func

from app.main import app as fastapi_app

# ANONYMOUS: the browser calls these routes directly, so a function key would have to be put in the
# frontend, where anyone can read it. Protect the app with user login (App Service Authentication) instead.
app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
