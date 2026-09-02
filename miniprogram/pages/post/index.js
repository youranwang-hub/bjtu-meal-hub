const app = getApp();

Page({
  data: { post: null, comments: [], content: '', replyTarget: null },
  onLoad(options) {
    this.id = options.id;
    this.commentId = options.commentId;
    this.load();
  },
  async load() {
    try {
      const suffix = this.commentId ? '?commentId=' + this.commentId : '';
      const data = await app.request({ url: '/posts/' + this.id + suffix });
      this.setData(data);
    } catch (error) {
      wx.showToast({ title: error.message, icon: 'none' });
    }
  },
  input(event) { this.setData({ content: event.detail.value }); },
  reply(event) { this.setData({ replyTarget: event.currentTarget.dataset.comment }); },
  cancelReply() { this.setData({ replyTarget: null }); },
  async like() {
    if (!app.requireLogin('点赞')) return;
    try {
      const data = await app.request({ url: '/posts/' + this.id + '/like', method: 'POST' });
      this.setData({ 'post.likeCount': data.likeCount, 'post.liked': data.liked });
    } catch (error) { wx.showToast({ title: error.message, icon: 'none' }); }
  },
  async removePost() {
    const result = await new Promise(resolve => wx.showModal({ title: '删除这条帖子？', content: '删除后无法恢复', success: value => resolve(value.confirm) }));
    if (!result) return;
    try { await app.request({ url: '/posts/' + this.id, method: 'DELETE' }); wx.showToast({ title: '已删除' }); setTimeout(() => wx.navigateBack(), 450); } catch (error) { wx.showToast({ title: error.message, icon: 'none' }); }
  },
  async removeComment(e) {
    const id = e.currentTarget.dataset.id;
    const result = await new Promise(resolve => wx.showModal({ title: '删除这条评论？', content: '删除后会保留回复关系', success: value => resolve(value.confirm) }));
    if (!result) return;
    try { await app.request({ url: '/posts/' + this.id + '/comments/' + id, method: 'DELETE' }); this.load(); } catch (error) { wx.showToast({ title: error.message, icon: 'none' }); }
  },
  report(e) {
    if (!app.requireLogin('举报内容')) return;
    const { type, id } = e.currentTarget.dataset;
    wx.showActionSheet({ itemList: ['不友善内容', '广告或诈骗', '其他不适宜内容'], success: async result => {
      try { await app.request({ url: '/community/reports', method: 'POST', data: { targetType: type, targetId: id, reason: ['不友善内容', '广告或诈骗', '其他不适宜内容'][result.tapIndex] } }); wx.showToast({ title: '举报已提交', icon: 'none' }); } catch (error) { wx.showToast({ title: error.message, icon: 'none' }); }
    }});
  },
  async comment() {
    if (!app.requireLogin('评论') || !this.data.content.trim()) return;
    try {
      await app.request({
        url: '/posts/' + this.id + '/comments', method: 'POST',
        data: { content: this.data.content, parentId: this.data.replyTarget ? this.data.replyTarget.id : null }
      });
      this.setData({ content: '', replyTarget: null });
      this.load();
    } catch (error) { wx.showToast({ title: error.message, icon: 'none' }); }
  }
});
