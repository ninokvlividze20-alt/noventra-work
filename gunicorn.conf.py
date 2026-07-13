cat <<EOF > gunicorn.conf.py
worker_class = 'sync'
workers = 2
timeout = 120
EOF
