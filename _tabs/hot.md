---
icon: fas fa-fire
order: 2
---

<link rel="stylesheet" href="{{ '/assets/css/hotpulse.css' | relative_url }}">

<div class="hp-shell" id="hotpulse-dashboard" data-src="{{ '/assets/data/hotpulse.json' | relative_url }}">
  <section class="hp-hero" aria-labelledby="hp-title">
    <div class="hp-hero-copy">
      <p class="hp-kicker">
        <span class="hp-pulse" aria-hidden="true"></span>
        HOTPULSE / 跨平台热点快照
      </p>
      <h1 id="hp-title">此刻，<em>大家在聊什么</em>？</h1>
      <p class="hp-lead">
        把 B站、知乎、抖音、贴吧、GitHub 和 Reddit 的公开榜单收进同一张桌面。
        不追逐实时，只记录这个时刻，哪些话题正在被反复提起。
      </p>
      <div class="hp-hero-meta">
        <span>
          <i class="fas fa-clock" aria-hidden="true"></i>
          <span data-hp-updated>正在读取快照…</span>
        </span>
        <span>
          <i class="fas fa-database" aria-hidden="true"></i>
          <span data-hp-window>数据截至 —</span>
        </span>
        <span>
          <i class="fas fa-layer-group" aria-hidden="true"></i>
          <span data-hp-count>— 条热点</span>
        </span>
      </div>
    </div>

    <div class="hp-radar" aria-hidden="true">
      <span class="hp-radar-node" style="--node:#00a1d6">B站</span>
      <span class="hp-radar-node" style="--node:#056de8">知乎</span>
      <span class="hp-radar-node" style="--node:#fe2c55">抖音</span>
      <span class="hp-radar-node" style="--node:#4e6ef2">贴吧</span>
      <span class="hp-radar-node" style="--node:#8b5cf6">GitHub</span>
      <span class="hp-radar-node" style="--node:#ff4500">Reddit</span>
      <div class="hp-radar-core">
        <strong data-hp-radar-count>—</strong>
        <small>HOT TOPICS</small>
      </div>
    </div>
  </section>

  <div class="hp-toolbar">
    <div class="hp-filters" data-hp-filters role="group" aria-label="按平台筛选"></div>
    <label class="hp-search">
      <i class="fas fa-magnifying-glass" aria-hidden="true"></i>
      <input type="search" data-hp-search placeholder="搜索标题、分类或平台…" aria-label="搜索热点" autocomplete="off">
    </label>
    <label class="hp-sort">
      <span>排序</span>
      <select data-hp-sort aria-label="热点排序">
        <option value="score">综合分</option>
        <option value="rank">平台排名</option>
        <option value="heat">热度值</option>
      </select>
    </label>
  </div>

  <section class="hp-kpis" aria-label="热点概况">
    <article class="hp-kpi">
      <span class="hp-kpi-label">活跃平台</span>
      <p class="hp-kpi-value"><span data-hp-kpi="platforms">—</span><small>/ 6</small></p>
      <p class="hp-kpi-note" data-hp-kpi-note="platforms">六个来源</p>
    </article>
    <article class="hp-kpi">
      <span class="hp-kpi-label">收录热点</span>
      <p class="hp-kpi-value" data-hp-kpi="topics">—</p>
      <p class="hp-kpi-note" data-hp-kpi-note="topics">最新一轮去重后</p>
    </article>
    <article class="hp-kpi">
      <span class="hp-kpi-label">平均 HotScore</span>
      <p class="hp-kpi-value"><span data-hp-kpi="score">—</span><small>分</small></p>
      <p class="hp-kpi-note" data-hp-kpi-note="score">满分 100</p>
    </article>
    <article class="hp-kpi">
      <span class="hp-kpi-label">跨平台同题</span>
      <p class="hp-kpi-value" data-hp-kpi="clusters">—</p>
      <p class="hp-kpi-note" data-hp-kpi-note="clusters">共振话题</p>
    </article>
  </section>

  <div class="hp-layout">
    <section class="hp-panel" aria-labelledby="hp-ranking-title">
      <div class="hp-panel-head">
        <h2 class="hp-panel-title" id="hp-ranking-title">热点榜单</h2>
        <span class="hp-panel-sub"><span data-hp-result-count>—</span> · 可搜索、筛选与排序</span>
      </div>
      <ol class="hp-ranking" data-hp-ranking></ol>
      <button class="hp-more" type="button" data-hp-more hidden>继续展开</button>
    </section>

    <aside class="hp-aside" aria-label="平台与趋势">
      <section class="hp-panel" aria-labelledby="hp-platform-mix-title">
        <div class="hp-panel-head">
          <h2 class="hp-panel-title" id="hp-platform-mix-title">平台声量</h2>
          <span class="hp-panel-sub">按收录条数</span>
        </div>
        <div class="hp-panel-body">
          <div class="hp-donut-wrap">
            <div class="hp-donut" data-hp-donut>
              <div class="hp-donut-hole">
                <strong data-hp-donut-total>—</strong>
                <small>条热点</small>
              </div>
            </div>
            <ul class="hp-legend" data-hp-legend></ul>
          </div>
        </div>
      </section>

      <section class="hp-panel" aria-labelledby="hp-trend-title">
        <div class="hp-panel-head">
          <h2 class="hp-panel-title" id="hp-trend-title">趋势温度</h2>
          <span class="hp-panel-sub">对比上一轮</span>
        </div>
        <div class="hp-panel-body">
          <div class="hp-trend-list" data-hp-trends></div>
        </div>
      </section>
    </aside>
  </div>

  <section class="hp-panel" aria-labelledby="hp-spectrum-title" style="margin-top:0.95rem">
    <div class="hp-panel-head">
      <h2 class="hp-panel-title" id="hp-spectrum-title">话题光谱</h2>
      <span class="hp-panel-sub">分类分布与高频词</span>
    </div>
    <div class="hp-panel-body">
      <div class="hp-split">
        <div>
          <h3 class="hp-subhead">分类分布</h3>
          <ul class="hp-cat-list" data-hp-categories></ul>
        </div>
        <div>
          <h3 class="hp-subhead">高频词</h3>
          <div class="hp-cloud" data-hp-keywords></div>
        </div>
      </div>
    </div>
  </section>

  <section class="hp-panel" aria-labelledby="hp-cluster-title" style="margin-top:0.95rem">
    <div class="hp-panel-head">
      <h2 class="hp-panel-title" id="hp-cluster-title">跨平台共振</h2>
      <span class="hp-panel-sub">同一件事，不止一个平台在说</span>
    </div>
    <div class="hp-panel-body">
      <div class="hp-clusters" data-hp-clusters></div>
    </div>
  </section>

  <section class="hp-panel" aria-labelledby="hp-platform-title" style="margin-top:0.95rem">
    <div class="hp-panel-head">
      <h2 class="hp-panel-title" id="hp-platform-title">平台脉搏</h2>
      <span class="hp-panel-sub">各平台前三与采集状态</span>
    </div>
    <div class="hp-panel-body">
      <div class="hp-platform-grid" data-hp-platforms></div>
    </div>
  </section>

  <footer class="hp-footer">
    <span>HotPulse 0.1.0 · 分层热点聚合 · 数据来自平台公开榜单</span>
    <span>快照按采集时点计 · 非实时行情</span>
  </footer>
</div>

<noscript>
  <p style="margin-top:1rem;color:#726d63">热点看板需要 JavaScript 才能渲染。静态数据位于 <code>/assets/data/hotpulse.json</code>。</p>
</noscript>

<script defer src="{{ '/assets/js/hotpulse.js' | relative_url }}"></script>
