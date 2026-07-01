#!/bin/bash

cd "$(dirname "$0")"

if [ ! -d ".git" ]; then
    git init
    git branch -M main
fi

# Rimuovi l'origin se esiste già e aggiungilo di nuovo
git remote remove origin 2>/dev/null
git remote add origin https://github.com/Raffaele-wq/scopone

git add .

# Usa il primo argomento come messaggio, altrimenti usa la data attuale
COMMIT_MSG=${1:-"Aggiornamento automatico: $(date +'%Y-%m-%d %H:%M:%S')"}

git commit -m "$COMMIT_MSG"

# Forza il push sul branch main per sovrascrivere tutto ciò che c'è nella repo
git push -u origin main --force

echo "Push completato con successo!"
