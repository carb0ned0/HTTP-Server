#!/bin/bash

# run.sh — Starts the WSGI HTTPS server

# Auto-generate certs if missing
if [ ! -f cert.pem ] || [ ! -f key.pem ]; then
  echo "📜 Generating self-signed cert.pem and key.pem..."
  openssl req -new -x509 -days 365 -nodes \
    -out cert.pem -keyout key.pem \
    -subj "/C=local/ST=Dev/L=Local/O=SelfSigned/CN=localhost"
fi

# Set environment path
export PYTHONPATH=.

# Default WSGI app module
APP="wsgiapp:app"

# Port
PORT=8443

# Run server
echo "Starting WSGI HTTPS server at https://localhost:$PORT/"
python server/webServer.py "$APP"
