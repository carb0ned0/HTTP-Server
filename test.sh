#!/bin/bash

# test.sh — Run curl tests against your running server

PORT=8443
BASE_URL="https://localhost:$PORT"

echo "🔍 Testing static file access..."

echo -e "\n hello.txt:"
curl -k "$BASE_URL/static/hello.txt"

echo -e "\n index.html:"
curl -k "$BASE_URL/static/index.html"

echo -e "\n Range request (sample.mp4 if exists):"
curl -k https://localhost:8443/static/sample.mp4 -H "Range: bytes=0-20" --output - 2>/dev/null || echo "404"

echo -e "\n HEAD request:"
curl -k -I "$BASE_URL/static/hello.txt"

echo -e "\n\n✅ Done."
