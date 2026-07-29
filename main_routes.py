"""主路由：首页、搜索、食堂/档口/菜品浏览、评分、评论、API"""
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from helpers import get_db, beijing_now, get_crowd_status, PER_PAGE


def init_app(app):
    @app.route('/')
    def index():
        db = get_db()
        canteens_raw = db.execute('SELECT * FROM canteen ORDER BY id').fetchall()
        crowd = get_crowd_status()
        canteens = []
        for c in canteens_raw:
            c = dict(c)
            c['crowd_status'] = crowd
            canteens.append(c)
        new_dishes = db.execute(
            "SELECT dish.*, stall.name as stall_name, canteen.name as canteen_name "
            "FROM dish JOIN stall ON dish.stall_id = stall.id "
            "JOIN canteen ON stall.canteen_id = canteen.id "
            "WHERE dish.is_new = 1 ORDER BY dish.create_time DESC LIMIT 6"
        ).fetchall()
        recommended = db.execute(
            "SELECT d.*, s.name as stall_name, c.name as canteen_name, "
            "(SELECT COUNT(*) FROM rating WHERE dish_id = d.id) as rate_count "
            "FROM dish d JOIN stall s ON d.stall_id = s.id "
            "JOIN canteen c ON s.canteen_id = c.id "
            "WHERE d.average_rating >= 4.0 AND rate_count >= 1 "
            "ORDER BY d.average_rating * rate_count DESC LIMIT 6"
        ).fetchall()
        if len(recommended) < 6:
            new_fill = db.execute(
                "SELECT d.*, s.name as stall_name, c.name as canteen_name "
                "FROM dish d JOIN stall s ON d.stall_id = s.id "
                "JOIN canteen c ON s.canteen_id = c.id "
                "WHERE d.is_new = 1 ORDER BY d.create_time DESC LIMIT ?",
                (6 - len(recommended),)
            ).fetchall()
            recommended = list(recommended) + list(new_fill)
        hot_dishes = db.execute(
            "SELECT d.*, s.name as stall_name, c.name as canteen_name "
            "FROM dish d JOIN stall s ON d.stall_id = s.id "
            "JOIN canteen c ON s.canteen_id = c.id "
            "ORDER BY d.average_rating DESC LIMIT 5"
        ).fetchall()
        special_dishes = db.execute(
            "SELECT d.*, s.name as stall_name, c.name as canteen_name "
            "FROM dish d JOIN stall s ON d.stall_id = s.id "
            "JOIN canteen c ON s.canteen_id = c.id "
            "WHERE d.special_price IS NOT NULL ORDER BY d.name LIMIT 8"
        ).fetchall()
        now = beijing_now()
        t = now.hour * 60 + now.minute
        if 390 <= t < 510:
            meal_hint = '早餐时间！来碗热粥暖暖胃'
        elif 660 <= t < 780:
            meal_hint = '午餐时间！食堂正热闹'
        elif 1020 <= t < 1140:
            meal_hint = '晚餐时间！一天辛苦了好好吃一顿'
        else:
            meal_hint = None
        db.close()
        return render_template('index.html', canteens=canteens, new_dishes=new_dishes,
                               recommended=recommended, hot_dishes=hot_dishes,
                               special_dishes=special_dishes, meal_hint=meal_hint)

    @app.route('/search')
    def search():
        q = request.args.get('q', '')
        if not q:
            return redirect(url_for('index'))
        page = request.args.get('page', 1, type=int)
        if page < 1:
            page = 1
        db = get_db()
        total_count = db.execute(
            "SELECT COUNT(*) as n FROM dish d JOIN stall s ON d.stall_id = s.id "
            "JOIN canteen c ON s.canteen_id = c.id "
            "WHERE d.name LIKE ? OR d.tags LIKE ? OR s.name LIKE ?",
            (f'%{q}%', f'%{q}%', f'%{q}%')
        ).fetchone()['n']
        total_pages = max(1, (total_count + PER_PAGE - 1) // PER_PAGE)
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * PER_PAGE
        dishes = db.execute(
            "SELECT d.*, s.name as stall_name, c.name as canteen_name "
            "FROM dish d JOIN stall s ON d.stall_id = s.id "
            "JOIN canteen c ON s.canteen_id = c.id "
            "WHERE d.name LIKE ? OR d.tags LIKE ? OR s.name LIKE ? "
            "ORDER BY d.average_rating DESC LIMIT ? OFFSET ?",
            (f'%{q}%', f'%{q}%', f'%{q}%', PER_PAGE, offset)
        ).fetchall()
        db.close()
        return render_template('index.html', dishes=dishes, query=q, search_mode=True,
                               page=page, total_pages=total_pages)

    @app.route('/canteen/<int:canteen_id>')
    def canteen(canteen_id):
        db = get_db()
        canteen_row = db.execute('SELECT * FROM canteen WHERE id = ?', (canteen_id,)).fetchone()
        if not canteen_row:
            db.close()
            return '食堂不存在', 404
        canteen = dict(canteen_row)
        canteen['crowd_status'] = get_crowd_status()
        stalls = db.execute(
            'SELECT s.*, COUNT(d.id) as dish_count '
            'FROM stall s LEFT JOIN dish d ON s.id = d.stall_id '
            'WHERE s.canteen_id = ? GROUP BY s.id ORDER BY s.id',
            (canteen_id,)
        ).fetchall()
        db.close()
        return render_template('canteen.html', canteen=canteen, stalls=stalls)

    @app.route('/stall/<int:stall_id>')
    def stall(stall_id):
        db = get_db()
        stall = db.execute(
            'SELECT s.*, c.name as canteen_name, c.id as canteen_id FROM stall s '
            'JOIN canteen c ON s.canteen_id = c.id WHERE s.id = ?', (stall_id,)
        ).fetchone()
        if not stall:
            db.close()
            return '档口不存在', 404
        dishes = db.execute(
            'SELECT * FROM dish WHERE stall_id = ? ORDER BY is_new DESC, id', (stall_id,)
        ).fetchall()
        db.close()
        return render_template('stall.html', stall=stall, dishes=dishes)

    @app.route('/dish/<int:dish_id>')
    def dish(dish_id):
        db = get_db()
        dish = db.execute(
            'SELECT d.*, s.name as stall_name, s.id as stall_id, '
            'c.name as canteen_name, c.id as canteen_id '
            'FROM dish d JOIN stall s ON d.stall_id = s.id '
            'JOIN canteen c ON s.canteen_id = c.id '
            'WHERE d.id = ?', (dish_id,)
        ).fetchone()
        if not dish:
            db.close()
            return '菜品不存在', 404
        user_rating = None
        if current_user.is_authenticated:
            user_rating = db.execute(
                'SELECT score FROM rating WHERE user_id = ? AND dish_id = ?',
                (current_user.id, dish_id)
            ).fetchone()
        comments = db.execute(
            'SELECT c.*, u.nickname, u.avatar_url FROM comment c '
            'JOIN user u ON c.user_id = u.id '
            'WHERE c.dish_id = ? ORDER BY c.create_time DESC',
            (dish_id,)
        ).fetchall()
        db.close()
        return render_template('dish.html', dish=dish, comments=comments,
                               user_rating=user_rating['score'] if user_rating else 0)

    @app.route('/dish/<int:dish_id>/rate', methods=['POST'])
    @login_required
    def rate_dish(dish_id):
        score = request.form.get('score', type=int)
        if not score or score < 1 or score > 5:
            flash('请选择 1-5 分', 'danger')
            return redirect(url_for('dish', dish_id=dish_id))
        db = get_db()
        db.execute(
            'INSERT INTO rating (user_id, dish_id, score) VALUES (?,?,?) '
            'ON CONFLICT(user_id, dish_id) DO UPDATE SET score = ?, create_time = CURRENT_TIMESTAMP',
            (current_user.id, dish_id, score, score))
        db.commit()
        avg = db.execute(
            'SELECT ROUND(AVG(score), 1) as avg FROM rating WHERE dish_id = ?', (dish_id,)
        ).fetchone()
        db.execute('UPDATE dish SET average_rating = ? WHERE id = ?', (avg['avg'] or 0, dish_id))
        db.commit()
        db.close()
        flash('评分成功！', 'success')
        return redirect(url_for('dish', dish_id=dish_id))

    @app.route('/dish/<int:dish_id>/comment', methods=['POST'])
    @login_required
    def comment_dish(dish_id):
        content = request.form.get('content', '').strip()
        if not content:
            flash('评论内容不能为空', 'danger')
            return redirect(url_for('dish', dish_id=dish_id))
        if len(content) > 500:
            flash('评论不能超过 500 字', 'danger')
            return redirect(url_for('dish', dish_id=dish_id))
        db = get_db()
        db.execute(
            'INSERT INTO comment (user_id, dish_id, content) VALUES (?,?,?)',
            (current_user.id, dish_id, content))
        db.commit()
        db.close()
        flash('评论发表成功！', 'success')
        return redirect(url_for('dish', dish_id=dish_id))

    @app.route('/comment/<int:comment_id>/delete', methods=['POST'])
    @login_required
    def delete_comment(comment_id):
        db = get_db()
        comment = db.execute('SELECT * FROM comment WHERE id = ?', (comment_id,)).fetchone()
        if not comment:
            db.close()
            flash('评论不存在', 'danger')
            return redirect(url_for('index'))
        if comment['user_id'] != current_user.id and not current_user.is_admin:
            db.close()
            flash('无权删除此评论', 'danger')
            return redirect(url_for('index'))
        dish_id = comment['dish_id']
        db.execute('DELETE FROM comment WHERE id = ?', (comment_id,))
        db.commit()
        db.close()
        flash('评论已删除', 'info')
        return redirect(url_for('dish', dish_id=dish_id))

    @app.route('/api/dishes/search')
    def api_dish_search():
        q = request.args.get('q', '').strip()
        if not q or len(q) < 1:
            return {'dishes': []}
        db = get_db()
        dishes = db.execute(
            "SELECT id, name, price, (SELECT name FROM stall WHERE id=dish.stall_id) as stall_name "
            "FROM dish WHERE name LIKE ? ORDER BY name LIMIT 8",
            (f'%{q}%',)
        ).fetchall()
        db.close()
        return {'dishes': [{'id': d['id'], 'name': d['name'], 'price': d['price'],
                'stall_name': d['stall_name']} for d in dishes]}
