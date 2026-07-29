"""应用工厂：CSRF 保护、错误处理、注册各模块路由"""
from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_login import LoginManager
import os
import secrets

from helpers import get_dish_image, generate_csrf_token, load_user


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'bjtu-canteen-secret-key-2026')

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = '请先登录后再操作'
    login_manager.user_loader(load_user)

    app.jinja_env.globals['get_dish_image'] = get_dish_image
    app.jinja_env.globals['csrf_token'] = generate_csrf_token

    @app.before_request
    def csrf_protect():
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            if request.path.startswith('/static/'):
                return None
            token = request.form.get('_csrf_token', '')
            if not token or not secrets.compare_digest(token, session.get('_csrf_token', '')):
                flash('表单已过期，请刷新页面后重试', 'danger')
                return redirect(request.referrer or url_for('index'))

    from auth import init_app as init_auth
    from main_routes import init_app as init_main
    from community_routes import init_app as init_community
    from checkin_routes import init_app as init_checkin
    from admin_routes import init_app as init_admin

    init_auth(app)
    init_main(app)
    init_community(app)
    init_checkin(app)
    init_admin(app)

    @app.errorhandler(404)
    def not_found(e):
        return render_template('base.html', error_code=404, error_msg='页面不存在'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('base.html', error_code=500, error_msg='服务器内部错误'), 500

    return app


app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, host='127.0.0.1', port=5000)
