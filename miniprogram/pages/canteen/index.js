const app = getApp();

Page({
  data: { canteen: null, dishes: [], crowdPrompt: true, crowdSending: false, crowdExplain: false },
  onLoad(options) { this.id = options.id; this.load(); },
  async load() {
    try {
      const canteen = await app.request({ url: '/canteens/' + this.id });
      canteen.descriptionText = canteen.description || '欢迎来吃饭';
      canteen.stalls = canteen.stalls.map(stall => Object.assign({}, stall, { locationText: stall.location || '食堂内', openTimeText: stall.open_time || '营业时间待补充' }));
      this.setData({ canteen });
    } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); }
  },
  async reportCrowd(e) {
    if (!app.requireLogin()) return;
    this.setData({ crowdSending: true });
    try {
      const snapshot = await app.request({ url: '/canteens/' + this.id + '/crowd', method: 'POST', data: { level: e.currentTarget.dataset.level } });
      this.setData({ canteen: Object.assign({}, this.data.canteen, snapshot), crowdPrompt: false });
      wx.showToast({ title: '感谢你的报送', icon: 'none' });
    } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } finally { this.setData({ crowdSending: false }); }
  },
  notHere() { this.setData({ crowdPrompt: false }); },
  toggleCrowdExplain() { this.setData({ crowdExplain: !this.data.crowdExplain }); },
  async stalls(e) { try { this.setData({ dishes: await app.request({ url: '/dishes?stallId=' + e.currentTarget.dataset.id }) }); } catch (e) {} },
  dish(e) { wx.navigateTo({ url: '/pages/dish/index?id=' + e.currentTarget.dataset.id }); }
});
