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

echo "=============================================================="
echo "  Latest Softwares — 阿里云 ECS 一次性初始化"
echo "=============================================================="

# ---------- Step 1: 装包 ----------
echo
echo "[1/5] 安装 nginx..."
sudo apt-get update -y
sudo apt-get install -y nginx rsync

# ---------- Step 2: 部署目录 ----------
echo
echo "[2/5] 创建部署目录 $DEPLOY_PATH ..."
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
echo "[3/5] 写 nginx 站点配置..."
sudo tee "$NGINX_SITE" > /dev/null <<'NGINX_CONF'
server {
    listen 8080 default_server;
    listen [::]:8080 default_server;
    server_name _;

    root /var/www/latest-softwares;
    index index.html;
    charset utf-8;

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

# ---------- Step 4: deploy key ----------
echo
echo "[4/5] 生成 deploy SSH key..."
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

# ---------- Step 5: 总结 ----------
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
