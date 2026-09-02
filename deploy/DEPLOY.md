# 小食叙记 · 上线部署手册

从「备案已完成」到「小程序发布」的完整落地步骤。目标环境：Ubuntu 22.04/24.04 轻量服务器（未装宝塔，走纯命令行路径 A）。

> 域名已确定为 `xiaoshixuji.xyz`；`your_server_ip` 替换成服务器公网 IP。

---

## 0. 先决条件（很重要，别跳过）

### 0.1 把最新代码推送到 GitHub

服务器部署会从 Git 拉代码，但你本地还有**大量改动未提交**：

- 未跟踪：`api_routes.py`、整个 `miniprogram/` 目录、`PROJECT_HANDOFF.md`
- 已修改：`app.py`、`schema.sql`、全部模板、`README.md` 等

**如果直接 `git clone`，服务器拿到的会是旧代码，没有小程序 API。** 建议拆成两个提交：

```bash
git add app.py schema.sql api_routes.py README.md templates/ 项目介绍.md
git commit -m "feat: 新增小程序 API 与食堂建筑/人流报送"

git add miniprogram/
git commit -m "feat: 原生微信小程序端"

git push origin main
```

> 注意：`database.db`、`deploy/.env`（含密钥）、`static/uploads/` 已被 `.gitignore` 排除，不要手动 `git add` 上去。

### 0.2 准备三样信息

| 信息 | 从哪拿 |
|------|--------|
| 域名 + 服务器公网 IP | 云厂商控制台 |
| `WECHAT_APPID` / `WECHAT_APPSECRET` | 微信公众平台 → 开发管理 → 开发设置 |
| 服务器 SSH 登录方式 | 云厂商控制台（root 密码或密钥） |

---

## 1. 登录服务器

你已确认未装宝塔，直接走**第 2 节（路径 A：纯命令行）**。若想再确认一次，登录后执行：

```bash
ls /www/server/panel 2>/dev/null && echo "装了宝塔" || echo "纯命令行"
```

输出「纯命令行」即按第 2 节执行。

---

## 2. 路径 A：纯命令行部署

### 2.1 安装系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git sqlite3
```

Ubuntu 22.04 自带 Python 3.10，满足项目要求（≥3.10）。

### 2.2 拉代码、建虚拟环境

```bash
sudo mkdir -p /opt/bjtu-meal
sudo chown -R $USER:$USER /opt/bjtu-meal
git clone https://github.com/youranwang-hub/bjtu-meal-hub.git /opt/bjtu-meal
cd /opt/bjtu-meal
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt gunicorn
```

### 2.3 初始化数据库（导入 1400 道菜品）

```bash
cd /opt/bjtu-meal
.venv/bin/python init_db.py
.venv/bin/python import_real_data.py
.venv/bin/python fill_categories.py
```

### 2.4 配置环境变量

```bash
cp deploy/.env.example /opt/bjtu-meal/.env
nano /opt/bjtu-meal/.env   # 填入真实值
```

生成 `SECRET_KEY`：

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2.5 配置 gunicorn + systemd 开机自启

```bash
sudo cp deploy/bjtu-meal.service /etc/systemd/system/bjtu-meal.service
sudo systemctl daemon-reload
sudo systemctl enable --now bjtu-meal
sudo systemctl status bjtu-meal   # 看到 active (running) 即成功
```

如果启动报权限错误，把目录属主切给 www-data：

```bash
sudo chown -R www-data:www-data /opt/bjtu-meal
sudo systemctl restart bjtu-meal
```

### 2.6 域名解析 + HTTPS

**先解析域名**（云厂商控制台 → DNS 解析 → 添加 A 记录指向服务器 IP），等解析生效后：

```bash
ping xiaoshixuji.xyz   # 确认已经指向你的服务器 IP
```

**申请 SSL 证书（Let's Encrypt，免费自动续期）**：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d xiaoshixuji.xyz
```

certbot 会自动改 Nginx 配置并加证书。如果你更喜欢用 `deploy/nginx.conf` 的模板，改为手动模式：

```bash
sudo certbot certonly --nginx -d xiaoshixuji.xyz
# 然后按 deploy/nginx.conf 配置，把证书路径改成
# /etc/letsencrypt/live/xiaoshixuji.xyz/fullchain.pem 和 privkey.pem
```

### 2.7 配置 Nginx 反向代理

如果用 `deploy/nginx.conf` 模板：

