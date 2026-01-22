#!/bin/bash


echo "Starting TrueCite Backend..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

sleep 5


PORT="${PORT:-8080}"
echo "Starting TrueCite Frontend on port $PORT..."
streamlit run src/frontend/app.py --server.port $PORT --server.address 0.0.0.0