const app = getApp();
Page({
  data: { stats: {}, statItems: [], posts: [], comments: [], photos: [], reports: [], contentReports: [], feedbacks: [], specialDishes: [], q: '', dishes: [], editing: null, price: '', specialPrice: '', feedbackReplies: {} },
  onShow() { this.load(); },
  async load() {
    try {
      const data = await app.request({ url: '/admin/overview' });
      const reviews = await app.request({ url: '/admin/reviews' });
      data.statItems = [{ label: '用户', value: data.stats.users }, { label: '菜品', value: data.stats.dishes }, { label: '帖子', value: data.stats.posts }, { label: '举报', value: data.stats.contentReports }];
      this.setData(Object.assign(data, reviews));
    } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); if (e.message === '需要管理员权限') wx.navigateBack(); }
  },
  input(e) { this.setData({ q: e.detail.value }); },
  async search() { try { this.setData({ dishes: await app.request({ url: '/admin/dishes?q=' + encodeURIComponent(this.data.q) }) }); } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } },
  edit(e) { const dish = e.currentTarget.dataset.dish; this.setData({ editing: dish, price: String(dish.price), specialPrice: dish.specialPrice ? String(dish.specialPrice) : '' }); },
  priceInput(e) { this.setData({ price: e.detail.value }); },
  specialInput(e) { this.setData({ specialPrice: e.detail.value }); },
  closeEdit() { this.setData({ editing: null }); },
  async savePrice() { try { await app.request({ url: '/admin/dishes/' + this.data.editing.id + '/price', method: 'POST', data: { price: this.data.price } }); wx.showToast({ title: '价格已更新' }); this.closeEdit(); this.load(); if (this.data.q) this.search(); } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } },
  async saveSpecial() { try { await app.request({ url: '/admin/dishes/' + this.data.editing.id + '/special', method: 'POST', data: { price: this.data.specialPrice } }); wx.showToast({ title: '特价已设置' }); this.closeEdit(); this.load(); if (this.data.q) this.search(); } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } },
  async clearSpecial(e) { const id = e.currentTarget.dataset.id || (this.data.editing && this.data.editing.id); if (!id) return; try { await app.request({ url: '/admin/dishes/' + id + '/special', method: 'POST', data: { action: 'clear' } }); wx.showToast({ title: '特价已撤销' }); this.closeEdit(); this.load(); if (this.data.q) this.search(); } catch (err) { wx.showToast({ title: err.message, icon: 'none' }); } },
  feedbackReplyInput(e) { this.setData({ ['feedbackReplies.' + e.currentTarget.dataset.id]: e.detail.value }); },
  async resolveFeedback(e) { const id = e.currentTarget.dataset.id, reply = (this.data.feedbackReplies[id] || '').trim(); if (reply.length < 2) return wx.showToast({ title: '请写一句回复再办结', icon: 'none' }); try { await app.request({ url: '/admin/feedback/' + id, method: 'POST', data: { reply } }); wx.showToast({ title: '回复已送达' }); this.load(); } catch (err) { wx.showToast({ title: err.message, icon: 'none' }); } },
  async handleContentReport(e) { const { id, action } = e.currentTarget.dataset; const removing = action === 'remove'; if (removing) { const result = await new Promise(resolve => wx.showModal({ title: '移除被举报内容？', content: '该操作将对用户不可见', success: value => resolve(value.confirm) })); if (!result) return; } try { await app.request({ url: '/admin/content-reports/' + id, method: 'POST', data: { action } }); wx.showToast({ title: removing ? '内容已移除' : '举报已忽略' }); this.load(); } catch (error) { wx.showToast({ title: error.message, icon: 'none' }); } },
  async removePost(e) { const id = e.currentTarget.dataset.id; const confirm = await new Promise(resolve => wx.showModal({ title: '删除帖子？', content: '删除后无法恢复', success: r => resolve(r.confirm) })); if (!confirm) return; try { await app.request({ url: '/admin/posts/' + id, method: 'DELETE' }); this.load(); } catch (err) { wx.showToast({ title: err.message, icon: 'none' }); } },
  async removeComment(e) { const { id, source } = e.currentTarget.dataset; try { await app.request({ url: '/admin/comments/' + source + '/' + id, method: 'DELETE' }); this.load(); } catch (err) { wx.showToast({ title: err.message, icon: 'none' }); } },
  async review(e) { const { id, type, action } = e.currentTarget.dataset; try { await app.request({ url: '/admin/reviews/' + type + '/' + id, method: 'POST', data: { action } }); wx.showToast({ title: '已处理' }); this.load(); } catch (err) { wx.showToast({ title: err.message, icon: 'none' }); } }
});
