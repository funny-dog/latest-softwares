/* Latest Softwares frontend logic (Alpine.js component). */

function app() {
  return {
    // ==== state ====
    edition: 'cn',
    query: '',
    activeCategory: 'all',
    activePlatform: 'all',
    dark: false,
    fuse: null,
    packages: [],
    stats: {},
    siteMetrics: { loaded: false, visits: 0, downloads: 0 },
    publicSiteUrl: '',
    lastUpdated: '—',
    directFileExtensions: ['.exe', '.dmg', '.iso', '.zip', '.tar.gz', '.msi', '.pkg', '.deb', '.rpm', '.appimage', '.7z'],

    // ==== i18n dictionary ====
    i18n: {
      cn: {
        all: '全部',
        app_title: 'Latest Softwares',
        status: ({ count, updated }) => `共 ${count} 项 · 最后同步 ${updated}`,
        total_software: '软件总数',
        total_software_value: ({ count }) => `${count} 项`,
        site_visits: '访问',
        site_downloads: '下载',
        site_metrics_title: '当前运行实例的访问与下载点击统计',
        category: '分类',
        platform: '平台',
        result_count: ({ shown, total }) => `显示 ${shown} / ${total} 项`,
        win: 'Windows',
        mac: 'macOS',
        linux: 'Linux',
        search_placeholder: '搜索软件…  (vsc / win11 / chrome / 游戏)',
        theme_light: '浅色模式',
        theme_dark: '深色模式',
        repo_title: '查看源仓库',
        no_results: '未找到匹配软件',
        no_results_hint: '试试其它关键词，或',
        clear_filter: '清除筛选',
        direct_download: ({ platform, size }) => `直链下载 · ${platform}${size ? ` (${size})` : ''}`,
        landing_download: ({ platform }) => `跳转下载页 · ${platform}`,
        release_notes: 'Release Notes →',
        stale: ({ reason }) => `本次抓取失败，复用上次数据${reason ? `：${reason}` : ''}`,
        warnings: ({ warnings }) => warnings.join('；'),
        footer: '由 GitHub Actions 每日同步上游官方源 · 仅记录元数据，不托管二进制',
        version: '版本',
        release_version: '发布版本',
        release_label: '发行标签',
        build_date: '构建日期',
        page_date: '页面日期',
        sync_date: '同步日期',
      },
      intl: {
        all: 'All',
        app_title: 'Latest Softwares',
        status: ({ count, updated }) => `Total ${count} items · Last synced ${updated}`,
        total_software: 'Total',
        total_software_value: ({ count }) => `${count} items`,
        site_visits: 'Visits',
        site_downloads: 'Downloads',
        site_metrics_title: 'Visit and download-click counts for the current running instance',
        category: 'Category',
        platform: 'Platform',
        result_count: ({ shown, total }) => `Showing ${shown} / ${total} items`,
        win: 'Windows',
        mac: 'macOS',
        linux: 'Linux',
        search_placeholder: 'Search apps...  (vscode / chrome / media / ai)',
        theme_light: 'Switch to light mode',
        theme_dark: 'Switch to dark mode',
        repo_title: 'View source repository',
        no_results: 'No matching apps found',
        no_results_hint: 'Try another keyword, or',
        clear_filter: 'clear all filters',
        direct_download: ({ platform, size }) => `Direct download · ${platform}${size ? ` (${size})` : ''}`,
        landing_download: ({ platform }) => `Download page · ${platform}`,
        release_notes: 'Release Notes →',
        stale: () => 'Fetch failed; using the previous successful result',
        warnings: ({ warnings }) => warnings.join('; '),
        footer: 'Synced daily from official upstream sources by GitHub Actions · Metadata only, no binaries hosted',
        version: 'Version',
        release_version: 'Release Version',
        release_label: 'Release Label',
        build_date: 'Build Date',
        page_date: 'Page Date',
        sync_date: 'Sync Date',
      }
    },

    t(key) {
      const dict = this.i18n[this.edition] || this.i18n.cn;
      return dict[key] || key;
    },

    msg(key, values = {}) {
      const value = this.t(key);
      return typeof value === 'function' ? value(values) : value;
    },

    // ==== lifecycle ====
    init() {
      // Theme: localStorage first, then the system preference.
      const saved = localStorage.getItem('theme');
      if (saved) {
        this.dark = saved === 'dark';
      } else {
        this.dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      }

      // Data is injected by build_web.py.
      const data = window.__PKG_DATA__ || { packages: [], stats: {} };
      this.edition = data.edition || 'cn';
      document.documentElement.lang = this.edition === 'intl' ? 'en' : 'zh-CN';
      document.title = this.t('app_title');
      // Keep packages.yaml order so categories remain predictable.
      this.packages = data.packages || [];
      this.stats = data.stats || {};
      this.publicSiteUrl = (data.public_site_url || '').replace(/\/$/, '');
      this.directFileExtensions = data.direct_file_extensions || this.directFileExtensions;
      this.recordVisit();

      // Prefer the top-level generated_at written by sync.py.
      const ts = data.generated_at || this.packages
        .map(p => p.fetched_at)
        .filter(Boolean)
        .sort()
        .pop();
      this.lastUpdated = ts ? this.formatDateTime(ts) : '—';

      // Fuse fuzzy search.
      this.fuse = new Fuse(this.packages, {
        keys: [
          { name: 'name',     weight: 0.45 },
          { name: 'id',       weight: 0.25 },
          { name: 'category', weight: 0.1 },
          { name: 'desc_cn',  weight: 0.1 },
          { name: 'desc_en',  weight: 0.05 },
          { name: 'version',  weight: 0.05 },
        ],
        threshold: 0.4,
        ignoreLocation: true,
        minMatchCharLength: 1,
      });
    },

    // ==== derived state ====
    get categories() {
      const set = new Set();
      this.packages.forEach(p => p.category && set.add(p.category));
      return ['all', ...set];
    },

    getCategoryLabel(c) {
      if (c === 'all') return this.t('all');
      const catI18n = {
        cn: {
          'AI Tools': 'AI 工具',
          'Browsers': '浏览器',
          'Cloud & DevOps': '云服务与运维',
          'Developer Tools': '开发工具',
          'Gaming': '游戏',
          'Media Players': '媒体与创作',
          'Messaging': '通讯',
          'Network & Proxy': '网络与代理',
          'Operating Systems': '操作系统',
          'Productivity': '效率办公',
          'Security & Privacy': '安全与隐私',
          'System Utilities': '系统工具',
          'Utilities': '实用工具',
        },
      };
      return (catI18n[this.edition] || {})[c] || c;
    },

    get platforms() {
      // Detect platform families in a stable display order.
      const present = new Set();
      this.packages.forEach(p =>
        p.assets?.forEach(a => present.add(a.platform.split('-')[0]))
      );
      const order = [
        { key: 'all',   label: this.t('all'), show: true },
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

    // ==== actions ====
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

    downloadUrl(pkg, asset) {
      if (this.edition === 'intl' && this.publicSiteUrl && pkg?.id && asset?.platform) {
        return `${this.publicSiteUrl}/api/download/${encodeURIComponent(pkg.id)}/${encodeURIComponent(asset.platform)}`;
      }
      return asset.url;
    },

    recordVisit() {
      if (this.edition !== 'intl' || !this.publicSiteUrl) return;
      fetch(`${this.publicSiteUrl}/api/visit`, {
        method: 'POST',
        keepalive: true,
      })
        .then(response => response.ok ? response.json() : null)
        .then(payload => {
          const metrics = payload?.metrics || payload;
          if (!this.applySiteMetrics(metrics)) this.fetchSiteMetrics();
        })
        .catch(() => this.fetchSiteMetrics());
    },

    fetchSiteMetrics() {
      if (this.edition !== 'intl' || !this.publicSiteUrl) return;
      fetch(`${this.publicSiteUrl}/api/metrics`)
        .then(response => response.ok ? response.json() : null)
        .then(metrics => this.applySiteMetrics(metrics))
        .catch(() => {});
    },

    applySiteMetrics(metrics) {
      if (!metrics?.visits || !metrics?.downloads) return false;
      this.siteMetrics = {
        loaded: true,
        visits: Number(metrics.visits.total) || 0,
        downloads: Number(metrics.downloads.total) || 0,
      };
      return true;
    },

    noteDownloadClick() {
      if (this.edition !== 'intl' || !this.publicSiteUrl || !this.siteMetrics.loaded) {
        return;
      }
      this.siteMetrics = {
        ...this.siteMetrics,
        downloads: this.siteMetrics.downloads + 1,
      };
    },

    // ==== direct-link detection ====
    // Strip query/hash before checking the file extension.
    isDirectLink(url, linkKind = null) {
      if (linkKind === 'direct') return true;
      if (linkKind === 'landing_page') return false;
      if (!url) return false;
      const path = url.toLowerCase().split(/[?#]/)[0];
      return this.directFileExtensions.some(ext => path.endsWith(ext));
    },

    // ==== platform badge colors (filled=direct, outline=landing page) ====
    badgeClass(platform, url, linkKind = null) {
      const family = platform.split('-')[0];
      const direct = this.isDirectLink(url, linkKind);
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

    statusText() {
      return this.msg('status', { count: this.totalCount(), updated: this.lastUpdated });
    },

    resultCountText() {
      return this.msg('result_count', {
        shown: this.filtered.length,
        total: this.totalCount(),
      });
    },

    totalCount() {
      return Number.isFinite(this.stats.total) ? this.stats.total : this.packages.length;
    },

    totalSoftwareText() {
      return this.msg('total_software_value', { count: this.totalCount() });
    },

    siteMetricsSummary() {
      if (!this.siteMetrics.loaded) return '';
      const visits = this.formatCount(this.siteMetrics.visits);
      const downloads = this.formatCount(this.siteMetrics.downloads);
      return `${this.t('site_visits')} ${visits} · ${this.t('site_downloads')} ${downloads}`;
    },

    themeTitle() {
      return this.dark ? this.t('theme_light') : this.t('theme_dark');
    },

    staleTitle(pkg) {
      if (pkg._stale) {
        return this.msg('stale', { reason: pkg._stale_reason });
      }
      return this.msg('warnings', { warnings: pkg.warnings || [] });
    },

    assetTitle(asset) {
      if (this.isDirectLink(asset.url, asset.link_kind)) {
        return this.msg('direct_download', {
          platform: asset.platform,
          size: asset.size ? this.formatSize(asset.size) : '',
        });
      }
      return this.msg('landing_download', { platform: asset.platform });
    },

    // ==== formatting helpers ====
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

    formatCount(value) {
      const locale = this.edition === 'intl' ? 'en-US' : 'zh-CN';
      return new Intl.NumberFormat(locale).format(Number(value) || 0);
    },

    versionKindLabel(kind) {
      return this.t(kind) || this.t('version');
    },

    // 根据当前 edition 返回对应语言的描述
    editionDesc(pkg) {
      if (this.edition === 'intl') return pkg.desc_en || pkg.desc_cn || '';
      return pkg.desc_cn || pkg.desc_en || '';
    },

    // 从 homepage 提取 favicon.im 图标 URL
    faviconUrl(homepage) {
      if (!homepage) return '';
      try {
        return `https://favicon.im/${new URL(homepage).hostname}`;
      } catch {
        return '';
      }
    },
  };
}
