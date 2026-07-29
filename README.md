# 上新了！我的饭

面向北京交通大学师生的食堂信息分享平台。项目提供菜品浏览、搜索、评分评论、社区交流和三餐打卡等功能。

线上地址：<http://wangyouran.pythonanywhere.com>

## 功能

- 食堂、档口、菜品三级浏览，以及菜品/档口/标签模糊搜索
- 菜品评分、评论和特价展示
- 社区发帖、图片上传、点赞、评论与关联菜品搜索
- 早午晚三餐打卡、积分、月历和排行榜
- 用户注册登录、管理员统计和内容管理

## 技术栈

- Python + Flask
- SQLite
- Flask-Login、bcrypt
- Jinja2、Bootstrap 5、原生 JavaScript

## 本地运行

建议使用 Python 3.10 或更高版本。

```bash
git clone https://github.com/youranwang-hub/bjtu-meal-hub.git
cd bjtu-meal-hub
python -m venv .venv
```

激活虚拟环境后安装依赖：

```bash
pip install -r requirements.txt
```

初始化一份演示数据库并启动应用：

```bash
python init_db.py
python app.py
```

浏览器打开 <http://127.0.0.1:5000>。

## 导入菜品数据

项目中的 Excel 数据源位于 `data/北交食堂菜品收集终版.xlsx`。需要重新生成菜品数据时：

```bash
python import_real_data.py
python fill_categories.py
```

以上操作会更新本地 `database.db`。该文件被 Git 忽略，线上已有用户、帖子和打卡数据不应被本地数据库覆盖。

## 环境变量

生产环境请设置强随机的 `SECRET_KEY`，不要依赖代码中的开发环境默认值。例如在 PowerShell 中：

```powershell
$env:SECRET_KEY = "replace-with-a-long-random-secret"
python app.py
```

## GitHub 与 PythonAnywhere 更新

代码管理和线上部署分开进行：GitHub 保存代码，PythonAnywhere 运行 Flask 应用。

```text
本地修改 -> git commit -> git push
PythonAnywhere -> git pull -> Web 页面 Reload
```

在 PythonAnywhere 的 Bash Console 中，首次部署可克隆仓库；后续仅需拉取最新提交：

```bash
cd ~/你的项目目录
git pull origin main
```

然后在 PythonAnywhere 的 `Web` 页面点击 `Reload`。Python 后端代码、依赖或静态资源变更后都建议 Reload。

## 不会提交到 GitHub 的内容

`.gitignore` 已排除以下运行时或本地文件：

- `database.db` 和数据库备份
- `static/uploads/` 中的用户上传图片
- `.env`
- Python 缓存和 IDE 配置

部署时请在 PythonAnywhere 单独保管线上数据库、上传文件和环境变量。

## 项目结构

```text
app.py                 Flask 应用工厂、CSRF 与错误处理
auth.py                注册、登录、登出
main_routes.py         首页、搜索、食堂/档口/菜品、评分评论
community_routes.py    社区帖子、点赞、评论、图片上传
checkin_routes.py      三餐打卡、积分、排行榜、个人主页
admin_routes.py        管理后台
helpers.py             数据库、时区、图片回退等共享逻辑
templates/             Jinja2 模板
static/                样式、前端脚本与菜品品类图片
schema.sql             SQLite 表结构
```

## 安全提示

请不要将真实数据库、用户上传文件、`.env`、部署令牌或管理员密码提交到公开仓库。`init_db.py` 中的演示账号仅用于本地开发，部署前应移除或修改。
