/* HotPulse 热点看板：读取静态 JSON，原生 JS 渲染，不依赖第三方运行时。 */
(() => {
  'use strict';

  const root = document.getElementById('hotpulse-dashboard');
  if (!root) return;

  const dataUrl = root.dataset.src;
  const numberFormat = new Intl.NumberFormat('zh-CN');
  const state = {
    data: null,
    platform: 'all',
    query: '',
    sort: 'score',
    visible: 24,
  };

  const TREND_LABELS = {
    new: '新上榜',
    rising: '升温',
    steady: '持平',
    falling: '降温',
  };

  function $(selector, scope = root) {
    return scope.querySelector(selector);
  }

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }

  function setText(selector, text) {
    const target = $(selector);
    if (target) target.textContent = String(text);
  }

  function dateValue(value) {
    if (!value) return null;
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function clock(value) {
    const date = dateValue(value);
    if (!date) return '时间未知';
    return new Intl.DateTimeFormat('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(date);
  }

  function relative(value) {
    const date = dateValue(value);
    if (!date) return '';
    const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000));
    if (minutes < 2) return '刚刚';
    if (minutes < 60) return `${minutes} 分钟前`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours} 小时前`;
    return `${Math.round(hours / 24)} 天前`;
  }

  function compact(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
    const number = Number(value);
    if (number >= 100000000) return `${(number / 100000000).toFixed(1).replace(/\.0$/, '')} 亿`;
    if (number >= 10000) return `${(number / 10000).toFixed(1).replace(/\.0$/, '')} 万`;
    return numberFormat.format(Math.round(number));
  }

  function platformByKey(data, key) {
    return (data.platforms || []).find((item) => item.key === key) || {};
  }

  function safeUrl(value) {
    try {
      const url = new URL(value, window.location.href);
      return ['http:', 'https:'].includes(url.protocol) ? url.href : '#';
    } catch (_) {
      return '#';
    }
  }

  function errorState(message) {
    root.innerHTML = '';
    const box = node('div', 'hp-error');
    box.textContent = message;
    root.appendChild(box);
    root.classList.add('is-ready');
  }

  function init() {
    if (!dataUrl) {
      errorState('热点看板缺少数据地址（data-src）。');
      return;
    }
    fetch(dataUrl, { cache: 'no-cache' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (!data || data.schema_version !== 1 || !Array.isArray(data.topics)) {
          throw new Error('数据格式不受支持');
        }
        state.data = data;
        render();
        root.classList.add('is-ready');
      })
      .catch((error) => {
        console.error('HotPulse dashboard:', error);
        errorState(`热点数据暂时无法载入。请先生成 assets/data/hotpulse.json，再刷新页面。`);
      });
  }

  function render() {
    const { data } = state;
    renderHero(data);
    renderFilters(data);
    renderKpis(data);
    renderDistribution(data);
    renderTrends(data);
    renderCategories(data);
    renderKeywords(data);
    renderClusters(data);
    renderPlatformCards(data);
    renderRanking();
    bindControls();
  }

  function renderHero(data) {
    const generated = data.generated_at;
    const through = data.data_through || generated;
    setText('[data-hp-updated]', `快照 ${clock(generated)} · ${relative(generated)}`);
    const updated = $('[data-hp-updated]');
    if (updated) updated.title = generated || '';
    setText('[data-hp-window]', `数据截至 ${clock(through)}`);
    setText('[data-hp-count]', `${numberFormat.format(data.topics.length)} 条热点 · ${data.stats.active_platforms}/${data.stats.platforms} 个平台`);
    setText('[data-hp-radar-count]', numberFormat.format(data.topics.length));
  }

  function renderFilters(data) {
    const container = $('[data-hp-filters]');
    if (!container) return;
    container.innerHTML = '';
    const all = filterButton('all', '全部', data.topics.length, null);
    container.appendChild(all);
    (data.platforms || []).forEach((platform) => {
      if (!platform.enabled) return;
      container.appendChild(
        filterButton(platform.key, platform.short || platform.label, platform.count, platform.color),
      );
    });
  }

  function filterButton(key, label, count, color) {
    const button = node('button', 'hp-chip');
    button.type = 'button';
    button.dataset.platform = key;
    button.setAttribute('aria-pressed', String(state.platform === key));
    button.style.setProperty('--dot', color || 'var(--hp-accent)');
    button.appendChild(node('span', 'hp-chip-dot'));
    button.appendChild(node('span', '', label));
    button.appendChild(node('span', 'hp-chip-count', numberFormat.format(count)));
    button.addEventListener('click', () => {
      state.platform = key;
      state.visible = 24;
      root.querySelectorAll('[data-platform]').forEach((item) => {
        if (item.classList.contains('hp-chip')) {
          item.setAttribute('aria-pressed', String(item.dataset.platform === key));
        }
      });
      renderRanking();
    });
    return button;
  }

  function renderKpis(data) {
    setText('[data-hp-kpi="platforms"]', data.stats.active_platforms);
    setText('[data-hp-kpi-note="platforms"]', `共 ${data.stats.platforms} 个来源`);
    setText('[data-hp-kpi="topics"]', numberFormat.format(data.stats.topics));
    setText('[data-hp-kpi-note="topics"]', '最新一轮去重后');
    setText('[data-hp-kpi="score"]', Number(data.stats.average_score || 0).toFixed(1));
    setText('[data-hp-kpi-note="score"]', `最高 ${Number(data.stats.max_score || 0).toFixed(1)} / 100`);
    setText('[data-hp-kpi="clusters"]', data.clusters.length);
    setText('[data-hp-kpi-note="clusters"]', data.clusters.length ? '跨平台同题' : '本轮暂无共振');
  }

  function renderDistribution(data) {
    const donut = $('[data-hp-donut]');
    const legend = $('[data-hp-legend]');
    const total = $('[data-hp-donut-total]');
    if (!donut || !legend) return;
    const active = (data.platforms || []).filter((item) => item.count > 0);
    const sum = active.reduce((acc, item) => acc + item.count, 0);
    if (total) total.textContent = numberFormat.format(sum);

    if (!sum) {
      donut.style.background = 'var(--hp-line)';
      legend.innerHTML = '';
      legend.appendChild(node('li', 'hp-empty', '暂无平台数据'));
      return;
    }

    let cursor = 0;
    const stops = active.map((item) => {
      const start = (cursor / sum) * 100;
      cursor += item.count;
      const end = (cursor / sum) * 100;
      return `${item.color} ${start.toFixed(2)}% ${end.toFixed(2)}%`;
    });
    donut.style.background = `conic-gradient(from -90deg, ${stops.join(', ')})`;
    legend.innerHTML = '';
    active.forEach((item) => {
      const row = node('li');
      const label = node('span', 'hp-legend-label', item.short || item.label);
      label.style.setProperty('--dot', item.color);
      row.appendChild(label);
      row.appendChild(node('b', '', `${numberFormat.format(item.count)} · ${Math.round((item.count / sum) * 100)}%`));
      legend.appendChild(row);
    });
  }

  function renderTrends(data) {
    const container = $('[data-hp-trends]');
    if (!container) return;
    container.innerHTML = '';
    const total = data.topics.length || 1;
    Object.entries(TREND_LABELS).forEach(([key, label]) => {
      const count = Number(data.trends[key] || 0);
      const row = node('div', 'hp-trend-item');
      row.dataset.trend = key;
      row.appendChild(node('strong', '', label));
      const track = node('div', 'hp-trend-track');
      const fill = node('i');
      fill.style.width = `${Math.max(count ? 3 : 0, (count / total) * 100)}%`;
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(node('em', '', numberFormat.format(count)));
      container.appendChild(row);
    });
  }

  function renderCategories(data) {
    const container = $('[data-hp-categories]');
    if (!container) return;
    container.innerHTML = '';
    const categories = (data.categories || []).slice(0, 8);
    if (!categories.length) {
      container.appendChild(node('p', 'hp-empty', '暂无分类数据'));
      return;
    }
    const max = Math.max(...categories.map((item) => item.count), 1);
    categories.forEach((item, index) => {
      const row = node('li', 'hp-cat-item');
      row.appendChild(node('span', '', item.label));
      const track = node('div', 'hp-cat-track');
      const fill = node('i');
      fill.style.width = `${Math.max(3, (item.count / max) * 100)}%`;
      fill.style.opacity = String(Math.max(0.4, 1 - index * 0.08));
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(node('b', '', item.count));
      container.appendChild(row);
    });
  }

  function renderKeywords(data) {
    const container = $('[data-hp-keywords]');
    if (!container) return;
    container.innerHTML = '';
    const keywords = (data.keywords || []).slice(0, 24);
    if (!keywords.length) {
      container.appendChild(node('p', 'hp-empty', '重复主题还不够多，暂时提炼不出关键词。'));
      return;
    }
    const max = Math.max(...keywords.map((item) => Number(item.score) || 0), 1);
    keywords.forEach((item) => {
      const chip = node('span', 'hp-keyword');
      const ratio = Number(item.score || 0) / max;
      chip.style.setProperty('--kw-size', `${(0.68 + ratio * 0.34).toFixed(2)}rem`);
      chip.title = `出现 ${item.count} 次 · ${item.platforms.map((key) => platformByKey(data, key).short || key).join(' / ')}`;
      chip.appendChild(node('span', '', item.term));
      chip.appendChild(node('small', '', `×${item.count}`));
      const dots = node('span', 'hp-keyword-dots');
      (item.platforms || []).forEach((key) => {
        const dot = node('i');
        dot.style.setProperty('--dot', platformByKey(data, key).color || 'var(--hp-accent)');
        dots.appendChild(dot);
      });
      chip.appendChild(dots);
      container.appendChild(chip);
    });
  }

  function renderClusters(data) {
    const container = $('[data-hp-clusters]');
    if (!container) return;
    container.innerHTML = '';
    if (!data.clusters.length) {
      container.appendChild(
        node('p', 'hp-empty', '本轮没有发现跨平台同题。等两个以上平台同时推同一件事，它会出现在这里。'),
      );
      return;
    }
    data.clusters.forEach((cluster) => {
      const card = node('article', 'hp-cluster');
      const head = node('div', 'hp-cluster-head');
      head.appendChild(node('strong', '', cluster.title));
      head.appendChild(node('span', '', Number(cluster.score).toFixed(1)));
      card.appendChild(head);
      const members = node('div', 'hp-cluster-members');
      cluster.members.forEach((member) => {
        const tag = node('span', '', member.platform_label || member.platform);
        tag.style.setProperty('--dot', member.platform_color || 'var(--hp-accent)');
        tag.title = member.title || '';
        members.appendChild(tag);
      });
      card.appendChild(members);
      container.appendChild(card);
    });
  }

  function renderPlatformCards(data) {
    const container = $('[data-hp-platforms]');
    if (!container) return;
    container.innerHTML = '';
    (data.platforms || []).forEach((platform) => {
      const card = node('article', 'hp-platform-card');
      const head = node('div', 'hp-platform-card-head');
      const name = node('span', 'hp-platform-name', platform.short || platform.label);
      name.style.setProperty('--dot', platform.color);
      head.appendChild(name);
      const status = node('span', 'hp-status', statusLabel(platform));
      status.dataset.status = platform.last_run ? platform.last_run.status : 'none';
      head.appendChild(status);
      card.appendChild(head);
      if (platform.top && platform.top.length) {
        const list = node('ol', 'hp-platform-top');
        platform.top.slice(0, 3).forEach((topic) => {
          const item = node('li');
          item.appendChild(node('span', '', `#${topic.rank}`));
          const link = node('a', '', topic.title);
          link.href = safeUrl(topic.url);
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          item.appendChild(link);
          list.appendChild(item);
        });
        card.appendChild(list);
      } else {
        const message = platform.key === 'reddit' ? '需要 OAuth 凭据后接入' : '本轮没有采集到条目';
        card.appendChild(node('p', 'hp-platform-empty', message));
      }
      container.appendChild(card);
    });
  }

  function statusLabel(platform) {
    if (!platform.last_run) return platform.count ? '快照' : '暂无';
    if (platform.last_run.status === 'success') return '正常';
    if (platform.last_run.status === 'failed') return '待接入';
    if (platform.last_run.status === 'empty') return '空结果';
    return platform.last_run.status;
  }

  function filteredTopics() {
    const { data } = state;
    const query = state.query.trim().toLocaleLowerCase('zh-CN');
    let topics = data.topics.filter((topic) => {
      if (state.platform !== 'all' && topic.platform !== state.platform) return false;
      if (!query) return true;
      return `${topic.title} ${topic.category_label} ${topic.platform_short}`.toLocaleLowerCase('zh-CN').includes(query);
    });
    topics = topics.slice();
    if (state.sort === 'rank') {
      topics.sort((a, b) => a.rank - b.rank || b.score - a.score);
    } else if (state.sort === 'heat') {
      topics.sort((a, b) => (b.hot_value || 0) - (a.hot_value || 0) || b.score - a.score);
    } else {
      topics.sort((a, b) => b.score - a.score || a.rank - b.rank);
    }
    return topics;
  }

  function renderRanking() {
    const list = $('[data-hp-ranking]');
    const more = $('[data-hp-more]');
    const count = $('[data-hp-result-count]');
    if (!list) return;
    const topics = filteredTopics();
    if (count) count.textContent = `${numberFormat.format(topics.length)} 条`;
    list.innerHTML = '';

    if (!topics.length) {
      list.appendChild(node('li', 'hp-empty', '没有匹配的热点。试试清空搜索或切换平台。'));
      if (more) more.hidden = true;
      return;
    }

    topics.slice(0, state.visible).forEach((topic, index) => {
      list.appendChild(rankRow(topic, index + 1));
    });

    if (more) {
      const remaining = topics.length - state.visible;
      more.hidden = remaining <= 0;
      more.textContent = remaining > 0 ? `继续展开 · 还有 ${numberFormat.format(remaining)} 条` : '';
    }
  }

  function rankRow(topic, position) {
    const row = node('li', 'hp-rank-row');
    row.appendChild(node('span', 'hp-rank-no', String(position).padStart(2, '0')));

    const main = node('div', 'hp-rank-main');
    const title = node('div', 'hp-rank-title');
    const link = node('a', '', topic.title);
    link.href = safeUrl(topic.url);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.title = topic.title;
    title.appendChild(link);
    const trend = node('span', 'hp-trend', topic.trend_label || TREND_LABELS[topic.trend] || '—');
    trend.dataset.trend = topic.trend;
    title.appendChild(trend);
    main.appendChild(title);

    const meta = node('div', 'hp-rank-meta');
    const platform = node('span', 'hp-platform', topic.platform_short || topic.platform_label);
    platform.style.setProperty('--dot', topic.platform_color || 'var(--hp-accent)');
    meta.appendChild(platform);
    meta.appendChild(node('span', '', `#${topic.rank}`));
    if (topic.hot_value !== null && topic.hot_value !== undefined) {
      meta.appendChild(node('span', '', `热度 ${compact(topic.hot_value)}`));
    }
    meta.appendChild(node('span', 'hp-cat', topic.category_label || '其他'));
    main.appendChild(meta);
    row.appendChild(main);

    const score = node('div', 'hp-score');
    score.appendChild(node('strong', '', Number(topic.score).toFixed(1)));
    const bar = node('div', 'hp-score-bar');
    const fill = node('i');
    fill.style.width = `${Math.max(2, Math.min(100, Number(topic.score) || 0))}%`;
    bar.appendChild(fill);
    score.appendChild(bar);
    row.appendChild(score);
    return row;
  }

  function bindControls() {
    const search = $('[data-hp-search]');
    if (search) {
      search.addEventListener('input', () => {
        state.query = search.value;
        state.visible = 24;
        renderRanking();
      });
    }
    const sort = $('[data-hp-sort]');
    if (sort) {
      sort.addEventListener('change', () => {
        state.sort = sort.value;
        state.visible = 24;
        renderRanking();
      });
    }
    const more = $('[data-hp-more]');
    if (more) {
      more.addEventListener('click', () => {
        state.visible += 24;
        renderRanking();
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
