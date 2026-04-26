/* Latest Softwares 前端逻辑（Alpine.js 组件）*/

function app() {
  return {
    // ==== state ====
    query: '',
    activeCategory: 'all',
    activePlatform: 'all',
    dark: false,
    fuse: null,
    packages: [],
    lastUpdated: '—',

    // ==== 生命周期 ====
    init() {
      // 主题：localStorage 优先，否则跟随系统
      const saved = localStorage.getItem('theme');
      if (saved) {
        this.dark = saved === 'dark';
      } else {
        this.dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      }

      // 数据（由 build_web.py 注入）
      const data = window.__PKG_DATA__ || { packages: [], stats: {} };
      // 排序：先按分类（packages.yaml 顺序），再按 name
      this.packages = data.packages || [];

      // 显示最近一次抓取时间（从第一个 fetched_at 取近似值）
      const ts = this.packages
        .map(p => p.fetched_at)
        .filter(Boolean)
        .sort()
        .pop();
      this.lastUpdated = ts ? this.formatDateTime(ts) : '—';

      // Fuse 模糊搜索
      this.fuse = new Fuse(this.packages, {
        keys: [
          { name: 'name',     weight: 0.5 },
          { name: 'id',       weight: 0.3 },
          { name: 'category', weight: 0.15 },
          { name: 'version',  weight: 0.05 },
        ],
        threshold: 0.4,
        ignoreLocation: true,
        minMatchCharLength: 1,
      });
    },

    // ==== 派生状态 ====
    get categories() {
      const set = new Set();
      this.packages.forEach(p => p.category && set.add(p.category));
      return ['all', ...set];
    },

    get platforms() {
      // 检测包内出现的平台前缀，固定常见展示顺序
      const present = new Set();
      this.packages.forEach(p =>
        p.assets?.forEach(a => present.add(a.platform.split('-')[0]))
      );
      const order = [
        { key: 'all',   label: '全部', show: true },
        { key: 'win',   label: 'Windows', show: present.has('win') },
        { key: 'mac',   label: 'macOS',   show: present.has('mac') },
        { key: 'linux', label: 'Linux',   show: present.has('linux') },
      ];
      return order.filter(p => p.show);
    },

    get filtered() {
      let list = this.query.trim()
        ? this.fuse.search(this.query.trim()).map(r => r.item)
        : [...this.packages];

      if (this.activeCategory !== 'all') {
        list = list.filter(p => p.category === this.activeCategory);
      }
      if (this.activePlatform !== 'all') {
        list = list.filter(p =>
          p.assets?.some(a => a.platform.startsWith(this.activePlatform))
        );
      }
      return list;
    },

    // ==== 动作 ====
    toggleDark() {
      this.dark = !this.dark;
      localStorage.setItem('theme', this.dark ? 'dark' : 'light');
    },

    resetFilters() {
      this.query = '';
      this.activeCategory = 'all';
      this.activePlatform = 'all';
      this.$refs.search?.focus();
    },

    // ==== 直链检测 ====
    // 剥掉查询串后看路径是否以文件扩展名结尾
    isDirectLink(url) {
      if (!url) return false;
      const path = url.toLowerCase().split('?')[0];
      return /\.(exe|dmg|iso|zip|tar\.gz|msi|pkg|deb|rpm|appimage|7z)$/.test(path);
    },

    // ==== 平台徽章颜色（direct=实心填充 / page=描边空心） ====
    badgeClass(platform, url) {
      const family = platform.split('-')[0];
      const direct = this.isDirectLink(url);
      const colorMap = {
        win: {
          direct: 'bg-blue-50   text-blue-700  hover:bg-blue-100  dark:bg-blue-950/40  dark:text-blue-300  dark:hover:bg-blue-900/40',
          page:   'ring-1 ring-blue-300   text-blue-600  hover:bg-blue-50   dark:ring-blue-700   dark:text-blue-400  dark:hover:bg-blue-950/30',
        },
        mac: {
          direct: 'bg-zinc-100  text-zinc-700  hover:bg-zinc-200  dark:bg-zinc-800     dark:text-zinc-300  dark:hover:bg-zinc-700',
          page:   'ring-1 ring-zinc-300   text-zinc-600  hover:bg-zinc-100  dark:ring-zinc-600   dark:text-zinc-400  dark:hover:bg-zinc-800/50',
        },
        linux: {
          direct: 'bg-orange-50 text-orange-700 hover:bg-orange-100 dark:bg-orange-950/40 dark:text-orange-300 dark:hover:bg-orange-900/40',
          page:   'ring-1 ring-orange-300 text-orange-600 hover:bg-orange-50 dark:ring-orange-700 dark:text-orange-400 dark:hover:bg-orange-950/30',
        },
      };
      const colors = colorMap[family] || {
        direct: 'bg-violet-50  text-violet-700 hover:bg-violet-100 dark:bg-violet-950/40 dark:text-violet-300 dark:hover:bg-violet-900/40',
        page:   'ring-1 ring-violet-300 text-violet-600 hover:bg-violet-50 dark:ring-violet-700 dark:text-violet-400 dark:hover:bg-violet-950/30',
      };
      return colors[direct ? 'direct' : 'page'];
    },

    // ==== 格式化辅助 ====
    formatDate(iso) {
      if (!iso) return '';
      try {
        const d = new Date(iso.replace('Z', '+00:00'));
        return d.toISOString().slice(0, 10);
      } catch {
        return iso;
      }
    },

    formatDateTime(iso) {
      if (!iso) return '—';
      try {
        const d = new Date(iso.replace('Z', '+00:00'));
        const pad = n => String(n).padStart(2, '0');
        return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`;
      } catch {
        return iso;
      }
    },

    formatSize(bytes) {
      if (!bytes) return '';
      const units = ['B', 'KB', 'MB', 'GB'];
      let i = 0, v = bytes;
      while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
      return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
    },
  };
}
