// 底部导航高亮
(function() {
    var path = window.location.pathname;
    var items = document.querySelectorAll('.bottom-nav-item');
    items.forEach(function(item) {
        var href = item.getAttribute('href');
        if (href === path || (href !== '/' && path.startsWith(href))) {
            item.classList.add('active');
        }
    });
})();

// 搜索框：回车提交
document.addEventListener('DOMContentLoaded', function() {
    var searchInput = document.querySelector('.search-input');
    if (searchInput) {
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                var q = searchInput.value.trim();
                if (q) {
                    window.location.href = '/search?q=' + encodeURIComponent(q);
                }
            }
        });
    }

    // 社区发帖：菜品模糊搜索
    var dishSearch = document.getElementById('dish-search');
    var dishHidden = document.getElementById('dish-name-hidden');
    var suggBox = document.getElementById('dish-suggestions');

    if (dishSearch && suggBox) {
        var timer = null;
        dishSearch.addEventListener('input', function() {
            clearTimeout(timer);
            var q = dishSearch.value.trim();
            if (!q) {
                suggBox.style.display = 'none';
                dishHidden.value = '';
                return;
            }
            timer = setTimeout(function() {
                fetch('/api/dishes/search?q=' + encodeURIComponent(q))
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        suggBox.innerHTML = '';
                        if (!data.dishes || data.dishes.length === 0) {
                            suggBox.style.display = 'none';
                            return;
                        }
                        data.dishes.forEach(function(d) {
                            var div = document.createElement('div');
                            div.className = 'sugg-item';
                            div.textContent = d.name + ' (' + d.stall_name + ') ¥' + d.price;
                            div.addEventListener('click', function() {
                                dishSearch.value = d.name;
                                dishHidden.value = d.name;
                                suggBox.style.display = 'none';
                            });
                            suggBox.appendChild(div);
                        });
                        suggBox.style.display = 'block';
                    });
            }, 200);
        });

        // 点击其他地方关闭下拉
        document.addEventListener('click', function(e) {
            if (!dishSearch.contains(e.target) && !suggBox.contains(e.target)) {
                suggBox.style.display = 'none';
            }
        });
    }
});
