#!/usr/bin/env bash
# ==============================================================================
# InsightX: AI Root Cause & Decision Intelligence Platform
# Unified Local Application Launcher
# DA-IICT | MSc Data Science | Group Innovation Project
# Authors: Aman Chauhan (202518004), Mannan Agarwal (202518013)
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=================================================================="
echo " Starting InsightX: AI Root Cause & Decision Intelligence Platform"
echo " Backend: FastAPI + SQLite + AST / Anomaly Analyzers (:8000)"
echo " Frontend: React + TypeScript + Vite + Tailwind CSS (:5173)"
echo "=================================================================="

# Cleanup on exit
cleanup() {
    echo ""
    echo "[InsightX] Shutting down application services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    echo "[InsightX] Services stopped cleanly."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 1. Start FastAPI Backend (unless --frontend-only)
if [ "$1" != "--frontend-only" ]; then
    echo "[1/2] Starting FastAPI backend on http://0.0.0.0:8000 (auto-reload enabled)..."
    export PYTHONPATH="$DIR"
    python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend &
    BACKEND_PID=$!
    sleep 2
fi

# 2. Start React Frontend (unless --backend-only)
if [ "$1" != "--backend-only" ]; then
    echo "[2/2] Starting Vite React frontend on http://0.0.0.0:5173..."
    cd "$DIR/frontend"
    npm run dev -- --host 0.0.0.0 --port 5173 &
    FRONTEND_PID=$!
fi

echo "=================================================================="
echo " InsightX is running!"
if [ "$1" != "--backend-only" ]; then
    echo " - Decision Dashboard: http://localhost:5173"
fi
if [ "$1" != "--frontend-only" ]; then
    echo " - Backend API & Docs: http://127.0.0.1:8000/docs"
fi
echo " Press Ctrl+C to stop all services."
echo "=================================================================="

wait
