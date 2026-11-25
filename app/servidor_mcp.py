"""servidor_mcp.py — Servidor MCP PROPIO del Gestor de solicitudes.

Procedencia : escrito por el equipo (Jilmar Veloza y Andrés Galvis) a partir de la
              herramienta `consultar_estado_solicitud` de las Clases 04 y 07 (notebook consolidado).
Versión     : 1.0.0
Transporte  : stdio (la aplicación lo arranca como subproceso; no escucha en la red).
Herramientas: UNA sola, de SOLO LECTURA -> consultar_estado_solicitud(codigo).
Datos       : FICTICIOS (SOL-1001 … SOL-1004). No hay base real de solicitudes.

Ejecución manual (diagnóstico):  python servidor_mcp.py
"""
from __future__ import annotations

import re
import sys

VERSION = "1.0.0"
PATRON_CODIGO = re.compile(r"^SOL-[0-9]{4}$")

# Datos ficticios, solo lectura.
SOLICITUDES = {
    "SOL-1001": {"estado": "en revisión", "area": "soporte técnico", "actualizado": "2026-09-14"},
    "SOL-1002": {"estado": "cerrada", "area": "registro académico", "actualizado": "2026-09-10"},
    "SOL-1003": {"estado": "pendiente de documentos", "area": "tesorería", "actualizado": "2026-09-16"},
    "SOL-1004": {"estado": "radicada", "area": "registro académico", "actualizado": "2026-09-18"},
}


def consultar_estado_solicitud(codigo: str) -> dict:
    """Devuelve el estado de una solicitud ficticia a partir de su código SOL-0000 (solo lectura)."""
    if not isinstance(codigo, str) or not PATRON_CODIGO.fullmatch(codigo):
        raise ValueError("El código debe tener el formato SOL-0000.")
    s = SOLICITUDES.get(codigo)
    return {"codigo": codigo, "encontrada": False} if s is None else {"codigo": codigo, "encontrada": True, **s}


def crear_servidor():
    from mcp.server.fastmcp import FastMCP

    servidor = FastMCP("gestor-solicitudes-estado")

    @servidor.tool(name="consultar_estado_solicitud",
                   description="Consulta (solo lectura) el estado de una solicitud por su código SOL-0000.")
    def _herramienta(codigo: str) -> dict:
        return consultar_estado_solicitud(codigo)

    return servidor


if __name__ == "__main__":
    if "--version" in sys.argv:
        print(VERSION)
    else:
        crear_servidor().run(transport="stdio")
