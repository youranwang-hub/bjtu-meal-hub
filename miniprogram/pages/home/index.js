const app = getApp();

Page({
  data: { recommended: [], newDishes: [], specialDishes: [], canteens: [], canteenBuildings: [], mapMarkers: [], selectedBuilding: null, mapCenter: { longitude: 116.342, latitude: 39.9505 }, mapScale: 15, today: '', searchOpen: false, query: '', searchResults: [], reportOpen: false, report: { canteenName: '', stallName: '', dishName: '' } },
  onLoad() { const d = new Date(); this.setData({ today: `${d.getMonth() + 1} 月 ${d.getDate()} 日 · ${['日', '一', '二', '三', '四', '五', '六'][d.getDay()]}` }); },
  onShow() { this.load(); },
  async load() {
    try {
      const data = await app.request({ url: '/home' });
      const statusMap = { '空闲': 'idle', '适中': 'moderate', '拥挤': 'busy', '暂无报送': 'unknown' };
      data.canteens = data.canteens.map(canteen => Object.assign({}, canteen, { statusClass: statusMap[canteen.crowdStatus] || 'unknown' }));
      data.canteenBuildings = (data.canteenBuildings || []).map(building => Object.assign({}, building, { statusClass: statusMap[building.crowdStatus] || 'unknown' }));
      data.mapMarkers = data.canteenBuildings.map((building, index) => {
        return { id: building.id, longitude: building.longitude, latitude: building.latitude, iconPath: '/assets/food-marker.svg', width: 34, height: 40, anchor: { x: 0.5, y: 1 }, callout: { content: building.name, display: 'ALWAYS', color: '#63482f', fontSize: 12, borderRadius: 13, bgColor: '#f8f0df', padding: 8, borderWidth: 1, borderColor: '#d3ac70', textAlign: 'center' }, zIndex: 10 + index };
      });
      this.setData(data);
    } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); }
  },
  mapMarkerTap(e) { this.setData({ selectedBuilding: this.data.canteenBuildings.find(item => item.id === e.detail.markerId) || null }); },
  closeBuilding() { this.setData({ selectedBuilding: null }); },
  search() { this.setData({ searchOpen: true }); },
  searchInput(e) { const query = e.detail.value; this.setData({ query }); clearTimeout(this.searchTimer); if (!query.trim()) return this.setData({ searchResults: [] }); this.searchTimer = setTimeout(async () => { try { this.setData({ searchResults: await app.request({ url: '/dishes?q=' + encodeURIComponent(query) }) }); } catch (e) {} }, 180); },
  closeSearch() { this.setData({ searchOpen: false, query: '', searchResults: [] }); },
  reportInput(e) { this.setData({ ['report.' + e.currentTarget.dataset.key]: e.detail.value }); },
  openReport(e) { if (!app.requireLogin('提交上新情报')) return; const canteenName = (e && e.currentTarget.dataset.canteen) || ''; this.setData({ selectedBuilding: null, reportOpen: true, report: { canteenName, stallName: '', dishName: '' } }); },
  closeReport() { this.setData({ reportOpen: false }); },
  async submitReport() { try { await app.request({ url: '/new-dish-reports', method: 'POST', data: this.data.report }); this.setData({ reportOpen: false, report: { canteenName: '', stallName: '', dishName: '' } }); wx.showToast({ title: '情报已送达，谢谢你！', icon: 'none' }); } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } },
  dish(e) { wx.navigateTo({ url: '/pages/dish/index?id=' + e.currentTarget.dataset.id }); },
  canteen(e) { this.closeBuilding(); wx.navigateTo({ url: '/pages/canteen/index?id=' + e.currentTarget.dataset.id }); },
  specials() { wx.navigateTo({ url: '/pages/specials/index' }); }
});
