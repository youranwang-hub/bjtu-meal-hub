const app = getApp();

Page({
  data: { posts: [], compose: false, content: '', imagePaths: [], publishing: false },
  onShow() { this.load(); },
  async load() { try { this.setData({ posts: await app.request({ url: '/community' }) }); } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } },
  open() { if (app.requireLogin()) this.setData({ compose: true }); },
  close() { this.setData({ compose: false, content: '', imagePaths: [] }); },
  input(e) { this.setData({ content: e.detail.value }); },
  photo() {
    wx.showActionSheet({ itemList: ['拍照', '从相册选择'], success: result => this.pickMedia(result.tapIndex === 0 ? 'camera' : 'album') });
  },
  pickMedia(sourceType) {
    wx.chooseMedia({ count: 3 - this.data.imagePaths.length, mediaType: ['image'], sourceType: [sourceType], sizeType: ['compressed'], success: async result => {
      try {
        wx.showLoading({ title: '正在处理图片' });
        const paths = [];
        for (const file of result.tempFiles) paths.push((await this.ensureSize(file.tempFilePath, file.size)).path);
        this.setData({ imagePaths: this.data.imagePaths.concat(paths).slice(0, 3) });
      } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } finally { wx.hideLoading(); }
    }});
  },
  async ensureSize(path, size) {
    const limit = 5 * 1024 * 1024;
    if (size <= limit) return { path, size };
    let current = path;
    for (const quality of [80, 60, 40]) {
      const compressed = await new Promise((resolve, reject) => wx.compressImage({ src: current, quality, success: resolve, fail: reject }));
      current = compressed.tempFilePath;
      const info = await new Promise((resolve, reject) => wx.getFileInfo({ filePath: current, success: resolve, fail: reject }));
      if (info.size <= limit) return { path: current, size: info.size };
    }
    throw new Error('图片压缩后仍超过 5MB，请换一张图片');
  },
  removeImage(e) { this.setData({ imagePaths: this.data.imagePaths.filter((_, index) => index !== e.currentTarget.dataset.index) }); },
  detail(e) { wx.navigateTo({ url: '/pages/post/index?id=' + e.currentTarget.dataset.id }); },
  async publish() {
    if (!this.data.content.trim() && !this.data.imagePaths.length) return wx.showToast({ title: '写点内容或选一张照片吧', icon: 'none' });
    this.setData({ publishing: true });
    try {
      const uploads = await Promise.all(this.data.imagePaths.map(filePath => app.upload({ url: '/community/uploads', filePath })));
      await app.request({ url: '/community', method: 'POST', data: { content: this.data.content, images: uploads.map(item => item.path) } });
      this.close(); wx.showToast({ title: '发布成功' }); this.load();
    } catch (e) { wx.showToast({ title: e.message, icon: 'none' }); } finally { this.setData({ publishing: false }); }
  }
});
