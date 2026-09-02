const app = getApp();

Page({
  data: {
    doneMeals: [], leaderboard: [], topLeaderboard: [], calendar: [], calendarRecords: [], selectedRecords: [], monthLabel: '', todayLabel: '', selectedDate: '', selectedDateLabel: '', viewYear: 0, viewMonth: 0,
    pendingMeal: null, celebrate: '', celebrateDishName: '', dishQuery: '', dishResults: [], selectedDishes: [], customDish: '',
    sourceOptions: ['食堂', '外卖', '聚餐', '自定义'], sourceIndex: 0, source: '食堂', sourceHint: '例如：麻辣烫、朋友做的饭',
    meals: [
      { key: 'breakfast', short: '早', label: '早餐', warm: '热乎乎的一天，从这里开始。', done: false },
      { key: 'lunch', short: '午', label: '午餐', warm: '午饭吃好，下午才有力气。', done: false },
      { key: 'dinner', short: '晚', label: '晚餐', warm: '辛苦啦，今天也要好好收尾。', done: false }
    ]
  },
  onShow() {
    if (!this.data.viewYear) { const now = new Date(); this.setData({ viewYear: now.getFullYear(), viewMonth: now.getMonth(), selectedDate: this.dateKey(now), selectedDateLabel: `${now.getMonth() + 1} 月 ${now.getDate()} 日` }); }
    this.makeCalendar(); if (wx.getStorageSync('token')) this.load();
  },
  dateKey(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; },
  makeCalendar() {
    const now = new Date(), year = this.data.viewYear, month = this.data.viewMonth;
    const start = new Date(year, month, 1).getDay(), days = new Date(year, month + 1, 0).getDate(), calendar = [];
    for (let i = 0; i < start; i++) calendar.push({ blank: true });
    const counts = this.data.calendarRecords.reduce((result, item) => { result[item.date] = (result[item.date] || 0) + 1; return result; }, {});
    for (let day = 1; day <= days; day++) { const date = this.dateKey(new Date(year, month, day)); calendar.push({ day, date, mealCount: counts[date] || 0, isToday: date === this.dateKey(now), isSelected: date === this.data.selectedDate }); }
    this.setData({ calendar, monthLabel: `${year} 年 ${month + 1} 月`, todayLabel: `${now.getMonth() + 1} 月 ${now.getDate()} 日` });
  },
  changeMonth(e) { const target = new Date(this.data.viewYear, this.data.viewMonth + Number(e.currentTarget.dataset.step), 1); this.setData({ viewYear: target.getFullYear(), viewMonth: target.getMonth(), selectedDate: '', selectedDateLabel: '' }); this.makeCalendar(); if (wx.getStorageSync('token')) this.load(); },
  selectDate(e) { const date = e.currentTarget.dataset.date; if (!date) return; const [year, month, day] = date.split('-'); this.setData({ selectedDate: date, selectedDateLabel: `${Number(month)} 月 ${Number(day)} 日` }); this.syncSelectedRecords(); this.makeCalendar(); },
  syncSelectedRecords() { this.setData({ selectedRecords: this.data.calendarRecords.filter(item => item.date === this.data.selectedDate) }); },
  decorateMeals(doneMeals) { return this.data.meals.map(meal => ({ ...meal, done: doneMeals.indexOf(meal.key) >= 0 })); },
  async load() {
    try {
      const data = await app.request({ url: '/checkins' });
      this.setData({ ...data, topLeaderboard: data.leaderboard.slice(0, 5), meals: this.decorateMeals(data.doneMeals || []) }, () => { this.syncSelectedRecords(); this.makeCalendar(); });
    } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); }
  },
  chooseMeal(e) {
    if (!app.requireLogin('记录这一餐')) return;
    const meal = this.data.meals.find(item => item.key === e.currentTarget.dataset.meal);
    if (!meal || meal.done) return;
    this.setData({ pendingMeal: meal, selectedDishes: [], customDish: '', dishQuery: '', dishResults: [], sourceIndex: 0, source: '食堂' });
  },
  closeMeal() { this.setData({ pendingMeal: null }); },
  changeSource(e) {
    const sourceIndex = Number(e.detail.value), source = this.data.sourceOptions[sourceIndex];
    this.setData({ sourceIndex, source, dishQuery: '', dishResults: [], selectedDishes: [], customDish: '' });
  },
  dishInput(e) {
    const dishQuery = e.detail.value;
    this.setData({ dishQuery }); clearTimeout(this.timer);
    if (!dishQuery) return this.setData({ dishResults: [] });
    this.timer = setTimeout(async () => {
      try { this.setData({ dishResults: await app.request({ url: '/dishes?q=' + encodeURIComponent(dishQuery) }) }); } catch (e) {}
    }, 180);
  },
  selectDish(e) {
    const dish = e.currentTarget.dataset.dish;
    if (this.data.selectedDishes.some(item => item.id === dish.id)) return;
    this.setData({ selectedDishes: this.data.selectedDishes.concat(dish), dishQuery: '', dishResults: [] });
  },
  removeDish(e) { this.setData({ selectedDishes: this.data.selectedDishes.filter(item => item.id !== e.currentTarget.dataset.id) }); },
  customInput(e) { this.setData({ customDish: e.detail.value }); },
  async checkin() {
    const meal = this.data.pendingMeal;
    if (!meal) return;
    if (this.data.source === '食堂' && !this.data.selectedDishes.length) return wx.showToast({ title: '选一道食堂菜品再打卡吧', icon: 'none' });
    if (this.data.source !== '食堂' && !this.data.customDish.trim()) return wx.showToast({ title: '写下这一餐吃了什么吧', icon: 'none' });
    const customDish = this.data.source === '食堂' ? '' : `${this.data.source}：${this.data.customDish.trim()}`;
    try {
      await app.request({ url: '/checkins', method: 'POST', data: { mealType: meal.key, dishIds: this.data.selectedDishes.map(item => item.id), customDish } });
      const celebrateDishName = this.data.selectedDishes[0] ? this.data.selectedDishes[0].name : this.data.customDish.trim();
      this.setData({ pendingMeal: null, celebrate: meal.label, celebrateDishName }); await this.load();
      setTimeout(() => this.setData({ celebrate: '' }), 5000);
    } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); }
  },
  addPhotoAfterCheckin() { const dishName = this.data.celebrateDishName; this.setData({ celebrate: '' }); wx.navigateTo({ url: '/pages/action/index?mode=upload' + (dishName ? '&dishName=' + encodeURIComponent(dishName) : '') }); }
});
