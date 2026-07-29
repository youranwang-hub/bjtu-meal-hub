"""认证路由：登录、注册、登出"""
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
import bcrypt
from helpers import get_db, User


def init_app(app):
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'GET':
            return render_template('register.html')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        nickname = request.form.get('nickname', '').strip() or username
        if not username or not password:
            flash('用户名和密码不能为空', 'danger')
            return render_template('register.html')
        if len(username) < 2 or len(username) > 20:
            flash('用户名需在 2-20 个字符之间', 'danger')
            return render_template('register.html')
        if len(password) < 6:
            flash('密码至少需要 6 位', 'danger')
            return render_template('register.html')
        if password != password_confirm:
            flash('两次输入的密码不一致', 'danger')
            return render_template('register.html')
        db = get_db()
        existing = db.execute('SELECT id FROM user WHERE username = ?', (username,)).fetchone()
        if existing:
            db.close()
            flash('用户名已被注册，请换一个', 'danger')
            return render_template('register.html')
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor = db.execute(
            'INSERT INTO user (username, password, nickname) VALUES (?,?,?)',
            (username, hashed, nickname))
        db.commit()
        user_id = cursor.lastrowid
        row = db.execute('SELECT * FROM user WHERE id = ?', (user_id,)).fetchone()
        db.close()
        login_user(User(row))
        flash('注册成功，欢迎加入！', 'success')
        return redirect(url_for('index'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            return render_template('login.html')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('请输入用户名和密码', 'danger')
            return render_template('login.html')
        db = get_db()
        row = db.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()
        db.close()
        if not row:
            flash('用户名不存在', 'danger')
            return render_template('login.html')
        if not bcrypt.checkpw(password.encode('utf-8'), row['password'].encode('utf-8')):
            flash('密码错误', 'danger')
            return render_template('login.html')
        login_user(User(row))
        flash('登录成功！', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('已退出登录', 'info')
        return redirect(url_for('index'))
