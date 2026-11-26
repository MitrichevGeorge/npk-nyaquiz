from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="frontend/templates")


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "landing.html", {"page_script": "auth.js"})


@router.get("/auth", response_class=HTMLResponse)
async def auth_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth.html", {"page_script": "auth.js"})


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "dashboard.html", {"page_script": "dashboard.js"})


@router.get("/host/{run_id}", response_class=HTMLResponse)
async def host_page(request: Request, run_id: str) -> HTMLResponse:
    return templates.TemplateResponse(request, "host.html", {"run_id": run_id, "page_script": "host.js"})


@router.get("/broadcast/{run_id}", response_class=HTMLResponse)
async def broadcast_page(request: Request, run_id: str, token: str = "") -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "broadcast.html",
        {"run_id": run_id, "broadcast_token": token, "page_script": "broadcast.js"},
    )


@router.get("/play/{join_code}", response_class=HTMLResponse)
async def participant_page(request: Request, join_code: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "participant.html",
        {"join_code": join_code.upper(), "page_script": "participant.js"},
    )


@router.get("/legal/{doc_type}", response_class=HTMLResponse)
async def legal_page(request: Request, doc_type: str) -> HTMLResponse:
    allowed = {"privacy", "terms", "disclaimer"}
    selected = doc_type if doc_type in allowed else "privacy"
    return templates.TemplateResponse(request, "legal.html", {"doc_type": selected, "page_script": ""})
