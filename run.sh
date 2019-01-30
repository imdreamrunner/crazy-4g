sleep 10
export PYTHONUNBUFFERED=1
python app.py > ./log-`date +%Y-%m-%d_%H:%M:%S`.txt 2>&1 &

while true; do
    sleep 10
    server=`ps aux | grep app.py | grep -v grep`
    if [ ! "$server" ]; then
        python app.py > ./log-`date +%Y-%m-%d_%H:%M:%S`.txt 2>&1 &
        sleep 10
    fi
done
