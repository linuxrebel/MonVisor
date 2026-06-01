"""
monvisor/api/server.py
Phase 3 — FastAPI web UI (localhost only).

Login (bcrypt via SimpleAuthProvider), environment list, per-environment service
review with Yes/No toggles, and a generate trigger. Jinja2 templates + minimal JS.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from monvisor import config
from monvisor.db import queries
from monvisor.db.schema import init_db
from monvisor.auth.simple import SimpleAuthProvider

_WEB = Path(__file__).resolve().parent.parent / "web"
templates = Jinja2Templates(directory=str(_WEB / "templates"))
auth = SimpleAuthProvider()

COOKIE = "monvisor_session"


def _require_auth(request: Request) -> bool:
    token = request.cookies.get(COOKIE)
    return bool(token and auth.validate_token(token))


def create_app() -> FastAPI:
    app = FastAPI(title="MonVisor", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(_WEB / "static")), name="static")
    init_db()

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        if not _require_auth(request):
            return RedirectResponse("/login", status_code=303)
        envs = queries.list_environments()
        rows = []
        for e in envs:
            svcs = queries.get_services(e["id"])
            rows.append({
                "name": e["name"],
                "services": len(svcs),
                "monitored": len([s for s in svcs if s["monitor"] == 1]),
                "undecided": len([s for s in svcs if s["monitor"] is None]),
            })
        return templates.TemplateResponse("index.html", {"request": request, "envs": rows})

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        return templates.TemplateResponse("login.html", {"request": request, "error": None})

    @app.post("/login")
    def login(request: Request, password: str = Form(...)):
        token = auth.authenticate("admin", password)
        if not token:
            return templates.TemplateResponse(
                "login.html", {"request": request, "error": "Invalid password."}, status_code=401
            )
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(COOKIE, token, httponly=True, samesite="lax")
        return resp

    @app.get("/logout")
    def logout(request: Request):
        token = request.cookies.get(COOKIE)
        if token:
            auth.logout(token)
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(COOKIE)
        return resp

    @app.get("/env/{name}", response_class=HTMLResponse)
    def env_review(request: Request, name: str):
        if not _require_auth(request):
            return RedirectResponse("/login", status_code=303)
        env = queries.get_environment(name)
        if not env:
            raise HTTPException(404, "Environment not found")
        services = queries.get_services(env["id"])
        return templates.TemplateResponse(
            "report.html", {"request": request, "env": name, "services": services}
        )

    @app.post("/api/services/{service_id}/decision")
    def decide(request: Request, service_id: int, monitor: bool = Form(...)):
        if not _require_auth(request):
            raise HTTPException(401)
        queries.set_service_decision(service_id, monitor)
        return JSONResponse({"ok": True, "service_id": service_id, "monitor": monitor})

    @app.post("/api/env/{name}/generate")
    def generate(request: Request, name: str):
        if not _require_auth(request):
            raise HTTPException(401)
        from monvisor.cli.generate import run_generate
        run_generate(name)  # writes configs + persists; CLI console output is harmless here
        return JSONResponse({"ok": True})

    return app
