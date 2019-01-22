sleep 10
export PYTHONUNBUFFERED=1
python app.py > ./log-`date +%Y-%m-%d_%H:%M:%S`.txt 2>&1
