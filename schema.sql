-- 用户表
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    nickname TEXT,
    avatar_url TEXT,
    checkin_points INTEGER DEFAULT 0,
    is_admin INTEGER DEFAULT 0,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 食堂建筑表：一座建筑可包含多个楼层/餐厅
CREATE TABLE IF NOT EXISTS canteen_building (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    longitude REAL,
    latitude REAL,
    description TEXT,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 餐厅表：隶属于食堂建筑，可代表不同楼层或独立餐厅
CREATE TABLE IF NOT EXISTS canteen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    floor TEXT,
    crowd_status TEXT DEFAULT '一般',
    description TEXT,
    building_id INTEGER,
    FOREIGN KEY (building_id) REFERENCES canteen_building(id)
);

-- 档口表
CREATE TABLE IF NOT EXISTS stall (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canteen_id INTEGER,
    name TEXT NOT NULL,
    location TEXT,
    open_time TEXT,
    FOREIGN KEY (canteen_id) REFERENCES canteen(id)
);

-- 菜品表
CREATE TABLE IF NOT EXISTS dish (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stall_id INTEGER,
    name TEXT NOT NULL,
    price REAL,
    image_url TEXT,
    average_rating REAL DEFAULT 0,
    is_new INTEGER DEFAULT 0,
    special_price REAL,
    tags TEXT,
    category TEXT,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stall_id) REFERENCES stall(id)
);

-- 评分表
CREATE TABLE IF NOT EXISTS rating (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    dish_id INTEGER,
    score INTEGER,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (dish_id) REFERENCES dish(id),
    UNIQUE(user_id, dish_id)
);

-- 评论表
CREATE TABLE IF NOT EXISTS comment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    dish_id INTEGER,
    content TEXT,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (dish_id) REFERENCES dish(id)
);

-- 社区帖子表
CREATE TABLE IF NOT EXISTS post (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    dish_id INTEGER,
    content TEXT,
    images TEXT,
    like_count INTEGER DEFAULT 0,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- 打卡记录表
CREATE TABLE IF NOT EXISTS checkin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    meal_type TEXT,
    dish_ids TEXT,
    checkin_date DATE,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- 帖子点赞表
CREATE TABLE IF NOT EXISTS post_like (
    user_id INTEGER,
    post_id INTEGER,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (post_id) REFERENCES post(id),
    UNIQUE(user_id, post_id)
);

-- 帖子评论表
CREATE TABLE IF NOT EXISTS post_comment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,
    user_id INTEGER,
    parent_id INTEGER,
    content TEXT,
    is_deleted INTEGER DEFAULT 0,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES post(id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- 社区内容举报：用户可举报帖子或评论，管理员统一处理
CREATE TABLE IF NOT EXISTS community_content_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reporter_id) REFERENCES user(id)
);

-- 小程序 API 登录令牌
CREATE TABLE IF NOT EXISTS api_token (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expire_time TIMESTAMP NOT NULL,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- 用户提交的菜品上新情报，供管理员审核后录入
CREATE TABLE IF NOT EXISTS new_dish_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    canteen_name TEXT,
    stall_name TEXT,
    dish_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- 用户上传的菜品实拍图，审核通过后可设为菜品图片
CREATE TABLE IF NOT EXISTS dish_image_submission (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    dish_id INTEGER,
    dish_name TEXT NOT NULL,
    image_path TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (dish_id) REFERENCES dish(id)
);

-- 微信身份与站内用户的映射；不保存 session_key
CREATE TABLE IF NOT EXISTS wechat_identity (
    openid TEXT PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- 用户建议、问题与想说的话，由管理员工作台统一处理
CREATE TABLE IF NOT EXISTS user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    feedback_type TEXT NOT NULL DEFAULT '建议',
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reply TEXT,
    replied_time TIMESTAMP,
    read_time TIMESTAMP,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- 同学主动报送的食堂人流；每人每天每个食堂可更新一次报送
CREATE TABLE IF NOT EXISTS canteen_crowd_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    canteen_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    crowd_level INTEGER NOT NULL CHECK (crowd_level BETWEEN 1 AND 3),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, canteen_id, report_date),
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (canteen_id) REFERENCES canteen(id)
);
