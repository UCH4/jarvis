"""
core/memory.py — Memoria persistente usando SQLite.
"""
import sqlite3
import os
from datetime import datetime
from pathlib import Path

DB_PATH = os.path.expanduser("~/.jarvis_memory.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_memory():
    """Inicializa las tablas de la base de datos si no existen."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Historial de Chat
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            role TEXT,
            content TEXT,
            mode TEXT,
            vault_path TEXT
        )
    ''')
    
    # Historial de Comandos Terminal
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS terminal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            command TEXT,
            output TEXT,
            status TEXT
        )
    ''')
    
    # Progreso de Aprendizaje (Ejercicios)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            topic TEXT,
            type TEXT,
            score INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

def save_chat_message(role: str, content: str, mode: str = "normal", vault_path: str = ""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (timestamp, role, content, mode, vault_path) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), role, content, mode, vault_path)
    )
    conn.commit()
    conn.close()

def get_recent_chat_history(limit: int = 10) -> list:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    # Invertir para que esté en orden cronológico
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def save_terminal_command(command: str, output: str, status: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO terminal_history (timestamp, command, output, status) VALUES (?, ?, ?, ?)",
        (datetime.now().isoformat(), command, output, status)
    )
    conn.commit()
    conn.close()

# Inicializar al importar
if not os.path.exists(DB_PATH):
    init_memory()
else:
    init_memory() # Por si hay actualizaciones de schema
