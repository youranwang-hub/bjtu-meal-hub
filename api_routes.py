"""供微信小程序调用的 JSON API。"""
from datetime import datetime, timedelta, timezone
from functools import wraps
import bcrypt
import json
import os
import random
import uuid
import hashlib
import re
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import secrets

from flask import jsonify, request, url_for
from helpers import get_db, beijing_now, get_dish_image, UPLOAD_FOLDER, ALLOWED_EXTENSIONS, MAX_FILE_SIZE


# 第一层自动审核：覆盖常见违法、诈骗和辱骂表达。生产环境还应接入微信内容安全服务。
SENSITIVE_TERMS = ('赌博', '博彩', '诈骗', '毒品', '代开发票', '办证', '色情', '裸聊', '傻逼', '操你', '妈的')
WECHAT_TOKEN_CACHE = {'value': '', 'expires_at': datetime.min}
BUILDING_LOCATIONS = {
    '东区食堂': (116.346054, 39.948394), '学生四食堂': (116.344112, 39.949765),
    '学活食堂': (116.338106, 39.950342),
    '明湖食堂': (116.343167, 39.953109), '西餐厅': (116.337475, 39.950994),
    '益民餐厅': (116.343553, 39.953118), '留园餐厅': (116.344173, 39.950140),
    '红果园餐厅': (116.344103, 39.950821)
}
ANONYMOUS_AVATARS = {
    'rice': '饭', 'leaf': '叶', 'tea': '茶', 'star': '星',
    'moon': '月', 'cloud': '云', 'seed': '芽', 'note': '记'
}


def validate_user_text(value, label='内容', min_length=1, max_length=1000):
    text = (value or '').strip()
    if len(text) < min_length or len(text) > max_length:
        return None, f'{label}长度应为 {min_length}-{max_length} 个字符'
    normalized = unicodedata.normalize('NFKC', text).lower()
    normalized = re.sub(r'[\s\W_]+', '', normalized, flags=re.UNICODE)
    if any(term in normalized for term in SENSITIVE_TERMS):
        return None, '内容含有不适宜发布的词语，请修改后再试'
    if len(re.findall(r'https?://', text, flags=re.I)) > 1:
        return None, '请勿发布多个外部链接'
    if re.search(r'(.)\1{7,}', text):
        return None, '请勿重复发送相同字符'
    return text, None


