"""PythonAnywhere 部署检查脚本，在 Bash 里运行: python3 check_setup.py"""
import os, sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

print("=== 路径检查 ===")
print(f"项目目录: {PROJECT_DIR}")

# 检查关键文件
checks = [
    ('static/images/dishes/category_images.json', '品类映射文件'),
    ('static/images/dishes/cat01_stirfry.jpg', 'cat01 图片'),
    ('static/images/dishes/cat16_dessert.jpg', 'cat16 图片'),
]
all_ok = True
for path, label in checks:
    full = os.path.join(PROJECT_DIR, path)
    exists = os.path.exists(full)
    status = '✓' if exists else '✗ 缺失!'
    if not exists:
        all_ok = False
    print(f"  [{status}] {label} -> {full}")

print()

# 检查数据库
import sqlite3
db_path = os.path.join(PROJECT_DIR, 'database.db')
print(f"数据库: {db_path}")
if not os.path.exists(db_path):
    print("  ✗ 数据库文件不存在!")
    sys.exit(1)

db = sqlite3.connect(db_path)
db.row_factory = sqlite3.Row

# 检查 category 列
cols = [c[1] for c in db.execute('PRAGMA table_info(dish)').fetchall()]
if 'category' in cols:
    null_count = db.execute(
        'SELECT COUNT(*) as n FROM dish WHERE category IS NULL OR category=""'
    ).fetchone()['n']
    total = db.execute('SELECT COUNT(*) as n FROM dish').fetchone()['n']
    print(f"  category 列存在, {total} 道菜, {null_count} 道无品类")
    if null_count > 0:
        print("  ✗ 需运行 fill_categories.py")
        all_ok = False
else:
    print("  ✗ category 列不存在! 需更新 schema")
    all_ok = False

# 检查映射文件内容
import json
try:
    json_path = os.path.join(PROJECT_DIR, 'static', 'images', 'dishes', 'category_images.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        cat_map = json.load(f)
    db_cats = set(r['category'] for r in db.execute(
        'SELECT DISTINCT category FROM dish WHERE category IS NOT NULL AND category!=""'
    ).fetchall())
    mapped = db_cats & set(cat_map.keys())
    unmapped = db_cats - set(cat_map.keys())
    print(f"\n品类映射: {len(mapped)} 匹配, {len(unmapped)} 无图")
    if unmapped:
        print(f"  无图的品类: {unmapped}")
        all_ok = False
except Exception as e:
    print(f"\n  ✗ 读取 category_images.json 失败: {e}")
    all_ok = False

# 检查时区
from datetime import datetime, timedelta
utc = datetime.utcnow()
bjt = utc + timedelta(hours=8)
print(f"\n服务器 UTC 时间: {utc.strftime('%H:%M')}")
print(f"推算北京时间: {bjt.strftime('%H:%M')}")
print(f"当前北京时间应接近: 约 {bjt.hour}:{bjt.minute}")

print(f"\n{'='*20}")
if all_ok:
    print("全部检查通过! 图片和时间应正常工作。如仍有问题请 Web -> Reload")
else:
    print("存在问题! 请根据上述 ✗ 项修复后重新上传")
