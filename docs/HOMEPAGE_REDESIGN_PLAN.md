# Hacker News 首页重设计计划

状态：待实施  
范围：仅重设计 `/hackernews/` 首页；Daily、Weekly、Monthly、Favorites 等内容页暂不改动。  
原则：提高视觉品质和导航效率，同时保持高信息密度、静态部署、低维护成本与现有 URL 稳定。

## 1. 背景与问题

当前首页功能完整，包含今日新闻、搜索、统计、周归档、月度摘要、Favorites、Trends 和 RSS，但存在以下体验问题：

- 所有模块基本沿单栏纵向排列，视觉层级相近，首页显得冗长。
- 顶部缺少明确的品牌区域和主要操作入口。
- 历史归档数量越来越多，用户不容易快速跳到某个月或某一周。
- Weekly 与 Monthly 信息都在正文中展开，页面可扫描性不足。
- 当前视觉更像自动生成的报告，还没有形成独立技术新闻站的品牌感。

## 2. 设计目标

1. 建立现代、克制的技术期刊/数据面板风格。
2. 首屏提供足够信息，不采用占据整屏但内容稀少的 Hero。
3. 保持 Top Stories 的高密度阅读体验。
4. 在桌面端提供可快速定位 Month/Week 的归档导航。
5. 在移动端保持清楚、易操作，不强行保留双栏。
6. 保留现有功能、内容、URL、收藏数据及自动生成流程。
7. 不引入 React、数据库或新的前端构建系统。

## 3. 推荐视觉方向

风格名称：**Modern Editorial Dashboard**。

- 背景使用轻微偏暖的灰白色，深色模式使用低对比度深灰。
- 主色保留 Hacker News 橙色，只用于关键强调、状态和链接。
- 标题使用现代无衬线字体；日期、分数和元数据可使用等宽字体。
- 减少厚重阴影，主要依靠细边框、留白和轻微背景层次区分区域。
- 控制圆角尺寸，避免所有元素都像大型 SaaS 卡片。
- 动效以 150–250ms 的 hover、折叠和定位反馈为主，不使用装饰性大动画。

## 4. 信息架构

### 4.1 紧凑 Header

Header 高度保持紧凑，建议包含：

- Hacker News Daily 品牌标题。
- 一句简短定位，例如 `AI-curated technology news, twice daily.`。
- 最近更新时间、当前 edition 和 story 数量。
- 搜索框。
- Favorites、Trends、RSS 快捷入口。

Header 可以使用非常淡的橙色渐变或技术网格纹理，但不能影响文字可读性。

### 4.2 桌面端双栏主体

建议使用约 `minmax(0, 1fr) + 260–300px` 的布局：

- 主栏：Today's Top Stories 与 News Archive。
- 右栏：Sticky Archive Navigation，以及可选的 Topics 快捷入口。

主内容宽度仍应足够展示较长的双语标题；整体页面最大宽度可从当前 920px 增加到约 1180–1240px。

### 4.3 Today's Top Stories

- 保留排名、英文标题、中文标题、热度、分数、评论数和标签。
- 保持紧凑列表，不改成大面积图片新闻卡。
- 前三名可通过更明显的排名或轻微背景进行区分，但尺寸不应显著增大。
- 保留 Show more/Show less。
- 保留当前标题进入 Daily 页面、原始新闻链接等行为。

### 4.4 Sticky Archive Navigation

右侧导航按 Year → Month → Week 组织：

- 当前年份和当前月份默认展开。
- 过去月份默认折叠。
- 点击月份或周，平滑滚动到主栏中对应的 archive section。
- 页面滚动时，当前可见 Month/Week 自动高亮。
- 提供 `Back to current week` 快捷入口。
- 可在下方加入热门标签，例如 AI、Programming、Security、Privacy。

右栏只承担导航职责，不复制完整的 Daily/Weekly/Monthly 内容。

### 4.5 News Archive 主栏

- 当前周默认展开。
- 其他周默认折叠，保持现有交互。
- Monthly Digest 继续作为月份之间的视觉分隔，但改成更精炼的 summary strip。
- 为每个 Month 和 Week 输出稳定的 DOM `id`，供右侧导航和深链接使用。
- 保留所有历史记录，不截断过去月份。

### 4.6 移动端

当视口小于约 800px：

- 回到单栏布局。
- Sticky Sidebar 变为 `Browse Archive` 按钮。
- 点击后打开下拉面板或侧边抽屉。
- Header 快捷入口允许换行，但主要搜索框保持完整宽度。
- 所有按钮至少保留约 44px 的可点击区域。
- 不依赖 hover 才能发现或使用功能。

