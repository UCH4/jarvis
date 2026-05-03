"""
core/cleanup.py — Herramientas para limpiar duplicados en el vault
"""
import re
import shutil
from pathlib import Path
from core.logger import log

def clean_vault_duplicates(vault_path: str, dry_run: bool = False) -> dict:
    """
    Escanea el vault y detecta notas que parecen ser duplicados.
    Criterios:
    1. Notas con el mismo 'fuente_pdf' en el YAML.
    2. Notas con nombres muy similares y sufijos de fecha.
    """
    vault = Path(vault_path).expanduser().resolve()
    if not vault.exists() or not vault.is_dir():
        log(f"Error: El vault en {vault_path} no existe o no es un directorio.", "error")
        return {"error": f"Vault no encontrado en {vault_path}"}

    log(f"Iniciando limpieza de duplicados en {vault.absolute()}...", "action")
    
    try:
        # 1. Ignorar la carpeta de basura y archivos ocultos de macOS (._*)
        # Esto evita bucles infinitos y errores de archivos de metadatos inexistentes
        notes = [
            n for n in vault.rglob("*.md") 
            if "_Limpieza_Duplicados" not in n.parts and not n.name.startswith("._")
        ]
    except Exception as e:
        log(f"Error escaneando el vault: {e}", "error")
        return {"error": f"Error accediendo a los archivos del vault: {str(e)}"}

    sources = {} # {fuente_pdf: [lista_de_rutas]}
    
    # 1. Agrupar por metadatos 'fuente_pdf'
    for note_path in notes:
        try:
            content = note_path.read_text(encoding="utf-8", errors="ignore")
            # Extraer fuente_pdf del YAML
            match = re.search(r'fuente_pdf:\s*"(.*?)"', content)
            if match:
                src = match.group(1)
                sources.setdefault(src, []).append(note_path)
            else:
                # Si no tiene metadatos, agrupar por nombre base (antes del timestamp)
                # Ejemplo: "Titulo - Archivo_20260503_110000.md" -> "Titulo - Archivo"
                name_clean = re.sub(r'_\d{8}_\d{6}$', '', note_path.stem)
                sources.setdefault(f"NAME_{name_clean}", []).append(note_path)
        except Exception:
            continue

    removed_count = 0
    trash_dir = vault / "_Limpieza_Duplicados"
    
    report = {"deleted": [], "kept": []}

    for src, paths in sources.items():
        if len(paths) > 1:
            # Función segura para obtener mtime (evita FileNotFoundError en archivos bloqueados/fantasma)
            def safe_mtime(p):
                try: return p.stat().st_mtime
                except Exception: return 0

            paths.sort(key=safe_mtime, reverse=True)
            
            kept = paths[0]
            to_delete = paths[1:]
            
            report["kept"].append(str(kept.relative_to(vault)))
            
            for p in to_delete:
                rel_p = str(p.relative_to(vault))
                if not dry_run:
                    trash_dir.mkdir(exist_ok=True)
                    # Mover a carpeta de basura en lugar de borrar
                    dest = trash_dir / p.name
                    if dest.exists():
                        dest = trash_dir / f"{p.stem}_{removed_count}.md"
                    shutil.move(str(p), str(dest))
                
                report["deleted"].append(rel_p)
                removed_count += 1
                log(f"Duplicado detectado y movido: {rel_p}", "warn")

    if removed_count > 0:
        log(f"Limpieza completada: {removed_count} archivos movidos a {trash_dir.name}", "ok")
    else:
        log("No se encontraron duplicados evidentes.", "info")

    # Si hay demasiados archivos, truncamos el reporte para evitar errores de JSON/memoria
    if len(report["deleted"]) > 500:
        report["deleted"] = report["deleted"][:500]
        report["note"] = "Reporte truncado a 500 archivos por tamaño."

    return report
