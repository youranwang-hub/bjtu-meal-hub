const app = getApp();
Page({
  data: { user: null, badges: [], photos: [], reports: [], feedbacks: [], unreadFeedbackCount: 0, checkins: [], mealMap: { monthLabel: '', total: 0, sourceStats: [], favoriteCanteen: '', canteenStats: [] }, likes: [], notifications: [], feedbackOpen: false, detailOpen: false, detailType: '', profileOpen: false, profileSaving: false, profileNickname: '', profileAvatarId: 'rice', avatars: [{ id: 'rice', label: '饭' }, { id: 'leaf', label: '叶' }, { id: 'tea', label: '茶' }, { id: 'star', label: '星' }, { id: 'moon', label: '月' }, { id: 'cloud', label: '云' }, { id: 'seed', label: '芽' }, { id: 'note', label: '记' }], feedbackTypes: ['建议', '问题', '想说的话'], feedbackTypeIndex: 0, feedbackType: '建议', feedbackContent: '', feedbackSending: false },
  onShow() { this.load(); },
  async load() { const cached = wx.getStorageSync('user'); if (!cached) return this.setData({ user: null }); try { const data = await app.request({ url: '/me' }); wx.setStorageSync('user', data.user); this.setData(data, () => this.drawMealMap()); } catch (e) { this.setData({ user: cached }); } },
  drawMealMap() {
    const map = this.data.mealMap || {}, stats = map.sourceStats || [], total = map.total || 0;
    const context = wx.createCanvasContext('mealMap', this), size = 300, center = 150, radius = 104;
    context.clearRect(0, 0, size, size); context.setLineWidth(30); context.setLineCap('butt');
    if (!total) { context.beginPath(); context.setStrokeStyle('#e9e1d4'); context.arc(center, center, radius, 0, Math.PI * 2); context.stroke(); }
    else {
      let start = -Math.PI / 2;
      stats.forEach(item => { if (!item.count) return; const angle = item.count / total * Math.PI * 2; context.beginPath(); context.setStrokeStyle(item.color); context.arc(center, center, radius, start + 0.025, start + angle - 0.025); context.stroke(); start += angle; });
    }
    context.setTextAlign('center'); context.setFillStyle('#604832'); context.setFontSize(42); context.fillText(String(total), center, 145);
    context.setFillStyle('#8b796d'); context.setFontSize(18); context.fillText('本月顿数', center, 178); context.draw();
  },
  login() { wx.navigateTo({ url: '/pages/login/index' }); }, admin() { wx.navigateTo({ url: '/pages/admin/index' }); },
  openProfile() { const user = this.data.user; if (!user) return; this.setData({ profileOpen: true, profileNickname: user.nickname, profileAvatarId: user.avatarId || 'rice' }); },
  openDetail(e) { this.setData({ detailOpen: true, detailType: e.currentTarget.dataset.type }); },
  closeDetail() { this.setData({ detailOpen: false, detailType: '' }); },
  closeProfile() { this.setData({ profileOpen: false }); },
  profileInput(e) { this.setData({ profileNickname: e.detail.value }); },
  chooseAvatar(e) { this.setData({ profileAvatarId: e.currentTarget.dataset.id }); },
  async saveProfile() { const nickname = this.data.profileNickname.trim(); if (nickname.length < 2) return wx.showToast({ title: '昵称至少 2 个字符', icon: 'none' }); this.setData({ profileSaving: true }); try { const data = await app.request({ url: '/me/profile', method: 'POST', data: { nickname, avatarId: this.data.profileAvatarId } }); wx.setStorageSync('user', data.user); app.globalData.user = data.user; this.setData({ user: data.user, profileOpen: false }); wx.showToast({ title: '小食身份已更新' }); } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } finally { this.setData({ profileSaving: false }); } },
  goPost(e) { const d = e.currentTarget.dataset; wx.navigateTo({ url: '/pages/post/index?id=' + d.postid + (d.commentid ? '&commentId=' + d.commentid : '') }); },
  privacy() { wx.navigateTo({ url: '/pages/privacy/index' }); },
  openFeedback() { if (!app.requireLogin('写信给饭搭子')) return; this.setData({ feedbackOpen: true, feedbackContent: '', feedbackTypeIndex: 0, feedbackType: '建议' }); },
  closeFeedback() { this.setData({ feedbackOpen: false }); },
  feedbackTypeChange(e) { const feedbackTypeIndex = Number(e.detail.value); this.setData({ feedbackTypeIndex, feedbackType: this.data.feedbackTypes[feedbackTypeIndex] }); },
  feedbackInput(e) { this.setData({ feedbackContent: e.detail.value }); },
  async submitFeedback() { if (this.data.feedbackContent.trim().length < 2) return wx.showToast({ title: '再多写一点点吧', icon: 'none' }); this.setData({ feedbackSending: true }); try { await app.request({ url: '/feedback', method: 'POST', data: { feedbackType: this.data.feedbackType, content: this.data.feedbackContent.trim() } }); this.closeFeedback(); wx.showModal({ title: '收到啦', content: '谢谢你愿意和饭搭子说说，我们会认真看。', showCancel: false }); } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } finally { this.setData({ feedbackSending: false }); } },
  async readFeedback(e) { const id = e.currentTarget.dataset.id; const item = this.data.feedbacks.find(x => x.id === id); if (!item || !item.hasUnreadReply) return; try { await app.request({ url: '/feedback/' + id + '/read', method: 'POST' }); this.setData({ feedbacks: this.data.feedbacks.map(x => x.id === id ? Object.assign({}, x, { hasUnreadReply: false }) : x), unreadFeedbackCount: Math.max(0, this.data.unreadFeedbackCount - 1) }); } catch (error) {} },
  logout() { wx.removeStorageSync('token'); wx.removeStorageSync('user'); app.globalData.user = null; this.setData({ user: null, badges: [], photos: [], reports: [], feedbacks: [], unreadFeedbackCount: 0, checkins: [], mealMap: { monthLabel: '', total: 0, sourceStats: [], favoriteCanteen: '', canteenStats: [] }, likes: [], notifications: [] }); }
});
