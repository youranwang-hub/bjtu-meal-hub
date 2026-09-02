const app = getApp();

Component({
  data: { activePath: '', actionOpen: false, randomDish: null, mealLabel: '', deciding: false, left: [
    { text: '首页', icon: '/assets/nav-home.svg', path: '/pages/home/index' },
    { text: '社区', icon: '/assets/nav-community.svg', path: '/pages/community/index' }], right: [
    { text: '打卡', icon: '/assets/nav-checkin.svg', path: '/pages/checkin/index' },
    { text: '我的', icon: '/assets/nav-profile.svg', path: '/pages/me/index' }
  ] },
  lifetimes: { attached() { this.syncActive(); } },
  pageLifetimes: { show() { this.syncActive(); } },
  methods: {
    syncActive() { const pages = getCurrentPages(); const page = pages[pages.length - 1]; this.setData({ activePath: page ? '/' + page.route : '' }); },
    switchTab(e) { const path = e.currentTarget.dataset.path; this.setData({ activePath: path }); wx.switchTab({ url: path }); },
    action() { this.setData({ actionOpen: true, randomDish: null, mealLabel: '' }); },
    closeAction() { this.setData({ actionOpen: false }); },
    async dice() {
      this.setData({ deciding: true });
      try { const result = await app.request({ url: '/dishes/random' }); this.setData({ randomDish: result.dish, mealLabel: result.mealLabel }); }
      catch (error) { wx.showToast({ title: error.message, icon: 'none' }); }
      finally { this.setData({ deciding: false }); }
    },
    openDish() { const id = this.data.randomDish && this.data.randomDish.id; if (!id) return; this.closeAction(); wx.navigateTo({ url: '/pages/dish/index?id=' + id }); }
  }
});
