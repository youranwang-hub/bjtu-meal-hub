const app=getApp();
Page({
  data:{pickedPath:'',dishName:'',randomDish:null,mealLabel:'',uploading:false,directUpload:false,fileSizeText:''},
  onLoad(o){const directUpload=o.mode==='upload';this.setData({directUpload,dishName:o.dishName?decodeURIComponent(o.dishName):''});wx.setNavigationBarTitle({title:directUpload?'上传菜品实拍图':'今天吃什么'})},
  choosePhoto(){ if(!app.requireLogin()) return; wx.showActionSheet({itemList:['拍照','从相册选择'],success:r=>this.pickMedia(r.tapIndex===0?'camera':'album')}); },
  pickMedia(sourceType){wx.chooseMedia({count:1,mediaType:['image'],sourceType:[sourceType],sizeType:['compressed'],success:async r=>{try{const result=await this.ensureSize(r.tempFiles[0].tempFilePath,r.tempFiles[0].size);this.setData({pickedPath:result.path,fileSizeText:(result.size/1024/1024).toFixed(1)+' MB'});}catch(e){wx.showToast({title:e.message,icon:'none'})}}})},
  async ensureSize(path,size){const limit=5*1024*1024;if(size<=limit)return {path,size};let current=path;for(const quality of [80,60,40]){const compressed=await new Promise((resolve,reject)=>wx.compressImage({src:current,quality,success:resolve,fail:reject}));current=compressed.tempFilePath;const info=await new Promise((resolve,reject)=>wx.getFileInfo({filePath:current,success:resolve,fail:reject}));if(info.size<=limit)return {path:current,size:info.size};}throw new Error('图片压缩后仍超过 5MB，请换一张图片');},
  inputName(e){this.setData({dishName:e.detail.value})},
  async upload(){if(!this.data.pickedPath)return wx.showToast({title:'先拍一张菜品图吧',icon:'none'});if(!this.data.dishName.trim())return wx.showToast({title:'告诉我们这道菜叫什么',icon:'none'});this.setData({uploading:true});try{await app.upload({url:'/dish-image-submissions',filePath:this.data.pickedPath,formData:{dishName:this.data.dishName.trim()}});this.setData({pickedPath:'',dishName:''});wx.showModal({title:'照片已收下',content:'审核通过后，它会点亮这道菜的实拍图。谢谢你的分享！',showCancel:false});}catch(e){wx.showToast({title:e.message,icon:'none'})}finally{this.setData({uploading:false})}},
  async dice(){try{wx.showLoading({title:'摇一摇…'});const result=await app.request({url:'/dishes/random'});this.setData({randomDish:result.dish,mealLabel:result.mealLabel});}catch(e){wx.showToast({title:e.message,icon:'none'})}finally{wx.hideLoading()}},
  openDish(){wx.navigateTo({url:'/pages/dish/index?id='+this.data.randomDish.id})}
});
