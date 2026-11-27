#!/bin/sh
# Trae los commits nuevos de GitHub (origin/main), los prueba en una copia aparte y, solo si todo pasa,
# despliega EXACTAMENTE esa versión en el VPS. Si el despliegue falla, vuelve a poner la versión anterior.
# Lo corre la tarea programada de Claude cada hora; también se puede correr a mano.
#
#   scripts/sincronizar_github.sh            revisa y, si hay commits nuevos que pasan las pruebas, despliega
#   scripts/sincronizar_github.sh --marcar   marca origin/main como ya desplegado (sin desplegar)
#
# Última línea de la salida (para leerla de forma automática):
#   SIN_CAMBIOS <commit> | DESPLEGADO <commit> | YA_FALLO <commit> | FALLO_<ETAPA> <commit> | OCUPADO
#
# Qué NO hace: no toca cambios locales sin subir (la carpeta de trabajo no se modifica, salvo avanzar
# main si está limpia), no publica la APK (eso sigue siendo `desplegar_vps.sh --apk`).
set -eu
cd "$(dirname "$0")/.."
RAIZ=$(pwd)
ESTADO="$RAIZ/.sync-github"          # último commit desplegado
FALLO="$RAIZ/.sync-github-fallo"     # último commit que falló (para no reintentarlo cada hora)
CANDADO="$RAIZ/.sync-github.lock"

mkdir "$CANDADO" 2>/dev/null || { echo "OCUPADO (otra sincronización en curso; si no es así, borra $CANDADO)"; exit 0; }
TMP=$(mktemp -d)
limpiar() {
  for wt in "$TMP"/wt-*; do [ -d "$wt" ] && git -C "$RAIZ" worktree remove --force "$wt" 2>/dev/null || true; done
  rm -rf "$TMP" "$CANDADO"
}
trap limpiar EXIT INT TERM

git fetch -q origin main
NUEVO=$(git rev-parse origin/main)
CORTO=$(git rev-parse --short "$NUEVO")
ULTIMO=$(cat "$ESTADO" 2>/dev/null || true)

if [ "${1:-}" = "--marcar" ]; then echo "$NUEVO" > "$ESTADO"; echo "MARCADO $CORTO"; exit 0; fi
if [ "$NUEVO" = "$ULTIMO" ]; then echo "SIN_CAMBIOS $CORTO"; exit 0; fi
if [ "$NUEVO" = "$(cat "$FALLO" 2>/dev/null || true)" ]; then
  echo "YA_FALLO $CORTO (no se reintenta hasta que llegue otro commit; ver el aviso anterior)"; exit 0
fi

echo "== commits nuevos en GitHub"
if [ -n "$ULTIMO" ] && git cat-file -e "$ULTIMO" 2>/dev/null; then git log --oneline "$ULTIMO..$NUEVO" | head -20
else git log --oneline -5 "$NUEVO"; fi

# Copia de trabajo aparte con ese commit, lista para probar y desplegar
preparar() {   # $1 = commit, $2 = nombre
  wt="$TMP/wt-$2"
  git worktree add -q --detach "$wt" "$1"
  cp "$RAIZ/.env" "$wt/.env"                                   # copia real: rsync no debe subir un enlace
  [ -f "$RAIZ/scripts/vps.local" ] && cp "$RAIZ/scripts/vps.local" "$wt/scripts/vps.local"
  if cmp -s "$wt/panel/package-lock.json" "$RAIZ/panel/package-lock.json"; then
    ln -s "$RAIZ/panel/node_modules" "$wt/panel/node_modules"  # mismas dependencias: se reutilizan
  else
    echo "== dependencias de la web cambiaron: npm ci"
    (cd "$wt/panel" && npm ci --no-audit --no-fund >/dev/null 2>&1)
  fi
  echo "$wt"
}

fallar() {     # $1 = etapa, $2 = archivo con la salida
  echo "--- últimas líneas ($1) ---"; tail -40 "$2"
  echo "$NUEVO" > "$FALLO"
  echo "FALLO_$1 $CORTO"; exit 1
}

WT=$(preparar "$NUEVO" nuevo | tail -1)

echo "== pruebas del servidor"
# PYTHONPATH primero: que se prueben los archivos del commit nuevo, no los de la carpeta de trabajo
(cd "$WT/backend" && PYTHONPATH="$WT/backend" "$RAIZ/backend/.venv/bin/python" -m pytest -q -p no:cacheprovider) \
  > "$TMP/pruebas.log" 2>&1 || fallar PRUEBAS "$TMP/pruebas.log"
tail -1 "$TMP/pruebas.log"

echo "== compilación de la web (TypeScript + Vite)"
(cd "$WT/panel" && npm run build) > "$TMP/web.log" 2>&1 || fallar COMPILACION "$TMP/web.log"
grep -E "built in" "$TMP/web.log" | tail -1

echo "== despliegue en el VPS"
if sh "$WT/scripts/desplegar_vps.sh" > "$TMP/despliegue.log" 2>&1; then
  tail -1 "$TMP/despliegue.log"
  echo "$NUEVO" > "$ESTADO"; rm -f "$FALLO"
  # la carpeta local avanza solo si no hay cambios sin subir (nunca se pisa trabajo de nadie)
  if [ -z "$(git -C "$RAIZ" status --porcelain)" ] && [ "$(git -C "$RAIZ" rev-parse --abbrev-ref HEAD)" = main ]; then
    git -C "$RAIZ" merge -q --ff-only "$NUEVO" 2>/dev/null && echo "carpeta local actualizada a $CORTO" || echo "carpeta local: no se pudo avanzar (divergió de GitHub)"
  else
    echo "carpeta local con cambios sin subir: no se tocó"
  fi
  echo "DESPLEGADO $CORTO"
else
  echo "--- últimas líneas (despliegue) ---"; tail -40 "$TMP/despliegue.log"
  if [ -n "$ULTIMO" ] && git cat-file -e "$ULTIMO" 2>/dev/null; then
    echo "== el despliegue falló: vuelvo a poner $(git rev-parse --short "$ULTIMO")"
    WT0=$(preparar "$ULTIMO" anterior | tail -1)
    if (cd "$WT0/panel" && npm run build >/dev/null 2>&1) && sh "$WT0/scripts/desplegar_vps.sh" > "$TMP/vuelta.log" 2>&1; then
      echo "versión anterior restaurada"
    else
      echo "¡no se pudo restaurar la versión anterior!"; tail -20 "$TMP/vuelta.log" 2>/dev/null || true
    fi
  fi
  echo "$NUEVO" > "$FALLO"
  echo "FALLO_DESPLIEGUE $CORTO"; exit 1
fi
