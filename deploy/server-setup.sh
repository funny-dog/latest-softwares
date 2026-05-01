#!/usr/bin/env bash
# 阿里云 ECS（Ubuntu/Debian）一次性初始化脚本。
#
# 用法（在 iTerm 里 ssh 进服务器之后）：
#   curl -fsSL https://raw.githubusercontent.com/funny-dog/latest-softwares/main/deploy/server-setup.sh -o setup.sh
#   bash setup.sh
#
# 或者本地传过去：
#   scp deploy/server-setup.sh user@<aliyun-ip>:/tmp/
#   ssh user@<aliyun-ip> 'bash /tmp/server-setup.sh'
#
# 这个脚本会：
#   1. 装 nginx
#   2. 创建部署目录 /var/www/latest-softwares
#   3. 写 nginx 站点配置（监听 8080）
#   4. 生成专门的 deploy SSH key 并加到 authorized_keys
#   5. 提示你把私钥粘贴到 GitHub Secrets

set -euo pipefail

readonly DEPLOY_PATH="/var/www/latest-softwares"
readonly NGINX_SITE="/etc/nginx/sites-available/latest-softwares"
readonly DEPLOY_KEY="$HOME/.ssh/latest-softwares-deploy"
readonly API_DIR="/opt/latest-softwares"
readonly METRICS_DIR="/var/lib/latest-softwares"

echo "=============================================================="
echo "  Latest Softwares — 阿里云 ECS 一次性初始化"
echo "=============================================================="

# ---------- Step 1: 装包 ----------
echo
echo "[1/7] 安装 nginx + Python..."
sudo apt-get update -y
sudo apt-get install -y nginx rsync python3 python3-venv python3-pip

# ---------- Step 2: 部署目录 ----------
echo
echo "[2/7] 创建部署目录 $DEPLOY_PATH ..."
sudo mkdir -p "$DEPLOY_PATH"
sudo chown -R "$USER:$USER" "$DEPLOY_PATH"
# 写一个占位首页，方便首次访问还没 rsync 时不 404
cat > "$DEPLOY_PATH/index.html" <<'EOF'
<!doctype html><meta charset="utf-8">
<title>等待首次部署</title>
<body style="font-family:system-ui;text-align:center;padding:4rem;color:#444">
<h2>📦 等待首次 GitHub Actions 部署</h2>
<p>本页内容尚未由 CI 推送。请检查 Actions 是否成功跑过 deploy job。</p>
</body>
EOF

# ---------- Step 3: nginx 配置 ----------
echo
echo "[3/7] 写 nginx 站点配置..."
sudo tee "$NGINX_SITE" > /dev/null <<'NGINX_CONF'
server {
    listen 8080 default_server;
    listen [::]:8080 default_server;
    server_name _;

    root /var/www/latest-softwares;
    index index.html;
    charset utf-8;

    # API 反向代理（CN 版后端）
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.(js|css|svg|png|ico|woff2?)$ {
        expires 1h;
        add_header Cache-Control "public, max-age=3600";
    }
    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    gzip on;
    gzip_vary on;
    gzip_min_length 256;
    gzip_types text/plain text/css application/json application/javascript image/svg+xml;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    server_tokens off;

    access_log /var/log/nginx/latest-softwares.access.log;
    error_log  /var/log/nginx/latest-softwares.error.log warn;
}
NGINX_CONF

sudo ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/latest-softwares
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

# ---------- Step 4: API 后端 ----------
echo
echo "[4/7] 部署 API 后端..."
sudo mkdir -p "$API_DIR/data" "$METRICS_DIR"
sudo chown -R "$USER:$USER" "$API_DIR"
sudo chown -R www-data:www-data "$METRICS_DIR"

# 创建 Python 虚拟环境
python3 -m venv "$API_DIR/venv"
"$API_DIR/venv/bin/pip" install --quiet fastapi uvicorn

# 写入 systemd 服务
sudo tee /etc/systemd/system/latest-softwares-api.service > /dev/null <<SERVICE_CONF
[Unit]
Description=Latest Softwares CN API Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$API_DIR
ExecStart=$API_DIR/venv/bin/uvicorn deploy.cn_server:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5
Environment="LATEST_SOFTWARES_METRICS_FILE=$METRICS_DIR/metrics.json"
Environment="LATEST_SOFTWARES_DATA_FILE=$API_DIR/data/latest.json"

[Install]
WantedBy=multi-user.target
SERVICE_CONF

sudo systemctl daemon-reload
sudo systemctl enable latest-softwares-api
echo "  API 后端服务已配置（端口 8001，首次部署后自动启动）"

# ---------- Step 5: deploy key ----------
echo
echo "[5/7] 生成 deploy SSH key..."
if [ -f "$DEPLOY_KEY" ]; then
  echo "  发现现有 deploy key（$DEPLOY_KEY），跳过生成"
else
  ssh-keygen -t ed25519 -f "$DEPLOY_KEY" -N "" -C "github-actions-deploy"
fi

mkdir -p "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
chmod 700 "$HOME/.ssh"
chmod 600 "$HOME/.ssh/authorized_keys"

PUB_LINE="$(cat "$DEPLOY_KEY.pub")"
if ! grep -qF "$PUB_LINE" "$HOME/.ssh/authorized_keys"; then
  echo "$PUB_LINE" >> "$HOME/.ssh/authorized_keys"
  echo "  公钥已加入 authorized_keys"
else
  echo "  公钥已存在 authorized_keys 中，跳过"
fi

# ---------- Step 6: 防火墙 ----------
echo
echo "[6/7] 检查防火墙..."
if command -v ufw &>/dev/null; then
  sudo ufw allow 8080/tcp comment "Latest Softwares" 2>/dev/null || true
  echo "  ufw 已放行 8080"
else
  echo "  未检测到 ufw，请手动确认阿里云安全组已放行 TCP 8080"
fi

# ---------- Step 7: 总结 ----------
echo
echo "=============================================================="
echo "  ✅ 服务器初始化完成"
echo "=============================================================="
echo
echo "下一步：把私钥和服务器信息加到 GitHub Secrets"
echo "（仓库 Settings → Secrets and variables → Actions）："
echo
printf "  %-22s : %s\n" "ALIYUN_HOST"        "$(curl -fsSL --max-time 3 ifconfig.me 2>/dev/null || echo '<手动填写公网 IP>')"
printf "  %-22s : %s\n" "ALIYUN_USER"        "$USER"
printf "  %-22s : %s\n" "ALIYUN_DEPLOY_PATH" "$DEPLOY_PATH"
printf "  %-22s : %s\n" "ALIYUN_DEPLOY_KEY"  "（下方私钥整段，含 BEGIN / END 行）"
echo
echo "──── ALIYUN_DEPLOY_KEY 内容（复制下面整段）─────────────"
cat "$DEPLOY_KEY"
echo "─────────────────────────────────────────────────────────"
echo
echo "别忘了：阿里云控制台 → ECS → 安全组 → 入方向 → 放行 TCP 8080"
echo
echo "Secrets 加好后，去仓库 Actions 页面手动跑一次 'Sync Latest Software'"
echo "看 deploy job 是否成功；之后浏览器开 http://<你的IP>:8080/ 即可。"
