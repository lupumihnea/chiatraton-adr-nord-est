"""Composition root for HTTP routes."""

from fastapi import APIRouter

from app.api.routes import analysis, document_questions, documents, health, projects, validations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(document_questions.router)
api_router.include_router(documents.router)
api_router.include_router(analysis.router)
api_router.include_router(validations.router)
