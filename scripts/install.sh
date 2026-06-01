#!/bin/bash
set -e

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CURRENT_USER="$(whoami)"

echo "=== Newshash setup ==="
echo "Repo:  $REPO"
echo "User:  $CURRENT_USER"
echo

# 1. Virtualenv + dependencies
if [ ! -d "$REPO/.venv" ]; then
    echo "Creating virtualenv..."
    python3 -m venv "$REPO/.venv"
fi
source "$REPO/.venv/bin/activate"
echo "Installing dependencies..."
pip install -q -r "$REPO/requirements.txt"
echo "Done."
echo

# 2. API key
if [ ! -f "$REPO/.env" ]; then
    read -rp "Anthropic API key: " api_key
    echo "ANTHROPIC_API_KEY=$api_key" > "$REPO/.env"
    echo ".env created."
    echo
fi

# 3. dist/ site repo
if [ ! -d "$REPO/dist/.git" ]; then
    mkdir -p "$REPO/dist"
    cd "$REPO/dist"
    git init -q && git branch -M main
    read -rp "Site repo SSH URL (e.g. git@github-newshash:user/newshash-site.git): " remote_url
    git remote add origin "$remote_url"
    echo "dist/ repo initialised."
    echo
    cd "$REPO"
fi

# 4. Systemd service + timer
read -rp "Daily run time in HH:MM (default 06:00): " run_time
run_time="${run_time:-06:00}"

sudo tee /etc/systemd/system/newshash.service > /dev/null << EOF
[Unit]
Description=Newshash daily build and deploy

[Service]
Type=oneshot
User=$CURRENT_USER
WorkingDirectory=$REPO
ExecStart=$REPO/scripts/deploy.sh
EOF

sudo tee /etc/systemd/system/newshash.timer > /dev/null << EOF
[Unit]
Description=Run Newshash daily

[Timer]
OnCalendar=*-*-* ${run_time}:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable newshash.timer
sudo systemctl start newshash.timer
echo "Timer enabled — runs daily at ${run_time}."
echo

# 5. First build and push
read -rp "Run first build and push now? (y/n): " do_build
if [[ "$do_build" =~ ^[Yy]$ ]]; then
    "$REPO/scripts/deploy.sh"
fi

echo
echo "All done. Check status with: systemctl status newshash.timer"
