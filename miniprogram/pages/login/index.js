const app = getApp();
const avatars = [{ id: 'rice', label: '饭' }, { id: 'leaf', label: '叶' }, { id: 'tea', label: '茶' }, { id: 'star', label: '星' }, { id: 'moon', label: '月' }, { id: 'cloud', label: '云' }, { id: 'seed', label: '芽' }, { id: 'note', label: '记' }];
Page({
  data: { loading: false, profileOpen: false, saving: false, nickname: '', avatarId: 'rice', avatars },
  async login() { this.setData({ loading: true }); try { const user = await app.wechatLogin(); if (user.profileCompleted) { wx.showToast({ title: '微信登录成功' }); setTimeout(() => wx.navigateBack(), 400); } else this.setData({ profileOpen: true, nickname: '', avatarId: 'rice' }); } catch (e) { wx.showToast({ title: e.message || '微信登录失败', icon: 'none' }); } finally { this.setData({ loading: false }); } },
  input(e) { this.setData({ nickname: e.detail.value }); },
  chooseAvatar(e) { this.setData({ avatarId: e.currentTarget.dataset.id }); },
  async saveProfile() { const nickname = this.data.nickname.trim(); if (nickname.length < 2) return wx.showToast({ title: '昵称至少 2 个字符', icon: 'none' }); this.setData({ saving: true }); try { const data = await app.request({ url: '/me/profile', method: 'POST', data: { nickname, avatarId: this.data.avatarId } }); wx.setStorageSync('user', data.user); app.globalData.user = data.user; wx.showToast({ title: '小食身份已保存' }); setTimeout(() => wx.navigateBack(), 400); } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } finally { this.setData({ saving: false }); } },
  skipProfile() { wx.navigateBack(); }
});
