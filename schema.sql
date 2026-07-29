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

-- 食堂表
CREATE TABLE IF NOT EXISTS canteen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    floor TEXT,
    crowd_status TEXT DEFAULT '一般',
    description TEXT
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
    content TEXT,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES post(id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);
