"""管理后台路由"""
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from helpers import get_db


def init_app(app):
    @app.route('/admin')
    @login_required
    def admin():
        if not current_user.is_admin:
            flash('无管理员权限', 'danger')
            return redirect(url_for('index'))
        db = get_db()
        stats = {
            'user_count': db.execute('SELECT COUNT(*) as n FROM user').fetchone()['n'],
            'dish_count': db.execute('SELECT COUNT(*) as n FROM dish').fetchone()['n'],
            'post_count': db.execute('SELECT COUNT(*) as n FROM post').fetchone()['n'],
            'rating_count': db.execute('SELECT COUNT(*) as n FROM rating').fetchone()['n'],
            'comment_count': db.execute('SELECT COUNT(*) as n FROM comment').fetchone()['n'],
            'checkin_count': db.execute('SELECT COUNT(*) as n FROM checkin').fetchone()['n'],
        }
        users = db.execute(
            'SELECT id, username, nickname, is_admin, checkin_points, create_time '
            'FROM user ORDER BY id'
        ).fetchall()
        recent_posts = db.execute(
            'SELECT p.*, u.nickname FROM post p JOIN user u ON p.user_id = u.id '
            'ORDER BY p.create_time DESC LIMIT 20'
        ).fetchall()
        recent_checkins = db.execute(
            'SELECT c.*, u.nickname FROM checkin c JOIN user u ON c.user_id = u.id '
            'ORDER BY c.create_time DESC LIMIT 20'
        ).fetchall()
        recent_ratings = db.execute(
            'SELECT r.*, u.nickname, d.name as dish_name FROM rating r '
            'JOIN user u ON r.user_id = u.id '
            'JOIN dish d ON r.dish_id = d.id '
            'ORDER BY r.create_time DESC LIMIT 20'
        ).fetchall()
        recent_comments = db.execute(
            'SELECT c.*, u.nickname, d.name as dish_name FROM comment c '
            'JOIN user u ON c.user_id = u.id '
            'JOIN dish d ON c.dish_id = d.id '
            'ORDER BY c.create_time DESC LIMIT 20'
        ).fetchall()
        dishes = db.execute(
            'SELECT d.*, s.name as stall_name, c.name as canteen_name '
            'FROM dish d JOIN stall s ON d.stall_id = s.id '
            'JOIN canteen c ON s.canteen_id = c.id '
            'ORDER BY CASE WHEN d.special_price IS NOT NULL THEN 0 ELSE 1 END, d.is_new DESC, d.name'
        ).fetchall()
        db.close()
        return render_template('admin.html', stats=stats, users=users,
                               recent_posts=recent_posts, recent_checkins=recent_checkins,
                               recent_comments=recent_comments, recent_ratings=recent_ratings,
                               all_dishes=dishes)

    @app.route('/admin/user/<int:user_id>')
    @login_required
    def admin_user_detail(user_id):
        if not current_user.is_admin:
            flash('无管理员权限', 'danger')
            return redirect(url_for('index'))
        db = get_db()
        user = db.execute('SELECT * FROM user WHERE id = ?', (user_id,)).fetchone()
        if not user:
            db.close()
            return '用户不存在', 404
        ratings = db.execute(
            'SELECT r.*, d.name as dish_name FROM rating r '
            'JOIN dish d ON r.dish_id = d.id WHERE r.user_id = ? '
            'ORDER BY r.create_time DESC', (user_id,)
        ).fetchall()
        comments = db.execute(
            'SELECT c.*, d.name as dish_name FROM comment c '
            'JOIN dish d ON c.dish_id = d.id WHERE c.user_id = ? '
            'ORDER BY c.create_time DESC', (user_id,)
        ).fetchall()
        posts = db.execute(
            'SELECT * FROM post WHERE user_id = ? ORDER BY create_time DESC', (user_id,)
        ).fetchall()
        checkins = db.execute(
            'SELECT * FROM checkin WHERE user_id = ? ORDER BY checkin_date DESC', (user_id,)
        ).fetchall()
        db.close()
        return render_template('admin_user.html', user=user, ratings=ratings,
                               comments=comments, posts=posts, checkins=checkins)

    @app.route('/admin/dish/<int:dish_id>/special', methods=['POST'])
    @login_required
    def admin_special_dish(dish_id):
        if not current_user.is_admin:
            flash('无管理员权限', 'danger')
            return redirect(url_for('index'))
        action = request.form.get('action', 'set')
        db = get_db()
        if action == 'set':
            price = request.form.get('price', '').strip()
            try:
                price_val = float(price)
                if price_val <= 0:
                    raise ValueError
            except ValueError:
                db.close()
                flash('请输入有效的价格', 'danger')
                return redirect(url_for('admin'))
            db.execute('UPDATE dish SET special_price = ? WHERE id = ?', (price_val, dish_id))
            flash('特价已设置', 'success')
        else:
            db.execute('UPDATE dish SET special_price = NULL WHERE id = ?', (dish_id,))
            flash('已取消特价', 'info')
        db.commit()
        db.close()
        return redirect(url_for('admin'))

    @app.route('/admin/post/<int:post_id>/delete', methods=['POST'])
    @login_required
    def admin_delete_post(post_id):
        if not current_user.is_admin:
            flash('无管理员权限', 'danger')
            return redirect(url_for('index'))
        db = get_db()
        db.execute('DELETE FROM post_like WHERE post_id = ?', (post_id,))
        db.execute('DELETE FROM post_comment WHERE post_id = ?', (post_id,))
        db.execute('DELETE FROM post WHERE id = ?', (post_id,))
        db.commit()
        db.close()
        flash('帖子已删除', 'info')
        return redirect(url_for('admin'))

    @app.route('/admin/rating/<int:rating_id>/delete', methods=['POST'])
    @login_required
    def admin_delete_rating(rating_id):
        if not current_user.is_admin:
            flash('无管理员权限', 'danger')
            return redirect(url_for('index'))
        db = get_db()
        rating = db.execute('SELECT dish_id FROM rating WHERE id = ?', (rating_id,)).fetchone()
        if rating:
            dish_id = rating['dish_id']
            db.execute('DELETE FROM rating WHERE id = ?', (rating_id,))
            db.commit()
            avg = db.execute(
                'SELECT ROUND(AVG(score), 1) as avg FROM rating WHERE dish_id = ?', (dish_id,)
            ).fetchone()
            db.execute('UPDATE dish SET average_rating = ? WHERE id = ?', (avg['avg'] or 0, dish_id))
            db.commit()
            flash('评分已删除', 'info')
        db.close()
        return redirect(url_for('admin'))

    @app.route('/admin/comment/<int:comment_id>/delete', methods=['POST'])
    @login_required
    def admin_delete_comment(comment_id):
        if not current_user.is_admin:
            flash('无管理员权限', 'danger')
            return redirect(url_for('index'))
        db = get_db()
        db.execute('DELETE FROM comment WHERE id = ?', (comment_id,))
        db.commit()
        db.close()
        flash('评论已删除', 'info')
        return redirect(url_for('admin'))
