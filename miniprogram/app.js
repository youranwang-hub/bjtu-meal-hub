const API_BASE = 'https://xiaoshixuji.xyz/api';

App({
  globalData: { apiBase: API_BASE, user: null },
  onLaunch() { this.globalData.user = wx.getStorageSync('user') || null; },
  request(options) {
    const token = wx.getStorageSync('token');
    return new Promise((resolve, reject) => {
      wx.request({
        url: API_BASE + options.url, method: options.method || 'GET', data: options.data,
        header: Object.assign({ 'content-type': 'application/json' }, token ? { Authorization: 'Bearer ' + token } : {}),
        success: (res) => {
          if (res.statusCode === 401) { wx.removeStorageSync('token'); wx.removeStorageSync('user'); this.globalData.user = null; }
          if (res.data && res.data.ok) resolve(res.data.data);
          else reject(new Error((res.data && res.data.message) || '请求失败'));
        },
        fail: () => reject(new Error('无法连接服务器，请检查 API 地址与网络配置'))
      });
    });
  },
  upload(options) {
    const token = wx.getStorageSync('token');
    return new Promise((resolve, reject) => {
      wx.uploadFile({ url: API_BASE + options.url, filePath: options.filePath, name: options.name || 'image', formData: options.formData || {}, header: token ? { Authorization: 'Bearer ' + token } : {}, success: (res) => { let data; try { data=JSON.parse(res.data); } catch(e) { return reject(new Error('服务器返回异常')); } if (data.ok) resolve(data.data); else reject(new Error(data.message || '上传失败')); }, fail: () => reject(new Error('图片上传失败，请检查网络')) });
    });
  },
  async wechatLogin() {
    const login = await new Promise((resolve, reject) => wx.login({ success: resolve, fail: reject }));
    const result = await this.request({ url: '/auth/wechat', method: 'POST', data: { code: login.code || 'dev-mock' } });
    wx.setStorageSync('token', result.token); wx.setStorageSync('user', result.user); this.globalData.user = result.user;
    return result.user;
  },
  requireLogin(action = '参与互动') {
    if (wx.getStorageSync('token')) return true;
    if (this.globalData.loginPrompting) return false;
    this.globalData.loginPrompting = true;
    wx.showModal({ title: '登录后即可' + action, content: '浏览内容无需登录。登录后可同步你的打卡、互动和投稿记录。', confirmText: '去登录', success: result => {
      if (result.confirm) wx.navigateTo({ url: '/pages/login/index' });
    }, complete: () => { this.globalData.loginPrompting = false; } });
    return false;
  }
});
