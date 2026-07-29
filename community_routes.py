"""社区路由：发帖、点赞、评论、帖子详情"""
import json as _json
import random
import uuid
import os
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from helpers import (get_db, relative_time, UPLOAD_FOLDER, MAX_FILE_SIZE,
                     ALLOWED_EXTENSIONS, PER_PAGE)

PLACEHOLDERS = [
    '今天吃了什么好吃的？',
    '分享一道让你惊艳的菜...',
    '食堂又出新品了？求安利！',
    '一人食也值得好好记录',
    '晒一晒今天的食堂战利品',
]
AVATAR_COLORS = ['#e74c3c', '#e67e22', '#2ecc71', '#3498db', '#9b59b6',
                 '#1abc9c', '#f39c12', '#e91e63', '#00bcd4', '#ff5722']


def init_app(app):
    @app.route('/community')
    def community():
        db = get_db()
        random_placeholder = random.choice(PLACEHOLDERS)
        hot_posts_data = []
        hot_posts_raw = db.execute(
            'SELECT p.*, u.nickname FROM post p JOIN user u ON p.user_id = u.id '
            'ORDER BY p.like_count DESC, p.create_time DESC LIMIT 10'
        ).fetchall()
        hot_ids = [row['id'] for row in hot_posts_raw]
        for row in hot_posts_raw:
            p = dict(row)
            p['time_ago'] = relative_time(p['create_time'])
            try:
                p['image_list'] = _json.loads(p['images']) if p['images'] else []
            except Exception:
                p['image_list'] = []
            name = p['nickname'] or '用户'
            p['avatar_color'] = AVATAR_COLORS[sum(ord(c) for c in name) % len(AVATAR_COLORS)]
            hot_posts_data.append(p)

        page = request.args.get('page', 1, type=int)
        if page < 1:
            page = 1
        if hot_ids:
            ph = ','.join('?' for _ in hot_ids)
            total_count = db.execute(
                f'SELECT COUNT(*) as n FROM post WHERE id NOT IN ({ph})', hot_ids
            ).fetchone()['n']
        else:
            total_count = db.execute('SELECT COUNT(*) as n FROM post').fetchone()['n']
        total_pages = max(1, (total_count + PER_PAGE - 1) // PER_PAGE)
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * PER_PAGE

        if hot_ids:
            ph = ','.join('?' for _ in hot_ids)
            page_rows = db.execute(
                f'SELECT p.*, u.nickname FROM post p JOIN user u ON p.user_id = u.id '
                f'WHERE p.id NOT IN ({ph}) '
                f'ORDER BY p.create_time DESC LIMIT ? OFFSET ?',
                (*hot_ids, PER_PAGE, offset)
            ).fetchall()
        else:
            page_rows = db.execute(
                'SELECT p.*, u.nickname FROM post p JOIN user u ON p.user_id = u.id '
                'ORDER BY p.create_time DESC LIMIT ? OFFSET ?',
                (PER_PAGE, offset)
            ).fetchall()

        page_post_ids = [row['id'] for row in page_rows]
        comments_by_post = {}
        if page_post_ids:
            ph = ','.join('?' for _ in page_post_ids)
            comment_rows = db.execute(
                f'SELECT pc.*, u2.nickname FROM post_comment pc '
                f'JOIN user u2 ON pc.user_id = u2.id WHERE pc.post_id IN ({ph}) '
                f'ORDER BY pc.create_time ASC',
                page_post_ids
            ).fetchall()
            for c in comment_rows:
                pc = dict(c)
                pc['time_ago'] = relative_time(pc['create_time'])
                comments_by_post.setdefault(c['post_id'], []).append(pc)

        user_likes = set()
        if current_user.is_authenticated and page_post_ids:
            ph = ','.join('?' for _ in page_post_ids)
            liked_rows = db.execute(
                f'SELECT post_id FROM post_like WHERE user_id = ? AND post_id IN ({ph})',
                (current_user.id, *page_post_ids)
            ).fetchall()
            user_likes = {r['post_id'] for r in liked_rows}

        posts_data = []
        for row in page_rows:
            p = dict(row)
            p['time_ago'] = relative_time(p['create_time'])
            try:
                p['image_list'] = _json.loads(p['images']) if p['images'] else []
            except Exception:
                p['image_list'] = []
            p['comments'] = comments_by_post.get(p['id'], [])
            p['user_liked'] = p['id'] in user_likes
            name = p['nickname'] or '用户'
            p['avatar_color'] = AVATAR_COLORS[sum(ord(c) for c in name) % len(AVATAR_COLORS)]
            posts_data.append(p)

        db.close()
        return render_template('community.html', posts=posts_data,
                               hot_posts=hot_posts_data,
                               random_placeholder=random_placeholder,
                               page=page, total_pages=total_pages)

    @app.route('/post/<int:post_id>')
    def post_detail(post_id):
        db = get_db()
        post = db.execute(
            'SELECT p.*, u.nickname FROM post p '
            'JOIN user u ON p.user_id = u.id WHERE p.id = ?', (post_id,)
        ).fetchone()
        if not post:
            db.close()
            return '帖子不存在', 404
        p = dict(post)
        p['time_ago'] = relative_time(p['create_time'])
        try:
            p['image_list'] = _json.loads(p['images']) if p['images'] else []
        except Exception:
            p['image_list'] = []
        name = p['nickname'] or '用户'
        p['avatar_color'] = AVATAR_COLORS[sum(ord(c) for c in name) % len(AVATAR_COLORS)]
        comments = []
        for c in db.execute(
            'SELECT pc.*, u2.nickname FROM post_comment pc '
            'JOIN user u2 ON pc.user_id = u2.id WHERE pc.post_id = ? '
            'ORDER BY pc.create_time ASC', (post_id,)
        ).fetchall():
            pc = dict(c)
            pc['time_ago'] = relative_time(pc['create_time'])
            comments.append(pc)
        p['user_liked'] = False
        if current_user.is_authenticated:
            liked = db.execute(
                'SELECT 1 FROM post_like WHERE user_id = ? AND post_id = ?',
                (current_user.id, post_id)
            ).fetchone()
            p['user_liked'] = liked is not None
        db.close()
        return render_template('post_detail.html', post=p, comments=comments)

    @app.route('/post/create', methods=['POST'])
    @login_required
    def create_post():
        content = request.form.get('content', '').strip()
        dish_name = request.form.get('dish_name', '').strip()
        if not content:
            flash('内容不能为空', 'danger')
            return redirect(url_for('community'))
        if len(content) > 1000:
            flash('内容不能超过 1000 字', 'danger')
            return redirect(url_for('community'))
        db = get_db()
        dish_id = None
        if dish_name:
            match = db.execute(
                'SELECT id FROM dish WHERE name LIKE ? ORDER BY name LIMIT 1',
                (f'%{dish_name}%',)
            ).fetchone()
            if match:
                dish_id = match['id']
        image_paths = []
        files = request.files.getlist('images')
        if len(files) > 9:
            flash('最多上传 9 张图片', 'danger')
            return redirect(url_for('community'))
        for f in files[:9]:
            if f and f.filename:
                ext = os.path.splitext(f.filename)[1]
                if ext.lower() not in ALLOWED_EXTENSIONS:
                    flash(f'不支持的文件类型: {ext}', 'danger')
                    return redirect(url_for('community'))
                file_data = f.read()
                if len(file_data) > MAX_FILE_SIZE:
                    flash(f'图片 {f.filename} 超过 5MB 限制，请压缩后上传', 'danger')
                    return redirect(url_for('community'))
                filename = f"{uuid.uuid4().hex}{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                with open(filepath, 'wb') as outf:
                    outf.write(file_data)
                image_paths.append(f"uploads/{filename}")
        db.execute(
            'INSERT INTO post (user_id, dish_id, content, images) VALUES (?,?,?,?)',
            (current_user.id, dish_id, content,
             _json.dumps(image_paths, ensure_ascii=False)))
        db.commit()
        db.close()
        flash('发布成功！', 'success')
        return redirect(url_for('community'))

    @app.route('/post/<int:post_id>/like', methods=['POST'])
    @login_required
    def like_post(post_id):
        db = get_db()
        existing = db.execute(
            'SELECT 1 FROM post_like WHERE user_id = ? AND post_id = ?',
            (current_user.id, post_id)
        ).fetchone()
        if not existing:
            db.execute(
                'INSERT INTO post_like (user_id, post_id) VALUES (?,?)',
                (current_user.id, post_id))
            count = db.execute(
                'SELECT COUNT(*) as n FROM post_like WHERE post_id = ?', (post_id,)
            ).fetchone()['n']
            db.execute('UPDATE post SET like_count = ? WHERE id = ?', (count, post_id))
            db.commit()
        db.close()
        return redirect(url_for('post_detail', post_id=post_id))

    @app.route('/post/<int:post_id>/comment', methods=['POST'])
    @login_required
    def comment_post(post_id):
        content = request.form.get('content', '').strip()
        if not content:
            flash('评论不能为空', 'danger')
            return redirect(url_for('community'))
        if len(content) > 300:
            flash('评论不能超过 300 字', 'danger')
            return redirect(url_for('community'))
        db = get_db()
        db.execute(
            'INSERT INTO post_comment (post_id, user_id, content) VALUES (?,?,?)',
            (post_id, current_user.id, content))
        db.commit()
        db.close()
        flash('评论成功！', 'success')
        return redirect(url_for('post_detail', post_id=post_id))

    @app.route('/post/<int:post_id>/delete', methods=['POST'])
    @login_required
    def delete_post(post_id):
        db = get_db()
        post = db.execute('SELECT * FROM post WHERE id = ?', (post_id,)).fetchone()
        if not post:
            db.close()
            flash('帖子不存在', 'danger')
            return redirect(url_for('community'))
        if post['user_id'] != current_user.id and not current_user.is_admin:
            db.close()
            flash('无权删除此帖子', 'danger')
            return redirect(url_for('community'))
        db.execute('DELETE FROM post_like WHERE post_id = ?', (post_id,))
        db.execute('DELETE FROM post_comment WHERE post_id = ?', (post_id,))
        db.execute('DELETE FROM post WHERE id = ?', (post_id,))
        db.commit()
        db.close()
        flash('帖子已删除', 'info')
        return redirect(url_for('community'))
