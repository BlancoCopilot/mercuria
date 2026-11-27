#!/bin/sh
# Despliega MercurIA (web + API) al VPS y, opcionalmente, compila y publica la APK.
#   scripts/desplegar_vps.sh          → código, web y backend
#   scripts/desplegar_vps.sh --apk    → además compila la APK firmada y la publica en /descargas/MercurIA.apk
# Requisitos: llave SSH al VPS y una ruta del túnel de Cloudflare <dominio> → http://localhost:8090.
# El servidor se configura en scripts/vps.local (no se sube al repositorio):
#   VPS=usuario@host
#   URL=https://tu-dominio
set -eu
cd "$(dirname "$0")/.."
[ -f scripts/vps.local ] && . scripts/vps.local
: "${VPS:?Define VPS=usuario@host en scripts/vps.local}"
: "${URL:?Define URL=https://tu-dominio en scripts/vps.local}"
DIR=apps/mercuria

echo "== web"
(cd panel && npm run build)

if [ "${1:-}" = "--apk" ]; then
  echo "== apk"
  export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk"
  (cd panel && VITE_API_URL=$URL npm run apk)
  cp panel/android/app/build/outputs/apk/release/app-release.apk MercurIA.apk
fi

echo "== sincronizar"
rsync -az --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' --exclude 'node_modules' \
  --exclude 'panel/android' --exclude 'panel/android-keys' --exclude 'panel/dist-mobile' --exclude 'panel/dist/descargas' \
  --exclude 'data/' --exclude 'docker-compose.override.yml' --exclude '.DS_Store' --exclude 'MercurIA.apk' --exclude '*.dump' --exclude 'scripts/vps.local' \
  ./ "$VPS:$DIR/"
rsync -az data/raw/rag "$VPS:$DIR/data/raw/"
[ -f MercurIA.apk ] && ssh "$VPS" "mkdir -p $DIR/panel/dist/descargas" && rsync -az MercurIA.apk "$VPS:$DIR/panel/dist/descargas/MercurIA.apk"

echo "== reconstruir y levantar"
ssh "$VPS" "cd $DIR && sed -i 's/^DOMAIN=.*/DOMAIN=:80/' .env && \
  docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build"

echo "== prueba"
sleep 8
curl -fsS "$URL/healthz" && echo " $URL en línea"
