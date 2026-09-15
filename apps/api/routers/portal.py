"""M0 门户：演示登录、菜单。"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from shared.auth import DEMO_USERS, menu_for_role, user_for_role

router = APIRouter(prefix="/api/portal", tags=["portal"])


def _role_from_header(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


@router.get("/roles")
def list_roles():
    return {
        "code": 0,
        "message": "",
        "data": [
            {"code": u.code, "label": u.label, "name": u.name, "home_path": u.home_path}
            for u in DEMO_USERS
        ],
    }


@router.get("/menu")
def get_menu(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")):
    role = _role_from_header(x_demo_role)
    user = user_for_role(role)
    return {
        "code": 0,
        "message": "",
        "data": {
            "role": role,
            "user_name": user.name if user else role,
            "items": menu_for_role(role),  # type: ignore[arg-type]
        },
    }


@router.get("/me")
def get_me(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")):
    role = _role_from_header(x_demo_role)
    user = user_for_role(role)
    if user is None:
        raise HTTPException(status_code=401, detail="无效角色")
    return {
        "code": 0,
        "message": "",
        "data": {
            "code": user.code,
            "label": user.label,
            "name": user.name,
            "home_path": user.home_path,
        },
    }
