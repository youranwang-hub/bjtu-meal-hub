"""根据档口名称自动填充菜品品类"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

# 档口→品类映射（按关键词优先级匹配）
# 子品类（如"汤面"）图片不存在时，get_dish_image() 自动回退到父类（如"面食"）
# 两周后你只需把图片文件放进 static/images/dishes/，子品类即刻生效
STALL_KEYWORDS = [
    # (关键词, 品类) — 先匹配到的生效
    # === 面食: 汤面 / 拌面炒面 / 饼类 / 面食 ===
    ('重庆小面', '汤面'),
    ('重庆面庄', '汤面'),
    ('亲爱的面', '汤面'),
    ('一碗好面', '汤面'),
    ('牛肉刀削面', '汤面'),
    ('牛肉汤', '汤面'),
    ('焖面', '汤面'),
    ('西北味道', '汤面'),
    ('炒色炒香', '拌面炒面'),
    ('锅盔', '饼类'),
    ('掉渣饼', '饼类'),
    # === 家常小炒: 川湘小炒 / 清淡小炒 / 砂锅煲类 / 家常小炒 ===
    ('川湘', '川湘小炒'),
    ('四川味道', '川湘小炒'),
    ('重庆味道', '川湘小炒'),
    ('湖南小炒', '川湘小炒'),
    ('江南味道', '清淡小炒'),
    ('南北味道', '清淡小炒'),
    ('广式味道', '清淡小炒'),
    ('瓦罐汤', '砂锅煲类'),
    ('煨养砂锅', '砂锅煲类'),
    ('私房小灶', '家常小炒'),
    ('烤盘饭', '家常小炒'),
    ('小炒', '家常小炒'),
    # === 西式快餐: 汉堡三明治 / 炸鸡 / 西式快餐 ===
    ('汉堡', '汉堡三明治'),
    ('炸鸡', '炸鸡'),
    ('西餐', '西式快餐'),
    ('西式', '西式快餐'),
    ('土耳其', '西式快餐'),
    ('俄餐', '西式快餐'),
    # === 早餐: 蒸品点心 / 汤粥 / 早餐 ===
    ('小笼包', '蒸品点心'),
    ('煎饼', '蒸品点心'),
    ('早餐', '早餐'),
    ('主食厨房', '早餐'),
    ('主食档', '早餐'),
    ('主食组合', '早餐'),
    ('烤制主食', '早餐'),
    ('煎制主食', '早餐'),
    ('面点主食', '早餐'),
    # === 凉菜卤味: 烧腊卤味 / 凉菜卤味 ===
    ('烧腊', '烧腊卤味'),
    ('匠心卤', '烧腊卤味'),
    ('卤味', '凉菜卤味'),
    ('卤', '凉菜卤味'),
    # === 米饭/盖浇类: 特色米饭 / 盖浇饭 ===
    ('鲍汁', '特色米饭'),
    ('鸡饭', '特色米饭'),
    ('卤肉饭', '盖浇饭'),
    ('滑蛋饭', '盖浇饭'),
    ('蒸饭', '盖浇饭'),
    ('腊饭', '盖浇饭'),
    ('捞饭', '盖浇饭'),
    ('小炒盖饭', '盖浇饭'),
    ('礼二府', '盖浇饭'),
    ('友客来', '盖浇饭'),
    ('盖饭', '盖浇饭'),
    # === 套餐: 轻食沙拉 / 套餐 ===
    ('轻食套餐', '轻食沙拉'),
    ('减脂餐', '轻食沙拉'),
    ('清养膳食', '套餐'),
    ('轻养膳食', '套餐'),
    # === 其余保持不变 ===
    ('铁板', '铁板烧'),
    ('板烧饭', '铁板烧'),
    ('麻辣烫', '麻辣烫/拌'),
    ('麻辣拌', '麻辣烫/拌'),
    ('冒菜', '麻辣烫/拌'),
    ('饺香', '饺子'),
    ('水饺', '饺子'),
    ('饺子', '饺子'),
    ('南昌拌粉', '米线/粉'),
    ('牛肉粉面', '米线/粉'),
    ('烤冷面', '面食'),
    ('炸串', '烧烤'),
    ('炙烤', '烧烤'),
    ('烧烤', '烧烤'),
    ('水吧', '饮品'),
    ('饮品', '饮品'),
    ('冷饮', '饮品'),
    ('热饮', '饮品'),
    ('鲜果路', '饮品'),
    ('主食饮品档口', '饮品'),
    ('甜品', '甜品'),
]


def match_category(stall_name):
    """根据档口名关键词匹配品类"""
    if not stall_name:
        return ''
    for keyword, category in STALL_KEYWORDS:
        if keyword in stall_name:
            return category
    return ''


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 确保有 category 列
    try:
        cursor.execute('ALTER TABLE dish ADD COLUMN category TEXT')
        print('已添加 category 列')
    except sqlite3.OperationalError:
        pass

    # 获取所有菜品及其档口名
    dishes = cursor.execute(
        'SELECT d.id, d.name, s.name as stall_name FROM dish d '
        'JOIN stall s ON d.stall_id = s.id'
    ).fetchall()

    updated = 0
    skipped = []
    for dish_id, dish_name, stall_name in dishes:
        cat = match_category(stall_name)
        if cat:
            cursor.execute('UPDATE dish SET category = ? WHERE id = ?', (cat, dish_id))
            updated += 1
        else:
            skipped.append(f'{dish_id}: {dish_name} ({stall_name})')

    conn.commit()

    # 统计
    stats = cursor.execute(
        'SELECT category, COUNT(*) FROM dish GROUP BY category ORDER BY COUNT(*) DESC'
    ).fetchall()
    total = cursor.execute('SELECT COUNT(*) FROM dish').fetchone()[0]

    print(f'共 {total} 道菜品，已填充 {updated} 道\n')
    print('品类分布:')
    for cat, cnt in stats:
        print(f'  {cat or "(空)":12s} {cnt:3d} 道')

    if skipped:
        # 写入文件避免编码问题
        with open('_unmatched.txt', 'w', encoding='utf-8') as f:
            f.write(f'未匹配 {len(skipped)} 道:\n')
            for s in skipped:
                f.write(f'  {s}\n')
        print(f'\n未匹配 {len(skipped)} 道，详见 _unmatched.txt')
    conn.close()
    print('完成！')


if __name__ == '__main__':
    main()
