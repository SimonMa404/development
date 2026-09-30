#!/bin/zsh

# Run from project folder; optionally pass a port: ./run_app.sh 8502
cd "$(dirname "$0")"

PORT="${1:-8501}"

# create venv if missing
if [ ! -d ".venv" ]; then
  echo "Virtual environment not found. Creating it..."
  python3.12 -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies (this may take a moment)..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Generating demo Munich data..."
python scripts/05_generate_demo_munich_data.py

# find a free port starting from desired PORT
while lsof -i :$PORT >/dev/null 2>&1; do
  echo "Port $PORT is in use; trying next port..."
  PORT=$((PORT+1))
done

echo "Starting Streamlit on port $PORT..."
streamlit run app/app.py --server.headless true --server.port $PORT &
STREAMLIT_PID=$!

# give streamlit a moment to start, then open the browser (macOS 'open')
sleep 2
echo "Opening http://localhost:$PORT in the default browser..."
open "http://localhost:$PORT"

wait $STREAMLIT_PID