## 5. 功能与兼容性约束

必须保持：

- `/hackernews/` 及全部既有 URL 不变。
- Favorites 的 localStorage key 与收藏数据不变。
- Search、Trends、RSS、Favorites 行为不变。
- Today 标题、日期、Morning 50/All 100 等生成逻辑不变。
- Weekly/Monthly/Daily 页面模板不受本阶段影响。
- 自动抓取后生成的首页必须继续使用新布局。
- Light/Dark mode 均可读。
- 键盘用户可以操作 archive navigation 和折叠控件。
- `prefers-reduced-motion` 下关闭非必要滚动和过渡动画。

## 6. 建议实施阶段

### Phase 1：结构与设计 Token

- 为首页增加专用 wrapper、header、main grid 和 sidebar 结构。
- 整理首页颜色、宽度、间距、边框和字体 token。
- 不改变新闻数据和现有交互。

### Phase 2：Archive Navigation

- 在生成器中为 Month/Week 添加稳定 anchor。
- 根据现有归档数据生成 Year/Month/Week 导航。
- 实现滚动定位、当前 section 高亮和桌面 sticky 行为。

### Phase 3：移动端与可访问性

- 实现移动端 Browse Archive 面板。
- 补齐 ARIA 状态、键盘操作、focus 样式和 reduced-motion。

### Phase 4：视觉细化

- 调整 Top Stories 排名、元数据和标签层级。
- 细化 Monthly strip、Week row、空白与 hover 状态。
- 同时检查浅色和深色模式。

### Phase 5：验证与发布

- 本地生成首页并进行桌面、窄屏和移动端检查。
- 确认搜索、归档折叠、Favorites 链接、RSS、Today 链接均正常。
- 推送后等待自动 Pages 部署成功。
- 对比生产首页与本地结果，并检查旧 URL。

## 7. 预计涉及文件

- `news_scraper/index_updater.py`
  - 输出新版首页结构、sidebar 数据和 Month/Week anchor。
- `assets/hn/hn.css`
  - 新增首页 grid、header、sidebar、响应式和视觉样式。
- `assets/hn/hn.js`
  - Archive navigation、scroll spy、移动端面板等轻量交互。
- `hackernews/index.md`
  - 更新当前已生成首页，确保部署后立即看到新版效果。

如无必要，不修改 `_layouts/hn.html`；Daily、Weekly、Monthly 和 Favorites 的生成代码不在本阶段范围内。

## 8. 验收标准

- 桌面端首屏能同时看到 Header、Today 标题和多条新闻。
- 桌面端右侧可直接跳到任意已有月份和周。
- 当前 Month/Week 随滚动正确高亮。
- 移动端没有横向滚动，Archive 面板可以打开、定位并关闭。
- 首页保留全部现有归档入口和统计信息。
- Search、Favorites、Trends、RSS 和 Today 链接均正常。
- 浅色、深色模式的文字和交互控件对比度足够。
- Daily、Weekly、Monthly、Favorites 页面没有视觉或行为回归。
- 自动任务下一次更新首页后，新结构不会被旧生成器覆盖。
- GitHub Pages 构建和部署成功。

## 9. 风险与控制

- **生成文件被覆盖**：必须先修改 `index_updater.py`，再同步当前 `index.md`。
- **右栏过长**：月份默认折叠，只展开当前月份，并限制 sidebar 可滚动区域。
- **主栏被压窄**：页面最大宽度增加，sidebar 固定在合理范围内。
- **移动端拥挤**：小屏不显示常驻 sidebar，改为抽屉/下拉。
- **全局样式污染内容页**：所有新增样式挂在首页专用 class 下。
- **一次改动过大**：按 Phase 提交；每个阶段都保持页面可用。

## 10. 回滚方案

- 每个 Phase 使用独立 commit。
- 发布前保留当前生产 commit 作为基线。
- 如果新版存在严重问题，可 revert 首页重设计 commits；生成数据与 URL 不需要回滚。
- 不修改新闻 JSON 数据，因此视觉回滚不会影响内容历史。

## 11. 暂不纳入本轮的事项

- Daily、Weekly、Monthly、Favorites 页面整体换肤。
- 新域名或托管方式调整。
- 用户账号、服务器端收藏或数据库。
- 大量图片型首页或全屏 Hero。
- React/Vue 等框架迁移。

这些事项可以在新版首页稳定后单独评估。
