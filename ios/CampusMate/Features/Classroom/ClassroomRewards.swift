import Foundation

/// 上游课堂 WebView 里的游戏化 HUD（页面 XP 与等级步长和 Web 原生课堂一致；
/// 连击按课堂页面连续浏览计算，Web 原生课堂的连击按测验连续答对计算）。
enum ClassroomRewards {
    static let script = #"""
    (function () {
      if (window.__campusRewards) return;
      window.__campusRewards = true;
      var KEY = 'campusmate:classroom-rewards:v1';
      var state;
      try { state = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (_) { state = null; }
      if (!state || typeof state !== 'object') state = {};
      state.xp = Number(state.xp) > 0 ? Number(state.xp) : 0;
      state.combo = Number(state.combo) > 0 ? Number(state.combo) : 0;
      state.bestCombo = Number(state.bestCombo) > 0 ? Number(state.bestCombo) : 0;
      state.pages = Array.isArray(state.pages) ? state.pages : [];
      state.achievements = Array.isArray(state.achievements) ? state.achievements : [];
      state.labels = state.labels && typeof state.labels === 'object' ? state.labels : {};
      state.lastTitle = state.lastTitle || '';
      state.lastAt = Number(state.lastAt) || 0;
      var level = function () { return 1 + Math.floor(state.xp / 100); };
      var save = function () { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (_) {} };
      var award = function (id, label) {
        if (state.achievements.indexOf(id) >= 0) return;
        state.achievements.push(id);
        state.labels[id] = label;
      };
      var title = function () {
        var node = document.querySelector('h1, [class*="text-xl"][class*="font-bold"]');
        var text = node && node.textContent ? node.textContent.trim() : '';
        return text || document.title || location.pathname;
      };
      function render() {
        var root = document.getElementById('campus-rewards');
        if (!root) {
          root = document.createElement('div');
          root.id = 'campus-rewards';
          document.body.appendChild(root);
        }
        var badges = state.achievements.map(function (id) {
          return '<span class="cr-badge">' + (state.labels[id] || id) + '</span>';
        }).join('');
        root.innerHTML = '<button id="campus-rewards-toggle" type="button">' +
          '<span class="cr-level">Lv.' + level() + '</span>' +
          '<span>' + state.xp + ' XP</span><span class="cr-combo">连击 ' + state.combo + '</span></button>' +
          '<div id="campus-rewards-panel"><strong>课堂进度</strong>' +
          '<div class="cr-bar"><i style="width:' + (state.xp % 100) + '%"></i></div>' +
          '<small>再得 ' + (100 - state.xp % 100) + ' XP 升到 Lv.' + (level() + 1) + '</small>' +
          '<p>最高连击 ' + state.bestCombo + ' · 已学 ' + state.pages.length + ' 页</p>' +
          '<div class="cr-badges">' + (badges || '<em>继续翻页解锁成就</em>') + '</div></div>';
        var panel = root.querySelector('#campus-rewards-panel');
        panel.style.display = state.open ? 'block' : 'none';
        root.querySelector('#campus-rewards-toggle').onclick = function () {
          state.open = !state.open;
          save();
          panel.style.display = state.open ? 'block' : 'none';
        };
        save();
      }
      function tick() {
        var now = Date.now();
        var current = title();
        if (!current || current === state.lastTitle) return;
        if (state.lastAt && now - state.lastAt > 5 * 60 * 1000) state.combo = 0;
        state.lastTitle = current;
        state.lastAt = now;
        // Only a page never seen before earns XP. Going back and forth must not
        // be a way to farm progress; this matches the Web native classroom.
        var firstVisit = state.pages.indexOf(current) < 0;
        if (firstVisit) {
          state.combo += 1;
          state.bestCombo = Math.max(state.bestCombo, state.combo);
          state.xp += 12;
          state.pages.push(current);
        }
        if (state.pages.length > 200) state.pages = state.pages.slice(-200);
        award('first-page', '第一页');
        if (state.combo >= 3) award('combo-3', '三连页');
        if (state.pages.length >= 10) award('pages-10', '十页');
        if (level() >= 5) award('level-5', 'Lv.5');
        render();
      }
      function mount() {
        if (!document.body) return;
        if (!document.getElementById('campus-rewards-style')) {
          var style = document.createElement('style');
          style.id = 'campus-rewards-style';
          style.textContent = '#campus-rewards{position:fixed;right:8px;bottom:74px;z-index:9999;' +
            'font-family:-apple-system,BlinkMacSystemFont,sans-serif}' +
            '#campus-rewards-toggle{display:flex;align-items:center;gap:6px;border:1px solid rgba(21,59,52,.18);' +
            'background:rgba(251,249,241,.96);color:#153b34;border-radius:999px;padding:5px 9px;font-size:11px;' +
            'font-weight:700;box-shadow:0 6px 18px rgba(21,59,52,.16)}' +
            '#campus-rewards-toggle .cr-level{background:#153b34;color:#fbf9f1;border-radius:999px;padding:1px 6px}' +
            '#campus-rewards-toggle .cr-combo{color:#ad6845}' +
            '#campus-rewards-panel{display:none;width:210px;margin-top:6px;background:#fbf9f1;border:1px solid #e4dfce;' +
            'border-radius:14px;padding:10px;color:#22332d;box-shadow:0 16px 36px rgba(21,59,52,.18)}' +
            '#campus-rewards-panel strong{font-size:12px;color:#153b34}' +
            '.cr-bar{height:6px;border-radius:999px;background:#e4dfce;overflow:hidden;margin:7px 0 4px}' +
            '.cr-bar i{display:block;height:100%;background:#dab27a}' +
            '#campus-rewards-panel small,#campus-rewards-panel p{font-size:10px;color:#6c7a72}' +
            '#campus-rewards-panel p{margin:5px 0}' +
            '.cr-badges{display:flex;flex-wrap:wrap;gap:4px}' +
            '.cr-badge{font-size:10px;background:rgba(21,59,52,.08);border-radius:999px;padding:2px 6px;color:#153b34}' +
            '.cr-badges em{font-size:10px;color:#8a9690}';
          document.head.appendChild(style);
        }
        render();
      }
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
      else mount();
      setInterval(tick, 1500);
    })();
"""#
}