def beijing_time(value, with_seconds=False):
    """SQLite 的 CURRENT_TIMESTAMP 按 UTC 存储；对外统一转换为北京时间。"""
    if not value:
        return ''
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value)[:19]
        try:
            parsed = datetime.strptime(text, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(timezone(timedelta(hours=8)))
    return local.strftime('%Y-%m-%d %H:%M:%S' if with_seconds else '%m-%d %H:%M')


def wechat_access_token():
    if WECHAT_TOKEN_CACHE['value'] and WECHAT_TOKEN_CACHE['expires_at'] > datetime.utcnow() + timedelta(minutes=2):
        return WECHAT_TOKEN_CACHE['value']
    app_id, app_secret = os.environ.get('WECHAT_APPID', ''), os.environ.get('WECHAT_APPSECRET', '')
    if not app_id or not app_secret:
        return ''
    query = urlencode({'grant_type': 'client_credential', 'appid': app_id, 'secret': app_secret})
    with urlopen(f'https://api.weixin.qq.com/cgi-bin/token?{query}', timeout=8) as response:
        data = json.loads(response.read().decode('utf-8'))
    token = data.get('access_token', '')
    if token:
        WECHAT_TOKEN_CACHE.update({'value': token, 'expires_at': datetime.utcnow() + timedelta(seconds=int(data.get('expires_in', 7200)))})
    return token


def wechat_text_safety_error(text, user, scene):
    """启用 WECHAT_CONTENT_SAFETY=1 后调用微信文本内容安全；未配置时安全降级到本地规则。"""
    if os.environ.get('WECHAT_CONTENT_SAFETY') != '1':
        return None
    try:
        db = get_db(); identity = db.execute('SELECT openid FROM wechat_identity WHERE user_id=?', (user['id'],)).fetchone(); db.close()
        if not identity:
            return None
        token = wechat_access_token()
        if not token:
            return '内容安全服务尚未配置完成，请稍后再试'
        body = json.dumps({'content': text, 'version': 2, 'scene': scene, 'openid': identity['openid']}).encode('utf-8')
        req = Request(f'https://api.weixin.qq.com/wxa/msg_sec_check?access_token={token}', data=body, headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(req, timeout=8) as response:
            result = json.loads(response.read().decode('utf-8'))
        if result.get('errcode', 0) != 0:
            return '内容安全服务暂时不可用，请稍后再试' if os.environ.get('WECHAT_CONTENT_SAFETY_FAIL_CLOSED') == '1' else None
        suggestion = (result.get('result') or {}).get('suggest', 'pass')
        if suggestion not in ('pass', 'risky') or suggestion == 'risky':
            return '内容未通过安全审核，请修改后再试'
    except Exception:
        if os.environ.get('WECHAT_CONTENT_SAFETY_FAIL_CLOSED') == '1':
            return '内容安全服务暂时不可用，请稍后再试'
    return None


def crowd_snapshot(db, canteen_id):
    # 仅汇总最近 90 分钟的同学报送，避免把过期状态当作实时信息。
    row = db.execute("SELECT COUNT(*) n, AVG(crowd_level) avg, MAX(create_time) latest FROM canteen_crowd_report WHERE canteen_id=? AND create_time>=datetime('now','-90 minutes')", (canteen_id,)).fetchone()
    count, average = row['n'], row['avg']
    if not count:
        return {'crowdStatus': '暂无报送', 'crowdCount': 0, 'crowdUpdatedAt': '', 'crowdHint': '等待同学报送'}
    status = '空闲' if average < 1.7 else ('适中' if average < 2.4 else '拥挤')
    return {'crowdStatus': status, 'crowdCount': count, 'crowdUpdatedAt': beijing_time(row['latest']), 'crowdHint': f'近 90 分钟 {count} 位同学报送'}


def building_crowd_snapshot(db, building_id):
    row = db.execute("SELECT COUNT(*) n, AVG(r.crowd_level) avg, MAX(r.create_time) latest FROM canteen_crowd_report r JOIN canteen c ON c.id=r.canteen_id WHERE c.building_id=? AND r.create_time>=datetime('now','-90 minutes')", (building_id,)).fetchone()
    if not row['n']:
        return {'crowdStatus': '暂无报送', 'crowdCount': 0, 'crowdUpdatedAt': '', 'crowdHint': '等待同学报送'}
    status = '空闲' if row['avg'] < 1.7 else ('适中' if row['avg'] < 2.4 else '拥挤')
    return {'crowdStatus': status, 'crowdCount': row['n'], 'crowdUpdatedAt': beijing_time(row['latest']), 'crowdHint': f'近 90 分钟 {row["n"]} 位同学报送'}


def ok(data=None, **extra):
    body = {'ok': True, 'data': data}
    body.update(extra)
    return jsonify(body)


def fail(message, status=400):
    return jsonify({'ok': False, 'message': message}), status


def payload():
    return request.get_json(silent=True) or request.form.to_dict() or {}


def token_user():
    header = request.headers.get('Authorization', '')
    token = header[7:] if header.startswith('Bearer ') else ''
    if not token:
        return None
    db = get_db()
    row = db.execute(
        'SELECT u.* FROM api_token t JOIN user u ON u.id=t.user_id '
        'WHERE t.token=? AND t.expire_time > ?', (token, beijing_now())
    ).fetchone()
    db.close()
    return row


def login_required_api(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        user = token_user()
        if not user:
            return fail('请先登录', 401)
        return func(user, *args, **kwargs)
    return wrapped


def admin_required_api(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        user = token_user()
        if not user:
            return fail('请先登录', 401)
        if not user['is_admin']:
            return fail('需要管理员权限', 403)
        return func(user, *args, **kwargs)
    return wrapped


def image_url(row):
    path = get_dish_image(row)
    return url_for('static', filename=path, _external=True) if path else ''


def dish_json(row):
    d = dict(row)
    raw_image = d.get('image_url') or ''
    has_real_image = raw_image.startswith('uploads/')
    return {
        'id': d['id'], 'name': d['name'], 'price': d['price'],
        'specialPrice': d.get('special_price'), 'rating': d.get('average_rating', 0),
        'isNew': bool(d.get('is_new')), 'tags': (d.get('tags') or '').split(','),
        'category': d.get('category') or '', 'stallName': d.get('stall_name', ''),
        'canteenName': d.get('canteen_name', ''), 'imageUrl': image_url(row),
        'hasRealImage': has_real_image, 'imageLabel': '实拍图' if has_real_image else '菜品示意图',
    }


def init_app(app):
    # 兼容已有数据库，不要求使用者重建数据。
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS api_token (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expire_time TIMESTAMP NOT NULL, create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    db.execute("CREATE TABLE IF NOT EXISTS new_dish_report (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, canteen_name TEXT, stall_name TEXT, dish_name TEXT NOT NULL, status TEXT DEFAULT 'pending', create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    db.execute("CREATE TABLE IF NOT EXISTS dish_image_submission (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, dish_id INTEGER, dish_name TEXT NOT NULL, image_path TEXT NOT NULL, status TEXT DEFAULT 'pending', create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    db.execute("CREATE TABLE IF NOT EXISTS wechat_identity (openid TEXT PRIMARY KEY, user_id INTEGER UNIQUE NOT NULL, create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    db.execute("CREATE TABLE IF NOT EXISTS user_feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, feedback_type TEXT NOT NULL DEFAULT '建议', content TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', reply TEXT, replied_time TIMESTAMP, read_time TIMESTAMP, create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    db.execute("CREATE TABLE IF NOT EXISTS canteen_crowd_report (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, canteen_id INTEGER NOT NULL, report_date DATE NOT NULL, crowd_level INTEGER NOT NULL CHECK (crowd_level BETWEEN 1 AND 3), create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE (user_id,canteen_id,report_date))")
    db.execute("CREATE TABLE IF NOT EXISTS canteen_building (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, longitude REAL, latitude REAL, description TEXT, create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    db.execute("CREATE TABLE IF NOT EXISTS community_content_report (id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER NOT NULL, target_type TEXT NOT NULL, target_id INTEGER NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    columns = {row['name'] for row in db.execute('PRAGMA table_info(post_comment)').fetchall()}
    if 'parent_id' not in columns:
        db.execute('ALTER TABLE post_comment ADD COLUMN parent_id INTEGER')
    if 'is_deleted' not in columns:
        db.execute('ALTER TABLE post_comment ADD COLUMN is_deleted INTEGER DEFAULT 0')
    feedback_columns = {row['name'] for row in db.execute('PRAGMA table_info(user_feedback)').fetchall()}
    if 'reply' not in feedback_columns:
        db.execute('ALTER TABLE user_feedback ADD COLUMN reply TEXT')
    if 'replied_time' not in feedback_columns:
        db.execute('ALTER TABLE user_feedback ADD COLUMN replied_time TIMESTAMP')
    if 'read_time' not in feedback_columns:
        db.execute('ALTER TABLE user_feedback ADD COLUMN read_time TIMESTAMP')
    canteen_columns = {row['name'] for row in db.execute('PRAGMA table_info(canteen)').fetchall()}
    if 'building_id' not in canteen_columns:
        db.execute('ALTER TABLE canteen ADD COLUMN building_id INTEGER')
    for row in db.execute('SELECT DISTINCT name FROM canteen').fetchall():
        name = row['name']; location = BUILDING_LOCATIONS.get(name, (None, None))
        db.execute('INSERT OR IGNORE INTO canteen_building (name,longitude,latitude) VALUES (?,?,?)', (name, location[0], location[1]))
        # 旧数据库可能已经生成过无坐标的建筑记录；补齐后让其立即出现在地图中。
        if location[0] is not None:
            db.execute('UPDATE canteen_building SET longitude=?, latitude=? WHERE name=?', (location[0], location[1], name))
        building = db.execute('SELECT id FROM canteen_building WHERE name=?', (name,)).fetchone()
        db.execute('UPDATE canteen SET building_id=? WHERE name=? AND building_id IS NULL', (building['id'], name))
    # 地图可先展示尚未收录菜品的餐厅；不伪造楼层、档口或菜品数据。
    for name, location in BUILDING_LOCATIONS.items():
        db.execute('INSERT OR IGNORE INTO canteen_building (name,longitude,latitude,description) VALUES (?,?,?,?)', (name, location[0], location[1], '资料筹备中'))
        db.execute('UPDATE canteen_building SET longitude=?, latitude=? WHERE name=?', (location[0], location[1], name))
    db.commit()
    db.close()

    @app.route('/api/health')
    def api_health():
        return ok({'service': 'meal-hub-api'})

    @app.route('/api/auth/login', methods=['POST'])
    def api_login():
        data = payload()
        username, password = data.get('username', '').strip(), data.get('password', '')
        if not username or not password:
            return fail('请输入用户名和密码')
        db = get_db()
        user = db.execute('SELECT * FROM user WHERE username=?', (username,)).fetchone()
        if not user or not bcrypt.checkpw(password.encode(), user['password'].encode()):
            db.close()
            return fail('用户名或密码错误', 401)
        token = secrets.token_urlsafe(32)
        expire = beijing_now() + timedelta(days=30)
        db.execute('DELETE FROM api_token WHERE user_id=? OR expire_time<=?', (user['id'], beijing_now()))
        db.execute('INSERT INTO api_token (token,user_id,expire_time) VALUES (?,?,?)', (token, user['id'], expire))
        db.commit(); db.close()
        return ok({'token': token, 'user': user_json(user)})

    @app.route('/api/auth/register', methods=['POST'])
    def api_register():
        data = payload()
        username, password = data.get('username', '').strip(), data.get('password', '')
        nickname = data.get('nickname', '').strip() or username
        if not 2 <= len(username) <= 20 or len(password) < 6:
            return fail('用户名需为 2-20 个字符，密码至少 6 位')
        db = get_db()
        if db.execute('SELECT 1 FROM user WHERE username=?', (username,)).fetchone():
            db.close(); return fail('用户名已存在')
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor = db.execute('INSERT INTO user (username,password,nickname) VALUES (?,?,?)', (username, hashed, nickname))
        user_id = cursor.lastrowid
        token = secrets.token_urlsafe(32)
        db.execute('INSERT INTO api_token (token,user_id,expire_time) VALUES (?,?,?)', (token, user_id, beijing_now() + timedelta(days=30)))
        user = db.execute('SELECT * FROM user WHERE id=?', (user_id,)).fetchone()
        db.commit(); db.close()
        return ok({'token': token, 'user': user_json(user)})

    @app.route('/api/auth/wechat', methods=['POST'])
    def wechat_login():
        code = payload().get('code', '').strip()
        if not code:
            return fail('微信登录凭证缺失')
        app_id, app_secret = os.environ.get('WECHAT_APPID', ''), os.environ.get('WECHAT_APPSECRET', '')
        if app_id and app_secret:
            try:
                query = urlencode({'appid': app_id, 'secret': app_secret, 'js_code': code, 'grant_type': 'authorization_code'})
                with urlopen(f'https://api.weixin.qq.com/sns/jscode2session?{query}', timeout=8) as response:
                    result = json.loads(response.read().decode('utf-8'))
                openid = result.get('openid')
                if not openid:
                    return fail('微信身份验证失败，请稍后再试', 401)
            except Exception:
                return fail('暂时无法连接微信登录服务', 503)
        elif os.environ.get('FLASK_ENV') != 'production':
            # 本地开发模拟身份，生产环境必须配置 AppID 与 AppSecret。
            openid = os.environ.get('WECHAT_DEV_OPENID', 'dev-admin')
        else:
            return fail('服务端尚未配置微信登录', 503)
        db = get_db()
        user = db.execute('SELECT u.* FROM wechat_identity w JOIN user u ON u.id=w.user_id WHERE w.openid=?', (openid,)).fetchone()
        if not user:
            admins = {x.strip() for x in os.environ.get('WECHAT_ADMIN_OPENIDS', '').split(',') if x.strip()}
            is_admin = int(openid in admins or (openid == 'dev-admin' and os.environ.get('FLASK_ENV') != 'production'))
            username = 'wx_' + hashlib.sha256(openid.encode()).hexdigest()[:12]
            password = secrets.token_urlsafe(32)
            cursor = db.execute('INSERT INTO user (username,password,nickname,is_admin) VALUES (?,?,?,?)', (username, password, '微信用户', is_admin))
            user_id = cursor.lastrowid
            db.execute('INSERT INTO wechat_identity (openid,user_id) VALUES (?,?)', (openid, user_id))
            user = db.execute('SELECT * FROM user WHERE id=?', (user_id,)).fetchone()
        token = secrets.token_urlsafe(32)
        db.execute('DELETE FROM api_token WHERE user_id=? OR expire_time<=?', (user['id'], beijing_now()))
        db.execute('INSERT INTO api_token (token,user_id,expire_time) VALUES (?,?,?)', (token, user['id'], beijing_now() + timedelta(days=30)))
        db.commit(); db.close()
        return ok({'token': token, 'user': user_json(user)})

    @app.route('/api/me/profile', methods=['POST'])
    @login_required_api
    def api_profile(user):
        data = payload()
        nickname, text_error = validate_user_text(data.get('nickname') or '', '昵称', 2, 16)
        avatar_id = (data.get('avatarId') or '').strip()
        if text_error:
            return fail(text_error)
        if avatar_id not in ANONYMOUS_AVATARS:
            return fail('请选择一个匿名头像')
        if safety_error := wechat_text_safety_error(nickname, user, 1):
            return fail(safety_error)
        db = get_db()
        db.execute('UPDATE user SET nickname=?,avatar_url=? WHERE id=?', (nickname, avatar_id, user['id']))
        updated = db.execute('SELECT * FROM user WHERE id=?', (user['id'],)).fetchone()
        db.commit(); db.close()
        return ok({'user': user_json(updated)})

    @app.route('/api/home')
    def api_home():
        db = get_db()
        base = 'SELECT d.*,s.name stall_name,c.name canteen_name FROM dish d JOIN stall s ON d.stall_id=s.id JOIN canteen c ON s.canteen_id=c.id '
        recommended = db.execute(base + 'WHERE d.average_rating>=4 ORDER BY d.average_rating DESC LIMIT 5').fetchall()
        if not recommended:
            recommended = db.execute(base + 'ORDER BY d.is_new DESC,d.id DESC LIMIT 5').fetchall()
        new = db.execute(base + 'WHERE d.is_new=1 ORDER BY d.create_time DESC LIMIT 4').fetchall()
        special = db.execute(base + 'WHERE d.special_price IS NOT NULL ORDER BY d.id LIMIT 4').fetchall()
        canteens = [dict(r) for r in db.execute('SELECT * FROM canteen ORDER BY id').fetchall()]
        for canteen in canteens: canteen.update(crowd_snapshot(db, canteen['id']))
        buildings = [dict(row) for row in db.execute('SELECT * FROM canteen_building WHERE longitude IS NOT NULL AND latitude IS NOT NULL ORDER BY id').fetchall()]
        for building in buildings:
            building['restaurants'] = [dict(row) for row in db.execute('SELECT id,name,floor FROM canteen WHERE building_id=? ORDER BY id', (building['id'],)).fetchall()]
            building['isCollecting'] = not bool(building['restaurants'])
            building.update(building_crowd_snapshot(db, building['id']))
        db.close()
        return ok({'recommended': [dish_json(x) for x in recommended], 'newDishes': [dish_json(x) for x in new], 'specialDishes': [dish_json(x) for x in special], 'canteens': canteens, 'canteenBuildings': buildings})

    @app.route('/api/specials')
    def api_specials():
        db=get_db(); rows=db.execute('SELECT d.*,s.name stall_name,c.name canteen_name FROM dish d JOIN stall s ON s.id=d.stall_id JOIN canteen c ON c.id=s.canteen_id WHERE d.special_price IS NOT NULL ORDER BY d.id').fetchall(); db.close()
        return ok([dish_json(x) for x in rows])

    @app.route('/api/dishes')
    def api_dishes():
        q = request.args.get('q', '').strip()
        stall_id = request.args.get('stallId', type=int)
        db = get_db()
        sql = 'SELECT d.*,s.name stall_name,c.name canteen_name FROM dish d JOIN stall s ON d.stall_id=s.id JOIN canteen c ON s.canteen_id=c.id WHERE 1=1'
        args = []
        if q:
            sql += ' AND (d.name LIKE ? OR d.tags LIKE ? OR s.name LIKE ?)'; args += [f'%{q}%'] * 3
        if stall_id:
            sql += ' AND d.stall_id=?'; args.append(stall_id)
        rows = db.execute(sql + ' ORDER BY d.average_rating DESC,d.id LIMIT 50', args).fetchall(); db.close()
        return ok([dish_json(x) for x in rows])

    @app.route('/api/canteens/<int:canteen_id>')
    def api_canteen(canteen_id):
        db = get_db(); c = db.execute('SELECT * FROM canteen WHERE id=?', (canteen_id,)).fetchone()
        if not c: db.close(); return fail('食堂不存在', 404)
        stalls = db.execute('SELECT s.*,COUNT(d.id) dish_count FROM stall s LEFT JOIN dish d ON d.stall_id=s.id WHERE s.canteen_id=? GROUP BY s.id ORDER BY s.id', (canteen_id,)).fetchall()
        result = dict(c); result.update(crowd_snapshot(db, canteen_id)); result['stalls'] = [dict(x) for x in stalls]; db.close()
        return ok(result)

    @app.route('/api/canteens/<int:canteen_id>/crowd', methods=['POST'])
    @login_required_api
    def api_report_crowd(user, canteen_id):
        try: level = int(payload().get('level'))
        except (TypeError, ValueError): return fail('请选择人流情况')
        if level not in (1, 2, 3): return fail('无效的人流选项')
        db = get_db()
        if not db.execute('SELECT 1 FROM canteen WHERE id=?', (canteen_id,)).fetchone(): db.close(); return fail('食堂不存在', 404)
        today = beijing_now().date().isoformat()
        db.execute("INSERT INTO canteen_crowd_report (user_id,canteen_id,report_date,crowd_level) VALUES (?,?,?,?) ON CONFLICT(user_id,canteen_id,report_date) DO UPDATE SET crowd_level=excluded.crowd_level,create_time=CURRENT_TIMESTAMP", (user['id'], canteen_id, today, level))
        result = crowd_snapshot(db, canteen_id); db.commit(); db.close()
        return ok(result, message='感谢你的报送')

    @app.route('/api/dishes/<int:dish_id>')
    def api_dish(dish_id):
        db = get_db(); row = db.execute('SELECT d.*,s.name stall_name,c.name canteen_name FROM dish d JOIN stall s ON d.stall_id=s.id JOIN canteen c ON s.canteen_id=c.id WHERE d.id=?', (dish_id,)).fetchone()
        if not row: db.close(); return fail('菜品不存在', 404)
        photo_count = db.execute("SELECT COUNT(*) n FROM dish_image_submission WHERE dish_id=? AND status='approve'", (dish_id,)).fetchone()['n']; db.close()
        result = dish_json(row); result['photoCount'] = photo_count
        return ok({'dish': result})

    @app.route('/api/dishes/<int:dish_id>/rate', methods=['POST'])
    @login_required_api
    def api_rate(user, dish_id):
        score = payload().get('score')
        try: score = int(score)
        except (TypeError, ValueError): return fail('请选择 1-5 分')
        if score not in range(1, 6): return fail('请选择 1-5 分')
        db = get_db(); db.execute('INSERT INTO rating (user_id,dish_id,score) VALUES (?,?,?) ON CONFLICT(user_id,dish_id) DO UPDATE SET score=excluded.score,create_time=CURRENT_TIMESTAMP', (user['id'], dish_id, score))
        avg = db.execute('SELECT ROUND(AVG(score),1) avg FROM rating WHERE dish_id=?', (dish_id,)).fetchone()['avg'] or 0
        db.execute('UPDATE dish SET average_rating=? WHERE id=?', (avg, dish_id)); db.commit(); db.close()
        return ok({'rating': avg})

    @app.route('/api/checkins', methods=['GET', 'POST'])
    @login_required_api
    def api_checkins(user):
        db = get_db(); today = beijing_now().date().isoformat()
        if request.method == 'POST':
            meal = payload().get('mealType', '')
            custom = payload().get('customDish', '').strip()[:60]
            dish_ids = [str(x) for x in payload().get('dishIds', []) if str(x).isdigit()]
            if meal not in ('breakfast', 'lunch', 'dinner'): db.close(); return fail('请选择餐次')
            if not dish_ids and not custom: db.close(); return fail('请选择食堂菜品或填写自定义菜品')
            if db.execute('SELECT 1 FROM checkin WHERE user_id=? AND checkin_date=? AND meal_type=?', (user['id'], today, meal)).fetchone(): db.close(); return fail('该餐次已打卡')
            if custom: dish_ids.append('custom:' + custom)
            db.execute('INSERT INTO checkin (user_id,meal_type,dish_ids,checkin_date) VALUES (?,?,?,?)', (user['id'], meal, ','.join(dish_ids), today))
            db.execute('UPDATE user SET checkin_points=checkin_points+? WHERE id=?', (3 if meal == 'breakfast' else 2, user['id'])); db.commit(); db.close()
            return ok(message='打卡成功')
        month = request.args.get('month', today[:7])
        if not re.fullmatch(r'\d{4}-\d{2}', month):
            db.close(); return fail('月份格式应为 YYYY-MM')
        today_rows = db.execute('SELECT * FROM checkin WHERE user_id=? AND checkin_date=?', (user['id'], today)).fetchall()
        month_rows = db.execute("SELECT * FROM checkin WHERE user_id=? AND strftime('%Y-%m', checkin_date)=? ORDER BY checkin_date,create_time", (user['id'], month)).fetchall()
        dish_ids = {int(value) for row in month_rows for value in (row['dish_ids'] or '').split(',') if value.isdigit()}
        dishes = {row['id']: row['name'] for row in db.execute(f"SELECT id,name FROM dish WHERE id IN ({','.join('?' for _ in dish_ids)})", tuple(dish_ids)).fetchall()} if dish_ids else {}
        rank = db.execute('SELECT nickname,checkin_points FROM user ORDER BY checkin_points DESC LIMIT 10').fetchall(); db.close()
        labels = {'breakfast': '早餐', 'lunch': '午餐', 'dinner': '晚餐'}
        records = []
        for row in month_rows:
            names = [dishes[int(value)] for value in (row['dish_ids'] or '').split(',') if value.isdigit() and int(value) in dishes]
            names.extend(value[7:] for value in (row['dish_ids'] or '').split(',') if value.startswith('custom:'))
            records.append({'date': row['checkin_date'], 'mealType': row['meal_type'], 'mealLabel': labels.get(row['meal_type'], '用餐'), 'dishText': '、'.join(names) or '这顿饭', 'checkinTime': beijing_time(row['create_time'])})
        return ok({'doneMeals': [x['meal_type'] for x in today_rows], 'calendarRecords': records, 'leaderboard': [dict(x) for x in rank]})

    @app.route('/api/community', methods=['GET', 'POST'])
    def api_community():
        if request.method == 'POST':
            user = token_user()
            if not user:
                return fail('请先登录', 401)
            raw_content = request.form.get('content') or payload().get('content', '')
            content, text_error = validate_user_text(raw_content, '帖子内容', 1, 1000) if raw_content.strip() else ('', None)
            if text_error: return fail(text_error)
            if content and (safety_error := wechat_text_safety_error(content, user, 1)): return fail(safety_error)
            images = request.files.getlist('images') or ([request.files.get('image')] if request.files.get('image') else [])
            saved_paths = payload().get('images', []) if not request.form else []
            if not isinstance(saved_paths, list): saved_paths = []
            saved_paths = [x for x in saved_paths[:3] if isinstance(x, str) and x.startswith('uploads/') and os.path.exists(os.path.join(os.path.dirname(UPLOAD_FOLDER), x))]
            if (not content and not images and not saved_paths) or len(content) > 1000 or len(images) > 3:
                return fail('帖子需包含文字或图片，文字不能超过 1000 字')
            image_paths = saved_paths
            for image in images:
                if not image or not image.filename: continue
                ext = os.path.splitext(image.filename)[1].lower()
                raw = image.read()
                if ext not in ALLOWED_EXTENSIONS or not raw or len(raw) > MAX_FILE_SIZE:
                    return fail('图片格式不支持或超过 5MB')
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                filename = f'{uuid.uuid4().hex}{ext}'
                with open(os.path.join(UPLOAD_FOLDER, filename), 'wb') as output: output.write(raw)
                image_paths.append(f'uploads/{filename}')
            db = get_db()
            db.execute('INSERT INTO post (user_id,content,images) VALUES (?,?,?)', (user['id'], content, json.dumps(image_paths)))
            db.commit(); db.close()
            return ok(message='发布成功')
        db = get_db()
        rows = db.execute('SELECT p.*,u.nickname,u.avatar_url,(SELECT COUNT(*) FROM post_comment pc WHERE pc.post_id=p.id AND pc.is_deleted=0) comment_count FROM post p JOIN user u ON u.id=p.user_id ORDER BY p.create_time DESC LIMIT 30').fetchall()
        viewer = token_user()
        posts = []
        for r in rows:
            images = json.loads(r['images']) if r['images'] else []
            liked = bool(viewer and db.execute('SELECT 1 FROM post_like WHERE user_id=? AND post_id=?', (viewer['id'], r['id'])).fetchone())
            posts.append({'id': r['id'], 'nickname': r['nickname'] or '用户', 'avatarLabel': ANONYMOUS_AVATARS.get(r['avatar_url'], '饭'), 'content': r['content'], 'likeCount': r['like_count'], 'liked': liked, 'isOwner': bool(viewer and viewer['id'] == r['user_id']), 'commentCount': r['comment_count'], 'createTime': beijing_time(r['create_time']), 'images': [url_for('static', filename=x, _external=True) for x in images]})
        db.close()
        return ok(posts)

    @app.route('/api/community/uploads', methods=['POST'])
    @login_required_api
    def api_community_upload(user):
        image=request.files.get('image')
        if not image or not image.filename:return fail('请选择图片')
        ext=os.path.splitext(image.filename)[1].lower(); raw=image.read()
        if ext not in ALLOWED_EXTENSIONS or not raw or len(raw)>MAX_FILE_SIZE:return fail('图片格式不支持或超过 5MB')
        os.makedirs(UPLOAD_FOLDER,exist_ok=True); filename=f'{uuid.uuid4().hex}{ext}'
        with open(os.path.join(UPLOAD_FOLDER,filename),'wb') as output:output.write(raw)
        return ok({'path':f'uploads/{filename}'})

    @app.route('/api/posts/<int:post_id>')
    def api_post_detail(post_id):
        db=get_db(); post=db.execute('SELECT p.*,u.nickname,u.avatar_url FROM post p JOIN user u ON u.id=p.user_id WHERE p.id=?',(post_id,)).fetchone()
        if not post: db.close(); return fail('帖子不存在',404)
        highlight_id=request.args.get('commentId',type=int)
        viewer = token_user()
        liked = bool(viewer and db.execute('SELECT 1 FROM post_like WHERE user_id=? AND post_id=?', (viewer['id'], post_id)).fetchone())
        comments=db.execute('SELECT pc.*,u.nickname,u.avatar_url,pu.nickname parent_nickname FROM post_comment pc JOIN user u ON u.id=pc.user_id LEFT JOIN post_comment parent ON parent.id=pc.parent_id LEFT JOIN user pu ON pu.id=parent.user_id WHERE pc.post_id=? ORDER BY pc.create_time ASC',(post_id,)).fetchall()
        db.close(); images=json.loads(post['images']) if post['images'] else []
        return ok({'post':{'id':post['id'],'nickname':post['nickname'] or '用户','avatarLabel':ANONYMOUS_AVATARS.get(post['avatar_url'], '饭'),'content':post['content'],'createTime':beijing_time(post['create_time']),'likeCount':post['like_count'],'liked':liked,'isOwner':bool(viewer and viewer['id']==post['user_id']),'images':[url_for('static',filename=x,_external=True) for x in images]},'comments':[{'id':x['id'],'parentId':x['parent_id'],'parentNickname':x['parent_nickname'] or '','nickname':x['nickname'] or '用户','avatarLabel':ANONYMOUS_AVATARS.get(x['avatar_url'], '饭'),'content':x['content'] if not x['is_deleted'] else '该评论已删除','isDeleted':bool(x['is_deleted']),'isOwner':bool(viewer and viewer['id']==x['user_id']),'createTime':beijing_time(x['create_time']),'highlight':x['id']==highlight_id} for x in comments]})

    @app.route('/api/posts/<int:post_id>/like', methods=['POST'])
    @login_required_api
    def api_like_post(user, post_id):
        db=get_db(); liked=db.execute('SELECT 1 FROM post_like WHERE user_id=? AND post_id=?',(user['id'],post_id)).fetchone()
        if liked: db.execute('DELETE FROM post_like WHERE user_id=? AND post_id=?',(user['id'],post_id))
        else: db.execute('INSERT OR IGNORE INTO post_like (user_id,post_id) VALUES (?,?)',(user['id'],post_id))
        count=db.execute('SELECT COUNT(*) n FROM post_like WHERE post_id=?',(post_id,)).fetchone()['n']; db.execute('UPDATE post SET like_count=? WHERE id=?',(count,post_id)); db.commit(); db.close()
        return ok({'likeCount':count,'liked':not bool(liked)})

    @app.route('/api/posts/<int:post_id>', methods=['DELETE'])
    @login_required_api
    def api_delete_own_post(user, post_id):
        db = get_db(); post = db.execute('SELECT user_id FROM post WHERE id=?', (post_id,)).fetchone()
        if not post: db.close(); return fail('帖子不存在', 404)
        if post['user_id'] != user['id']: db.close(); return fail('只能删除自己发布的帖子', 403)
        db.execute('DELETE FROM post_like WHERE post_id=?', (post_id,)); db.execute('DELETE FROM post_comment WHERE post_id=?', (post_id,)); db.execute("DELETE FROM community_content_report WHERE target_type='post' AND target_id=?", (post_id,)); db.execute('DELETE FROM post WHERE id=?', (post_id,)); db.commit(); db.close()
        return ok(message='帖子已删除')

    @app.route('/api/posts/<int:post_id>/comments', methods=['POST'])
    @login_required_api
    def api_post_comment(user, post_id):
        data=payload(); content, text_error=validate_user_text(data.get('content',''), '评论', 1, 300); parent_id=data.get('parentId')
        if text_error:return fail(text_error)
        if safety_error := wechat_text_safety_error(content, user, 2): return fail(safety_error)
        db=get_db()
        if not db.execute('SELECT 1 FROM post WHERE id=?',(post_id,)).fetchone(): db.close(); return fail('帖子不存在',404)
        if parent_id and not db.execute('SELECT 1 FROM post_comment WHERE id=? AND post_id=? AND is_deleted=0',(parent_id,post_id)).fetchone(): db.close(); return fail('回复对象不存在或已删除')
        db.execute('INSERT INTO post_comment (post_id,user_id,content,parent_id) VALUES (?,?,?,?)',(post_id,user['id'],content,parent_id or None)); db.commit(); db.close()
        return ok(message='评论成功')

    @app.route('/api/posts/<int:post_id>/comments/<int:comment_id>', methods=['DELETE'])
    @login_required_api
    def api_delete_own_comment(user, post_id, comment_id):
        db = get_db(); comment = db.execute('SELECT user_id FROM post_comment WHERE id=? AND post_id=? AND is_deleted=0', (comment_id, post_id)).fetchone()
        if not comment: db.close(); return fail('评论不存在或已删除', 404)
        if comment['user_id'] != user['id']: db.close(); return fail('只能删除自己的评论', 403)
        db.execute('UPDATE post_comment SET is_deleted=1,content="" WHERE id=?', (comment_id,)); db.execute("UPDATE community_content_report SET status='resolved' WHERE target_type='comment' AND target_id=? AND status='pending'", (comment_id,)); db.commit(); db.close()
        return ok(message='评论已删除')

    @app.route('/api/community/reports', methods=['POST'])
    @login_required_api
    def api_community_report(user):
        data = payload(); target_type = data.get('targetType'); target_id = data.get('targetId'); reason = (data.get('reason') or '').strip()
        if target_type not in ('post', 'comment') or not isinstance(target_id, int) or reason not in ('不友善内容', '广告或诈骗', '其他不适宜内容'):
            return fail('举报信息不完整')
        db = get_db(); table = 'post' if target_type == 'post' else 'post_comment'
        if not db.execute(f'SELECT 1 FROM {table} WHERE id=?', (target_id,)).fetchone(): db.close(); return fail('内容不存在', 404)
        if db.execute("SELECT 1 FROM community_content_report WHERE reporter_id=? AND target_type=? AND target_id=? AND status='pending'", (user['id'], target_type, target_id)).fetchone(): db.close(); return fail('你已举报过该内容')
        db.execute('INSERT INTO community_content_report (reporter_id,target_type,target_id,reason) VALUES (?,?,?,?)', (user['id'], target_type, target_id, reason)); db.commit(); db.close()
        return ok(message='举报已提交，管理员会尽快处理')

    @app.route('/api/new-dish-reports', methods=['POST'])
    @login_required_api
    def api_new_dish_report(user):
        data = payload()
        dish_name, text_error = validate_user_text(data.get('dishName', ''), '菜品名称', 1, 60)
        if text_error: return fail(text_error)
        canteen_name, text_error = validate_user_text(data.get('canteenName', ''), '食堂名称', 0, 60) if data.get('canteenName', '').strip() else ('', None)
        if text_error: return fail(text_error)
        stall_name, text_error = validate_user_text(data.get('stallName', ''), '档口名称', 0, 60) if data.get('stallName', '').strip() else ('', None)
        if text_error: return fail(text_error)
        if safety_error := wechat_text_safety_error(' '.join(filter(None, (canteen_name, stall_name, dish_name))), user, 3): return fail(safety_error)
        db = get_db()
        db.execute('INSERT INTO new_dish_report (user_id,canteen_name,stall_name,dish_name) VALUES (?,?,?,?)',
                   (user['id'], canteen_name, stall_name, dish_name))
        db.commit(); db.close()
        return ok(message='情报已送达')

    @app.route('/api/dishes/random')
    def api_random_dish():
        now = beijing_now()
        hour = now.hour
        meal = 'breakfast' if hour < 10 else ('lunch' if hour < 16 else 'dinner')
        labels = {'breakfast': '早餐', 'lunch': '午餐', 'dinner': '晚餐'}
        db = get_db()
        base = 'SELECT d.*,s.name stall_name,c.name canteen_name FROM dish d JOIN stall s ON d.stall_id=s.id JOIN canteen c ON s.canteen_id=c.id '
        if meal == 'breakfast':
            rows = db.execute(base + "WHERE d.tags LIKE '%早餐%' OR d.category='早餐' ORDER BY RANDOM() LIMIT 1").fetchall()
        else:
            rows = db.execute(base + 'ORDER BY RANDOM() LIMIT 1').fetchall()
        if not rows:
            db.close(); return fail('暂时没有可推荐的菜品', 404)
        dish = rows[0]; db.close()
        return ok({'dish': dish_json(dish), 'meal': meal, 'mealLabel': labels[meal]})

    @app.route('/api/dish-image-submissions', methods=['POST'])
    @login_required_api
    def api_dish_image_submission(user):
        dish_name, text_error = validate_user_text(request.form.get('dishName', ''), '菜品名称', 1, 60)
        image = request.files.get('image')
        if text_error:
            return fail(text_error)
        if safety_error := wechat_text_safety_error(dish_name, user, 4): return fail(safety_error)
        if not image or not image.filename:
            return fail('请先选择一张菜品图片')
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return fail('仅支持 JPG、PNG、GIF、WebP 图片')
        content = image.read()
        if not content or len(content) > MAX_FILE_SIZE:
            return fail('图片不能为空且不能超过 5MB')
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filename = f'{uuid.uuid4().hex}{ext}'
        with open(os.path.join(UPLOAD_FOLDER, filename), 'wb') as output:
            output.write(content)
        db = get_db()
        match = db.execute('SELECT id FROM dish WHERE name LIKE ? ORDER BY name LIMIT 1', (f'%{dish_name}%',)).fetchone()
        db.execute('INSERT INTO dish_image_submission (user_id,dish_id,dish_name,image_path) VALUES (?,?,?,?)',
                   (user['id'], match['id'] if match else None, dish_name, f'uploads/{filename}'))
        db.commit(); db.close()
        return ok(message='照片已送去审核')

    @app.route('/api/admin/overview')
    @admin_required_api
    def api_admin_overview(user):
        db = get_db()
        stats = {name: db.execute(f'SELECT COUNT(*) n FROM {table}').fetchone()['n'] for name, table in {
            'users': 'user', 'dishes': 'dish', 'posts': 'post', 'comments': 'comment', 'reports': 'new_dish_report', 'contentReports': 'community_content_report', 'photoSubmissions': 'dish_image_submission', 'feedback': 'user_feedback'
        }.items()}
        posts = db.execute('SELECT p.id,p.content,p.create_time,u.nickname FROM post p JOIN user u ON u.id=p.user_id ORDER BY p.create_time DESC LIMIT 10').fetchall()
        comments = db.execute('SELECT * FROM (SELECT c.id,c.content,c.create_time,u.nickname,"dish" AS source FROM comment c JOIN user u ON u.id=c.user_id UNION ALL SELECT pc.id,pc.content,pc.create_time,u.nickname,"post" AS source FROM post_comment pc JOIN user u ON u.id=pc.user_id) ORDER BY create_time DESC LIMIT 10').fetchall()
        special = db.execute('SELECT d.*,s.name stall_name,c.name canteen_name FROM dish d JOIN stall s ON s.id=d.stall_id JOIN canteen c ON c.id=s.canteen_id WHERE d.special_price IS NOT NULL ORDER BY d.id').fetchall()
        db.close()
        return ok({'stats': stats, 'posts': [dict(x) for x in posts], 'comments': [dict(x) for x in comments], 'specialDishes': [dish_json(x) for x in special]})

    @app.route('/api/admin/reviews')
    @admin_required_api
    def api_admin_reviews(user):
        db = get_db()
        photos = db.execute("SELECT s.*,u.nickname FROM dish_image_submission s JOIN user u ON u.id=s.user_id WHERE s.status='pending' ORDER BY s.create_time DESC").fetchall()
        reports = db.execute("SELECT r.*,u.nickname FROM new_dish_report r JOIN user u ON u.id=r.user_id WHERE r.status='pending' ORDER BY r.create_time DESC").fetchall()
        feedbacks = db.execute("SELECT f.*,u.nickname FROM user_feedback f JOIN user u ON u.id=f.user_id WHERE f.status='pending' ORDER BY f.create_time DESC").fetchall()
        content_reports = db.execute("SELECT r.*,u.nickname reporter_nickname FROM community_content_report r JOIN user u ON u.id=r.reporter_id WHERE r.status='pending' ORDER BY r.create_time DESC").fetchall()
        report_items = []
        for report in content_reports:
            if report['target_type'] == 'post':
                target = db.execute('SELECT content FROM post WHERE id=?', (report['target_id'],)).fetchone()
            else:
                target = db.execute('SELECT content,is_deleted FROM post_comment WHERE id=?', (report['target_id'],)).fetchone()
            report_items.append({'id': report['id'], 'targetType': report['target_type'], 'targetId': report['target_id'], 'reason': report['reason'], 'reporterNickname': report['reporter_nickname'], 'targetContent': (target['content'] if target and target['content'] else '内容已删除'), 'createTime': beijing_time(report['create_time'])})
        db.close()
        return ok({'photos': [{'id':x['id'],'dishName':x['dish_name'],'imageUrl':url_for('static',filename=x['image_path'],_external=True),'nickname':x['nickname'],'createTime':beijing_time(x['create_time'])} for x in photos], 'reports':[dict(x, createTime=beijing_time(x['create_time'])) for x in reports], 'contentReports': report_items, 'feedbacks':[dict(x, createTime=beijing_time(x['create_time'])) for x in feedbacks]})

    @app.route('/api/admin/feedback/<int:feedback_id>', methods=['POST'])
    @admin_required_api
    def api_admin_feedback(user, feedback_id):
        reply, text_error = validate_user_text(payload().get('reply') or '', '回复内容', 2, 500)
        if text_error: return fail(text_error)
        db = get_db(); cursor = db.execute("UPDATE user_feedback SET status='resolved',reply=?,replied_time=CURRENT_TIMESTAMP,read_time=NULL WHERE id=? AND status='pending'", (reply, feedback_id)); db.commit(); db.close()
        if not cursor.rowcount: return fail('反馈不存在或已处理', 404)
        return ok(message='回复已送达')

    @app.route('/api/admin/content-reports/<int:report_id>', methods=['POST'])
    @admin_required_api
    def api_admin_content_report(user, report_id):
        action = payload().get('action')
        if action not in ('dismiss', 'remove'):
            return fail('无效处理操作')
        db = get_db(); report = db.execute("SELECT * FROM community_content_report WHERE id=? AND status='pending'", (report_id,)).fetchone()
        if not report: db.close(); return fail('举报不存在或已处理', 404)
        if action == 'remove':
            if report['target_type'] == 'post':
                db.execute('DELETE FROM post_like WHERE post_id=?', (report['target_id'],)); db.execute('DELETE FROM post_comment WHERE post_id=?', (report['target_id'],)); db.execute('DELETE FROM post WHERE id=?', (report['target_id'],))
            else:
                db.execute('UPDATE post_comment SET is_deleted=1,content="" WHERE id=?', (report['target_id'],))
        db.execute("UPDATE community_content_report SET status=? WHERE id=?", ('resolved' if action == 'remove' else 'dismissed', report_id)); db.commit(); db.close()
        return ok(message='举报已处理')

    @app.route('/api/admin/reviews/photo/<int:submission_id>', methods=['POST'])
    @admin_required_api
    def api_review_photo(user, submission_id):
        action = payload().get('action')
        if action not in ('approve','reject'): return fail('无效审核操作')
        db=get_db(); row=db.execute('SELECT * FROM dish_image_submission WHERE id=? AND status="pending"',(submission_id,)).fetchone()
        if not row: db.close(); return fail('投稿不存在或已处理',404)
        db.execute('UPDATE dish_image_submission SET status=? WHERE id=?',(action,submission_id))
        if action=='approve':
            reward = 8 if row['dish_id'] and not db.execute("SELECT 1 FROM dish_image_submission WHERE dish_id=? AND status='approve' AND id!=?",(row['dish_id'],submission_id)).fetchone() else 2
            if row['dish_id']: db.execute('UPDATE dish SET image_url=? WHERE id=?',(row['image_path'],row['dish_id']))
            db.execute('UPDATE user SET checkin_points=checkin_points+? WHERE id=?',(reward,row['user_id']))
        db.commit(); db.close(); return ok(message='审核完成')

    @app.route('/api/admin/reviews/report/<int:report_id>', methods=['POST'])
    @admin_required_api
    def api_review_report(user, report_id):
        action=payload().get('action')
        if action not in ('approve','reject'): return fail('无效审核操作')
        db=get_db(); cursor=db.execute("UPDATE new_dish_report SET status=? WHERE id=? AND status='pending'",(action,report_id)); db.commit(); db.close()
        if not cursor.rowcount: return fail('情报不存在或已处理',404)
        return ok(message='情报已处理')

    @app.route('/api/admin/dishes')
    @admin_required_api
    def api_admin_dishes(user):
        q = request.args.get('q', '').strip()
        db = get_db()
        rows = db.execute('SELECT d.*,s.name stall_name,c.name canteen_name FROM dish d JOIN stall s ON s.id=d.stall_id JOIN canteen c ON c.id=s.canteen_id WHERE d.name LIKE ? ORDER BY d.name LIMIT 30', (f'%{q}%',)).fetchall()
        db.close()
        return ok([dish_json(x) for x in rows])

    @app.route('/api/admin/dishes/<int:dish_id>/price', methods=['POST'])
    @admin_required_api
    def api_admin_dish_price(user, dish_id):
        data = payload()
        try:
            price = float(data.get('price'))
        except (TypeError, ValueError):
            return fail('请输入有效价格')
        if price <= 0 or price > 1000:
            return fail('价格应在 0-1000 元之间')
        db = get_db()
        if not db.execute('SELECT 1 FROM dish WHERE id=?', (dish_id,)).fetchone():
            db.close(); return fail('菜品不存在', 404)
        db.execute('UPDATE dish SET price=? WHERE id=?', (price, dish_id))
        db.commit(); db.close()
        return ok(message='菜品价格已更新')

    @app.route('/api/admin/dishes/<int:dish_id>/special', methods=['POST'])
    @admin_required_api
    def api_admin_dish_special(user, dish_id):
        data=payload(); action=data.get('action','set')
        db=get_db()
        if not db.execute('SELECT 1 FROM dish WHERE id=?',(dish_id,)).fetchone(): db.close(); return fail('菜品不存在',404)
        if action=='clear': db.execute('UPDATE dish SET special_price=NULL WHERE id=?',(dish_id,))
        else:
            try: price=float(data.get('price'))
            except (TypeError,ValueError): db.close(); return fail('请输入有效特价')
            if price<=0 or price>1000: db.close(); return fail('特价应在 0-1000 元之间')
            db.execute('UPDATE dish SET special_price=? WHERE id=?',(price,dish_id))
        db.commit(); db.close(); return ok(message='特价已更新')

    @app.route('/api/admin/posts/<int:post_id>', methods=['DELETE'])
    @admin_required_api
    def api_admin_delete_post(user, post_id):
        db = get_db()
        db.execute('DELETE FROM post_like WHERE post_id=?', (post_id,))
        db.execute('DELETE FROM post_comment WHERE post_id=?', (post_id,))
        cursor = db.execute('DELETE FROM post WHERE id=?', (post_id,))
        db.commit(); db.close()
        if not cursor.rowcount:
            return fail('帖子不存在', 404)
        return ok(message='帖子已删除')

    @app.route('/api/admin/comments/<string:source>/<int:comment_id>', methods=['DELETE'])
    @admin_required_api
    def api_admin_delete_comment(user, source, comment_id):
        table = 'comment' if source == 'dish' else ('post_comment' if source == 'post' else None)
        if not table:
            return fail('无效的评论类型')
        db = get_db(); cursor = db.execute(f'DELETE FROM {table} WHERE id=?', (comment_id,)); db.commit(); db.close()
        if not cursor.rowcount:
            return fail('评论不存在', 404)
        return ok(message='评论已删除')

    @app.route('/api/feedback', methods=['POST'])
    @login_required_api
    def api_feedback(user):
        data = payload(); content, text_error = validate_user_text(data.get('content') or '', '来信内容', 2, 1000); feedback_type = (data.get('feedbackType') or '建议').strip()
        if feedback_type not in ('建议', '问题', '想说的话'): feedback_type = '想说的话'
        if text_error: return fail(text_error)
        if safety_error := wechat_text_safety_error(content, user, 5): return fail(safety_error)
        db = get_db(); db.execute('INSERT INTO user_feedback (user_id,feedback_type,content) VALUES (?,?,?)', (user['id'], feedback_type, content)); db.commit(); db.close()
        return ok(message='收到啦，谢谢你愿意告诉我们')

    @app.route('/api/feedback/<int:feedback_id>/read', methods=['POST'])
    @login_required_api
    def api_feedback_read(user, feedback_id):
        db = get_db()
        cursor = db.execute("UPDATE user_feedback SET read_time=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND status='resolved' AND read_time IS NULL", (feedback_id, user['id']))
        db.commit(); db.close()
        return ok({'changed': bool(cursor.rowcount)})

    @app.route('/api/me')
    @login_required_api
    def api_me(user):
        db=get_db()
        photos=db.execute('SELECT id,dish_name,status,create_time FROM dish_image_submission WHERE user_id=? ORDER BY create_time DESC LIMIT 5',(user['id'],)).fetchall()
        reports=db.execute('SELECT id,dish_name,status,create_time FROM new_dish_report WHERE user_id=? ORDER BY create_time DESC LIMIT 5',(user['id'],)).fetchall()
        feedbacks=db.execute('SELECT id,feedback_type,content,status,reply,create_time,replied_time,read_time FROM user_feedback WHERE user_id=? ORDER BY create_time DESC LIMIT 10',(user['id'],)).fetchall()
        checkins=db.execute('SELECT meal_type,dish_ids,checkin_date,create_time FROM checkin WHERE user_id=? ORDER BY checkin_date DESC,create_time DESC LIMIT 8',(user['id'],)).fetchall()
        current_month = beijing_now().strftime('%Y-%m')
        month_checkins=db.execute("SELECT meal_type,dish_ids,checkin_date,create_time FROM checkin WHERE user_id=? AND strftime('%Y-%m', checkin_date)=? ORDER BY checkin_date DESC,create_time DESC",(user['id'],current_month)).fetchall()
        likes=db.execute('SELECT pl.create_time,u.nickname,p.id post_id,p.content FROM post_like pl JOIN post p ON p.id=pl.post_id JOIN user u ON u.id=pl.user_id WHERE p.user_id=? AND pl.user_id!=? ORDER BY pl.create_time DESC LIMIT 10',(user['id'],user['id'])).fetchall()
        notes=db.execute('SELECT pc.id comment_id,pc.content,pc.create_time,u.nickname,p.id post_id FROM post_comment pc JOIN post p ON p.id=pc.post_id JOIN user u ON u.id=pc.user_id LEFT JOIN post_comment parent ON parent.id=pc.parent_id WHERE (p.user_id=? OR parent.user_id=?) AND pc.user_id!=? ORDER BY pc.create_time DESC LIMIT 10',(user['id'],user['id'],user['id'])).fetchall()
        checkin_total = db.execute('SELECT COUNT(*) n FROM checkin WHERE user_id=?', (user['id'],)).fetchone()['n']
        photo_total = db.execute('SELECT COUNT(*) n FROM dish_image_submission WHERE user_id=? AND status="approve"', (user['id'],)).fetchone()['n']
        report_total = db.execute('SELECT COUNT(*) n FROM new_dish_report WHERE user_id=?', (user['id'],)).fetchone()['n']
        community_total = db.execute('SELECT (SELECT COUNT(*) FROM post WHERE user_id=?) + (SELECT COUNT(*) FROM post_comment WHERE user_id=? AND is_deleted=0) n', (user['id'], user['id'])).fetchone()['n']
        all_checkins = list(checkins) + list(month_checkins)
        dish_ids = {int(value) for row in all_checkins for value in (row['dish_ids'] or '').split(',') if value.isdigit()}
        dish_rows = db.execute(f"SELECT d.id,d.name,c.name canteen_name FROM dish d JOIN stall s ON s.id=d.stall_id JOIN canteen c ON c.id=s.canteen_id WHERE d.id IN ({','.join('?' for _ in dish_ids)})", tuple(dish_ids)).fetchall() if dish_ids else []
        dishes = {row['id']: row['name'] for row in dish_rows}
        dish_canteens = {row['id']: row['canteen_name'] for row in dish_rows}
        db.close()
        meal_labels = {'breakfast':'早餐','lunch':'午餐','dinner':'晚餐'}
        checkin_items = []
        for row in checkins:
            names = [dishes[int(value)] for value in (row['dish_ids'] or '').split(',') if value.isdigit() and int(value) in dishes]
            names.extend(value[7:] for value in (row['dish_ids'] or '').split(',') if value.startswith('custom:'))
            checkin_items.append({'mealType': row['meal_type'], 'mealLabel': meal_labels.get(row['meal_type'], '用餐'), 'dishText': '、'.join(names) or '这顿饭', 'checkinDate': row['checkin_date'], 'checkinTime': beijing_time(row['create_time'])})
        source_counts = {'食堂': 0, '外卖': 0, '聚餐': 0, '自定义': 0}
        canteen_counts = {}
        for row in month_checkins:
            values = (row['dish_ids'] or '').split(',')
            custom = next((value[7:] for value in values if value.startswith('custom:')), '')
            source = custom.split('：', 1)[0] if '：' in custom else ('自定义' if custom else '食堂')
            if source not in source_counts: source = '自定义'
            source_counts[source] += 1
            if source == '食堂':
                for canteen_name in {dish_canteens[int(value)] for value in values if value.isdigit() and int(value) in dish_canteens}:
                    canteen_counts[canteen_name] = canteen_counts.get(canteen_name, 0) + 1
        total_meals = len(month_checkins)
        source_stats = [{'key': key, 'label': key, 'count': source_counts[key], 'color': color} for key, color in (('食堂', '#c78a45'), ('外卖', '#d97c68'), ('聚餐', '#78a98a'), ('自定义', '#8d87b8')) if source_counts[key] or key != '自定义']
        canteen_stats = [{'name': name, 'count': count} for name, count in sorted(canteen_counts.items(), key=lambda item: (-item[1], item[0]))[:3]]
        meal_map = {'monthLabel': f'{int(current_month[5:])} 月', 'total': total_meals, 'sourceStats': source_stats, 'favoriteCanteen': canteen_stats[0]['name'] if canteen_stats else '', 'canteenStats': canteen_stats}
        feedback_items = [dict(x, createTime=beijing_time(x['create_time']), repliedTime=beijing_time(x['replied_time']), hasUnreadReply=bool(x['status'] == 'resolved' and x['reply'] and not x['read_time'])) for x in feedbacks]
        badges = []
        if checkin_total >= 1: badges.append({'id': 'first-meal', 'mark': '食', 'name': '第一顿饭', 'description': '留下第一条用餐记录'})
        if checkin_total >= 5: badges.append({'id': 'meal-journal', 'mark': '记', 'name': '食堂手帐', 'description': '累计打卡 5 顿'})
        if photo_total >= 1: badges.append({'id': 'real-photo', 'mark': '拍', 'name': '实拍食客', 'description': '有实拍图通过审核'})
        if report_total >= 1: badges.append({'id': 'new-scout', 'mark': '新', 'name': '上新观察员', 'description': '提交过一条上新情报'})
        if community_total >= 3: badges.append({'id': 'meal-pal', 'mark': '聊', 'name': '饭搭子', 'description': '分享过 3 条社区内容'})
        return ok({'user':user_json(user),'badges':badges,'photos':[dict(x, createTime=beijing_time(x['create_time'])) for x in photos],'reports':[dict(x, createTime=beijing_time(x['create_time'])) for x in reports],'feedbacks':feedback_items,'unreadFeedbackCount':sum(1 for x in feedback_items if x['hasUnreadReply']),'checkins':checkin_items,'mealMap':meal_map,'likes':[dict(x, createTime=beijing_time(x['create_time'])) for x in likes],'notifications':[dict(x, createTime=beijing_time(x['create_time'])) for x in notes]})


def user_json(user):
    avatar_id = user['avatar_url'] if user['avatar_url'] in ANONYMOUS_AVATARS else 'rice'
    nickname = user['nickname'] or user['username']
    return {'id': user['id'], 'username': user['username'], 'nickname': nickname, 'avatarId': avatar_id, 'avatarLabel': ANONYMOUS_AVATARS[avatar_id], 'profileCompleted': nickname != '微信用户', 'points': user['checkin_points'], 'isAdmin': bool(user['is_admin'])}
