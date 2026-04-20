# -*- coding: utf-8 -*-
"""
conftest.py — fixtures y mocks globales para los tests del backend.
Mockea el módulo app.database antes de cualquier import para que los tests
funcionen sin necesitar una conexión real a Supabase.
"""
import sys
from unittest.mock import MagicMock

# ── Mock de Supabase antes de importar cualquier módulo de la app ──────────
# Esto evita que app.database intente conectarse a Supabase al importar.
sys.modules.setdefault("app.database", MagicMock())
