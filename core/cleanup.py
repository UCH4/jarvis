"""
core/cleanup.py — Herramientas para limpiar duplicados en el vault
"""
import os
import re
from pathlib import Path
from core.logger import log

def clean_vault_duplicates(vault_path: str, dry_run: bool = False) -> dict:
    """
    Escanea el vault y detecta notas que parecen ser duplicados.
    Criterios:
    1. Notas con el mismo 'fuente_pdf' en el YAML.
    2. Notas con nombres muy similares y sufijos de fecha.
    """
    vault = Path(vault_path)
    if not vault.exists():
        return {"error": "Vault no encontrado"}

    notes = list(vault.rglob("*.md"))
    sources = {} # {fuente_pdf: [lista_de_rutas]}
    
    log(f"Iniciando limpieza de duplicados en {vault_path}...", "action")
    
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
            # Ordenar por fecha de modificación (mantener la más reciente o la primera)
            # Aquí mantendremos la que tenga el nombre más "limpio" (sin fecha)
            # o simplemente la más reciente.
            paths.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
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
                    os.rename(p, dest)
                
                report["deleted"].append(rel_p)
                removed_count += 1
                log(f"Duplicado detectado y movido: {rel_p}", "warn")

    if removed_count > 0:
        log(f"Limpieza completada: {removed_count} archivos movidos a {trash_dir.name}", "ok")
    else:
        log("No se encontraron duplicados evidentes.", "info")

    return report
