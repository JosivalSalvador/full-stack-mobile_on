"""Ponto único que agrega o router de cada módulo de negócio.

`main.py` inclui apenas `api_router`, sem precisar conhecer os módulos
individualmente. Adicionar um novo módulo em `app/modules/` significa
registrar seu router aqui, e em nenhum outro lugar.
"""

from fastapi import APIRouter

from ai_service.app.domain.vault_audit.router import router as vault_audit_router

api_router = APIRouter()
api_router.include_router(vault_audit_router)
