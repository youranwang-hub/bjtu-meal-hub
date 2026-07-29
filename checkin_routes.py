"""打卡路由：三餐打卡、个人主页"""
import random as _random
from datetime import timedelta
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from helpers import get_db, beijing_now


def init_app(app):
    @app.route('/checkin')
    @login_required
    def checkin():
        db = get_db()
        today = beijing_now().date().isoformat()
        today_checkins = db.execute(
            'SELECT * FROM checkin WHERE user_id = ? AND checkin_date = ?',
            (current_user.id, today)
        ).fetchall()
        done_meals = [c['meal_type'] for c in today_checkins]
        done_count = len(done_meals)
        if done_count == 3:
            encourage_status = 'full'
            encourage_msg = '太棒了！今天三餐都打卡了，认真生活的你闪闪发光'
        elif done_count >= 1:
            missing = {'breakfast': '早餐', 'lunch': '午餐', 'dinner': '晚餐'}
            left = [missing[m] for m in ['breakfast', 'lunch', 'dinner'] if m not in done_meals]
            encourage_status = 'half'
            encourage_msg = f'还差{"、".join(left)}就满勤啦，继续加油！'
        else:
            encourage_status = 'none'
            encourage_msg = '新的一天，从记录早餐开始吧！'
        quotes = [
            '吃好喝好，长生不老。有菜有肉，健康长寿。',
            '周一周五吃苦，周末大补特补。',
            '睡前一定要吃饱，不然会做"饿"梦哦！',
            '世界这么大，我们去吃吃看。',
            '吃得多想得少，天天开心没烦恼。',
            '人生苦短，好好吃饭。',
            '肚子胖胖，生活旺旺。',
            '三观很重要，但三餐更重要。',
            '这辈子最放不下的就是筷子！',
            '只要碗里是满的，人生就不会空虚。',
        ]
        random_quote = _random.choice(quotes)
        first_day = beijing_now().date().replace(day=1)
        start_weekday = (first_day.weekday() + 1) % 7
        cal_data = []
        for _ in range(start_weekday):
            cal_data.append({'day': '', 'date': '', 'count': 0})
        d = first_day
        while d.month == first_day.month:
            cnt = db.execute(
                'SELECT COUNT(*) as n FROM checkin WHERE user_id = ? AND checkin_date = ?',
                (current_user.id, d.isoformat())
            ).fetchone()['n']
            cal_data.append({'day': d.day, 'date': d.isoformat(), 'count': cnt})
            d += timedelta(days=1)
        leaderboard = db.execute(
            'SELECT username, nickname, checkin_points FROM user '
            'ORDER BY checkin_points DESC LIMIT 10'
        ).fetchall()
        db.close()
        return render_template('checkin.html', done_meals=done_meals, cal_data=cal_data,
                               leaderboard=leaderboard, today=today,
                               encourage_status=encourage_status, encourage_msg=encourage_msg,
                               random_quote=random_quote)

    @app.route('/checkin/submit', methods=['POST'])
    @login_required
    def submit_checkin():
        meal_type = request.form.get('meal_type', '').strip()
        dish_ids = ','.join(request.form.getlist('dish_ids'))
        if not meal_type or meal_type not in ('breakfast', 'lunch', 'dinner'):
            flash('请选择餐次', 'danger')
            return redirect(url_for('checkin'))
        if not dish_ids:
            flash('请至少选择一道菜品', 'danger')
            return redirect(url_for('checkin'))
        today = beijing_now().date().isoformat()
        db = get_db()
        existing = db.execute(
            'SELECT id FROM checkin WHERE user_id = ? AND checkin_date = ? AND meal_type = ?',
            (current_user.id, today, meal_type)
        ).fetchone()
        if existing:
            db.close()
            flash('今天该餐次已打卡', 'warning')
            return redirect(url_for('checkin'))
        db.execute(
            'INSERT INTO checkin (user_id, meal_type, dish_ids, checkin_date) VALUES (?,?,?,?)',
            (current_user.id, meal_type, dish_ids, today))
        points_add = 3 if meal_type == 'breakfast' else 2
        db.execute(
            'UPDATE user SET checkin_points = checkin_points + ? WHERE id = ?',
            (points_add, current_user.id))
        db.commit()
        row = db.execute('SELECT checkin_points FROM user WHERE id = ?', (current_user.id,)).fetchone()
        current_user.checkin_points = row['checkin_points']
        db.close()
        flash(f'打卡成功！+{points_add} 积分', 'success')
        return redirect(url_for('checkin'))

    @app.route('/profile')
    @login_required
    def profile():
        db = get_db()
        ratings = db.execute(
            'SELECT r.*, d.name as dish_name FROM rating r '
            'JOIN dish d ON r.dish_id = d.id WHERE r.user_id = ? '
            'ORDER BY r.create_time DESC LIMIT 10',
            (current_user.id,)
        ).fetchall()
        comments = db.execute(
            'SELECT c.*, d.name as dish_name FROM comment c '
            'JOIN dish d ON c.dish_id = d.id WHERE c.user_id = ? '
            'ORDER BY c.create_time DESC LIMIT 10',
            (current_user.id,)
        ).fetchall()
        posts = db.execute(
            'SELECT * FROM post WHERE user_id = ? ORDER BY create_time DESC',
            (current_user.id,)
        ).fetchall()
        checkins = db.execute(
            'SELECT * FROM checkin WHERE user_id = ? ORDER BY checkin_date DESC, create_time DESC LIMIT 20',
            (current_user.id,)
        ).fetchall()
        db.close()
        return render_template('profile.html', ratings=ratings, comments=comments,
                               posts=posts, checkins=checkins)
