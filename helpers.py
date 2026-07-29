"""共享工具函数和常量"""
import sqlite3
import os
import json as _json
from datetime import datetime, timedelta, timezone as _tz
from flask import session
from flask_login import UserMixin
import secrets

BJ_TZ = _tz(timedelta(hours=8))
DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
PER_PAGE = 20

CATEGORY_IMAGES_PATH = os.path.join(os.path.dirname(__file__), 'static', 'images', 'dishes', 'category_images.json')
CATEGORY_IMAGES = {}
try:
    with open(CATEGORY_IMAGES_PATH, 'r', encoding='utf-8') as f:
        CATEGORY_IMAGES = _json.load(f)
except Exception:
    pass


def beijing_now():
    return datetime.now(BJ_TZ).replace(tzinfo=None)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def relative_time(dt_str):
    if not dt_str:
        return ''
    try:
        dt = datetime.strptime(dt_str[:19], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return dt_str[:16]
    now = beijing_now()
    diff = now - dt
    if diff < timedelta(minutes=1):
        return '刚刚'
    elif diff < timedelta(hours=1):
        return f'{diff.seconds // 60} 分钟前'
    elif diff < timedelta(hours=3):
        return f'{diff.seconds // 3600} 小时前'
    elif dt.date() == now.date():
        return f'今天 {dt.strftime("%H:%M")}'
    elif dt.date() == (now - timedelta(days=1)).date():
        return f'昨天 {dt.strftime("%H:%M")}'
    elif diff < timedelta(days=7):
        return f'{diff.days} 天前'
    else:
        return dt.strftime('%m-%d %H:%M')


CATEGORY_PARENT = {
    '汤面': '面食', '拌面炒面': '面食', '饼类': '面食',
    '川湘小炒': '家常小炒', '清淡小炒': '家常小炒', '砂锅煲类': '家常小炒',
    '蒸品点心': '早餐', '汤粥': '早餐',
    '炸物': '西式快餐', '汉堡三明治': '西式快餐', '炸鸡': '西式快餐',
    '轻食沙拉': '套餐',
    '烧腊卤味': '凉菜卤味',
    '特色米饭': '盖浇饭',
}


def _resolve_category_image(cat):
    """返回品类对应的图片路径，文件必须存在；子品类不存在时回退到父类"""
    if not cat:
        return None
    # 先试自身
    if cat in CATEGORY_IMAGES:
        path = 'images/dishes/' + CATEGORY_IMAGES[cat]
        full = os.path.join(os.path.dirname(__file__), 'static', path)
        if os.path.exists(full):
            return path
    # 回退父类
    parent = CATEGORY_PARENT.get(cat)
    if parent:
        return _resolve_category_image(parent)
    return None


def get_dish_image(dish):
    if dish is None:
        return None
    try:
        img = dish['image_url'] if 'image_url' in dish.keys() else None
        cat = dish['category'] if 'category' in dish.keys() else None
    except TypeError:
        img = dish.get('image_url', None) if hasattr(dish, 'get') else None
        cat = dish.get('category', None) if hasattr(dish, 'get') else None
    if img:
        full = os.path.join(os.path.dirname(__file__), 'static', img)
        if os.path.exists(full):
            return img
    return _resolve_category_image(cat)


def get_crowd_status():
    t = beijing_now().time()
    crowded = [(11, 30, 12, 30), (18, 0, 18, 30)]
    for sh, sm, eh, em in crowded:
        if (t.hour > sh or (t.hour == sh and t.minute >= sm)) and \
           (t.hour < eh or (t.hour == eh and t.minute <= em)):
            return '拥挤'
    moderate = [(7, 30, 8, 0), (11, 0, 11, 30), (12, 30, 13, 0),
                (17, 30, 18, 0), (18, 30, 19, 0)]
    for sh, sm, eh, em in moderate:
        if (t.hour > sh or (t.hour == sh and t.minute >= sm)) and \
           (t.hour < eh or (t.hour == eh and t.minute <= em)):
            return '适中'
    return '空闲'


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


class User(UserMixin):
    def __init__(self, row):
        self.id = row['id']
        self.username = row['username']
        self.nickname = row['nickname']
        self.avatar_url = row['avatar_url']
        self.checkin_points = row['checkin_points']
        self.is_admin = row['is_admin'] if 'is_admin' in row.keys() else 0

    def get_id(self):
        return str(self.id)


def load_user(user_id):
    db = get_db()
    row = db.execute('SELECT * FROM user WHERE id = ?', (int(user_id),)).fetchone()
    db.close()
    return User(row) if row else None