```bash
sudo mkdir -p /etc/nginx/ssl
sudo cp deploy/nginx.conf /etc/nginx/sites-available/bjtu-meal.conf
# 编辑文件：替换 xiaoshixuji.xyz 和 SSL 证书路径
sudo ln -s /etc/nginx/sites-available/bjtu-meal.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 2.8 配置数据库备份

```bash
sudo chmod +x deploy/backup.sh
sudo crontab -e
# 加入一行：
0 3 * * * /opt/bjtu-meal/deploy/backup.sh >> /opt/bjtu-meal/backups/backup.log 2>&1
```

### 2.9 验证后端

```bash
curl -k https://xiaoshixuji.xyz/api/health   # 或访问首页看是否正常返回
```

---

## 3. 路径 B：装了宝塔面板

宝塔的优势是**一键 SSL 证书 + 可视化反向代理**。后端仍建议用命令行 systemd（宝塔的 Python 项目管理器对 Flask+gunicorn 支持一般）。

1. 后端照走 **第 2 节 2.1–2.5**（装依赖、拉代码、建库、环境变量、systemd）。宝塔已带 Nginx，若 2.1 里 nginx 装不上可跳过。
2. 宝塔面板 →「网站」→「添加站点」：绑定 `xiaoshixuji.xyz`，纯静态。
3. 站点设置 →「SSL」→「Let's Encrypt」一键申请证书并开启 HTTPS（宝塔会自动续期）。
4. 站点设置 →「反向代理」→ 添加：目标 `http://127.0.0.1:8000`。
5. 站点设置 →「配置文件」里确保有 `client_max_body_size 50m;`（或用面板的「上传大小限制」项设为 50MB）。
6. 备份照走 **2.8**。

---

## 4. 微信公众平台配置

1. 登录 [微信公众平台](https://mp.weixin.qq.com) → 开发 → 开发管理 → 开发设置 → 服务器域名。
2. 把 `request 合法域名`、`uploadFile 合法域名`、`downloadFile 合法域名` 三处都填 `https://xiaoshixuji.xyz`。
   - 要求：HTTPS、已 ICP 备案（你已完成）、域名不能带端口。
3. 「业务域名」本小程序未用 webview，可不填。

---

## 5. 小程序端改造

改 `miniprogram/app.js` 第 1 行：

```js
const API_BASE = 'https://xiaoshixuji.xyz/api';
```

然后在微信开发者工具里：
1. 详情 → 本地设置 → 勾选「不校验合法域名、web-view、TLS 版本」仅在本地调试用；**真机预览/发布前必须关掉**。
2. 编译预览，真机扫码验证：微信登录能走通、首页菜品能加载。

---

## 6. 管理员账号配置

1. 先用真机登录一次小程序（任意新微信用户）。
2. 查服务器拿到你的 openid：

```bash
sqlite3 /opt/bjtu-meal/database.db "SELECT openid, user_id FROM wechat_identity;"
```

3. 把 openid 填入 `.env` 的 `WECHAT_ADMIN_OPENIDS`（多个用逗号分隔）。
4. `sudo systemctl restart bjtu-meal`，重新登录后「我的」页应出现「管理员工作台」入口。

---

## 7. 上线验收清单

- [ ] 后端 HTTPS 可访问，无 502/500
- [ ] 真机微信登录成功，`wechat_identity` 表有记录
- [ ] 管理员 openid 白名单生效，能看到管理后台
- [ ] 评分、打卡、发帖（含图片上传）在真机正常
- [ ] 打开 `WECHAT_CONTENT_SAFETY=1` 后，正常内容可发、违规内容被拦
- [ ] 备份脚本已跑通一次，`backups/` 有文件
- [ ] 微信公众平台合法域名三处均已填
- [ ] 开发者工具「上传」→ 体验版 → 提交审核 → 审核通过后发布

---

## 8. 常见问题速查

| 现象 | 排查 |
|------|------|
| 小程序真机报「不在合法域名列表」 | 微信后台 request 域名没填 / 忘了 HTTPS / 开发者工具还勾着「不校验域名」 |
| 登录返回 503 | 服务器没设 `FLASK_ENV=production` 或 `WECHAT_APPID/SECRET` 没配 |
| 上传图片失败 | Nginx `client_max_body_size` 太小 |
| 首页图片裂 | 静态文件没走 Nginx 或 `static/uploads` 目录无写权限 |
| systemd 启动失败 | `journalctl -u bjtu-meal -n 50` 看日志；多半是 `.env` 没放或属主不对 |
