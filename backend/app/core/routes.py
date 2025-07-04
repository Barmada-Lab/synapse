from fastapi import APIRouter

from app.acquisition import routes as procedure_routes
from app.labware import routes as labware_routes
from app.users import routes as user_routes

api_router = APIRouter()
api_router.include_router(user_routes.api_router)
api_router.include_router(procedure_routes.api_router, tags=["acquisition"])
api_router.include_router(
    labware_routes.api_router, prefix="/labware", tags=["labware"]
)
