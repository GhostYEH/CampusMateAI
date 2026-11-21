/**
 * CampusMate 网页兼容课堂奖励 HUD。
 *
 * 规则与 Android 原生 `ClassroomRewardsEngine` 对齐，并共享
 * `android/app/src/test/resources/classroom-rewards-events.json` 事件样例：
 * 首次访问页面 +12 XP；首次交卷按答对题数 ×6，满分 +20，
 * 第二次起的连续满分/答对 +12；同一场景重复访问或重做不重复结算。
 *
 * 账本按 `window.__campusRewardsConfig.key` 隔离（服务 + 账号 + 课堂）。
 * 只有拿到稳定的 `data-scene-id` 才记账；匹配不到时只显示归属，不猜测页面身份。
 * 旧版 `campusmate:classroom-rewards:v1` 不带账号信息，不迁移、不删除，只在面板注明。
 *
 * 纯函数部分同时导出给 Node 一致性测试；在 WebView 中自动挂载 HUD。
 */
(function (root, factory) {
  var api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ClassroomRewardsRules = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  var VISIT_XP = 12;
  var CORRECT_XP = 6;
  var PERFECT_BONUS = 20;
  var COMBO_BONUS = 12;
  var LEVEL_STEP = 100;
  var ACHIEVEMENT_LABELS = {
    first_scene: '开课了',
    half_route: '过半',
    finish_route: '走完这一章',
    combo_3: '三连对',
    combo_5: '五连对',
    perfect_quiz: '满分答卷'
  };
  var ACHIEVEMENT_IDS = Object.keys(ACHIEVEMENT_LABELS);

  function empty() {
    return {
      version: 2,
      xp: 0,
      visited: {},
      quiz: {},
      combo: 0,
      bestCombo: 0,
      achievements: [],
      updatedAt: ''
    };
  }

  function normalize(raw) {
    var state = empty();
    if (!raw || typeof raw !== 'object') return state;
    state.xp = Math.max(0, Number(raw.xp) || 0);
    state.combo = Math.max(0, Number(raw.combo) || 0);
    state.bestCombo = Math.max(0, Number(raw.bestCombo) || 0);
    state.updatedAt = typeof raw.updatedAt === 'string' ? raw.updatedAt : '';
    if (raw.visited && typeof raw.visited === 'object') {
      Object.keys(raw.visited).forEach(function (key) {
        if (key && raw.visited[key]) state.visited[key] = true;
      });
    }
    if (raw.quiz && typeof raw.quiz === 'object') {
      Object.keys(raw.quiz).forEach(function (key) {
        var item = raw.quiz[key];
        if (!key || !item || typeof item !== 'object') return;
        state.quiz[key] = {
          correct: Math.max(0, Number(item.correct) || 0),
          total: Math.max(0, Number(item.total) || 0),
          perfect: item.perfect === true
        };
      });
    }
    if (Array.isArray(raw.achievements)) {
      raw.achievements.forEach(function (id) {
        if (ACHIEVEMENT_IDS.indexOf(id) >= 0 && state.achievements.indexOf(id) < 0) {
          state.achievements.push(id);
        }
      });
    }
    return state;
  }

  function levelOf(xp) {
    var total = Math.max(0, Number(xp) || 0);
    var inLevel = total % LEVEL_STEP;
    return {
      level: Math.floor(total / LEVEL_STEP) + 1,
      xp: total,
      inLevel: inLevel,
      toNext: LEVEL_STEP - inLevel,
      progress: inLevel / LEVEL_STEP
    };
  }

  function unlockedAchievements(state, totalScenes) {
    var next = [];
    var earned = state.achievements;
    function add(id, condition) {
      if (condition && earned.indexOf(id) < 0 && next.indexOf(id) < 0) next.push(id);
    }
    var visitedCount = Object.keys(state.visited).length;
    add('first_scene', visitedCount >= 1);
    add('half_route', totalScenes >= 2 && visitedCount >= Math.floor((totalScenes + 1) / 2));
    add('finish_route', totalScenes > 0 && visitedCount >= totalScenes);
    add('combo_3', state.bestCombo >= 3);
    add('combo_5', state.bestCombo >= 5);
    add('perfect_quiz', Object.keys(state.quiz).some(function (key) { return state.quiz[key].perfect; }));
    return next;
  }

  function withUnlocks(state, totalScenes, awarded, now) {
    var unlocked = unlockedAchievements(state, totalScenes);
    if (!unlocked.length) {
      return { state: state, awardedXp: awarded, unlocked: [], combo: state.combo };
    }
    var next = normalize(state);
    next.achievements = next.achievements.concat(unlocked);
    next.updatedAt = now || '';
    return { state: next, awardedXp: awarded, unlocked: unlocked, combo: next.combo };
  }

  function visit(rewards, sceneId, totalScenes, now) {
    var current = normalize(rewards);
    if (!sceneId || current.visited[sceneId]) {
      return { state: current, awardedXp: 0, unlocked: [], combo: current.combo };
    }
    current.visited[sceneId] = true;
    current.xp += VISIT_XP;
    return withUnlocks(current, totalScenes, VISIT_XP, now);
  }

  function grade(rewards, sceneId, correct, total, totalScenes, now) {
    var current = normalize(rewards);
    var safeCorrect = Math.max(0, Number(correct) || 0);
    var safeTotal = Number(total) > 0 ? Number(total) : safeCorrect;
    var right = safeTotal > 0 ? Math.min(safeCorrect, safeTotal) : 0;
    if (!sceneId || current.quiz[sceneId] || safeTotal === 0) {
      return { state: current, awardedXp: 0, unlocked: [], combo: current.combo };
    }
    var perfect = right === safeTotal && safeTotal > 0;
    var combo = right > 0 ? current.combo + 1 : 0;
    var xp = right * CORRECT_XP +
      (perfect ? PERFECT_BONUS : 0) +
      (right > 0 && combo > 1 ? COMBO_BONUS : 0);
    current.xp += xp;
    current.combo = combo;
    current.bestCombo = Math.max(current.bestCombo, combo);
    current.quiz[sceneId] = { correct: right, total: safeTotal, perfect: perfect };
    return withUnlocks(current, totalScenes, xp, now);
  }

  /** 从 quiz-attempt 响应中提取判分；重做由 grade 的场景去重保证只计一次。 */
  function gradeFromAttempt(rewards, sceneId, payload, totalScenes, now) {
    var state = payload && payload.state ? payload.state : payload;
    var phase = state && state.phase;
    var results = state && state.results;
    if (!state || (phase !== 'submitted' && phase !== 'reviewed') || !Array.isArray(results) || !results.length) {
      return { state: normalize(rewards), awardedXp: 0, unlocked: [], combo: 0, applied: false };
    }
    var correct = results.filter(function (item) { return item && item.correct === true; }).length;
    var outcome = grade(rewards, sceneId, correct, results.length, totalScenes, now);
    outcome.applied = true;
    return outcome;
  }

  var api = {
    VISIT_XP: VISIT_XP,
    CORRECT_XP: CORRECT_XP,
    PERFECT_BONUS: PERFECT_BONUS,
    COMBO_BONUS: COMBO_BONUS,
    LEVEL_STEP: LEVEL_STEP,
    ACHIEVEMENT_LABELS: ACHIEVEMENT_LABELS,
    ACHIEVEMENT_IDS: ACHIEVEMENT_IDS,
    empty: empty,
    normalize: normalize,
    levelOf: levelOf,
    unlockedAchievements: unlockedAchievements,
    visit: visit,
    grade: grade,
    gradeFromAttempt: gradeFromAttempt
  };

  if (root && root.document && !root.__campusRewards) {
    root.__campusRewards = true;
    mount(root, api);
  }
  return api;

  // ── WebView 挂载 ───────────────────────────────────────────────────────────

  function mount(root, rules) {
    var config = root.__campusRewardsConfig || {};
    var key = typeof config.key === 'string' && config.key ? config.key : 'campusmate:classroom-rewards:v2:unbound';
    var accountBound = config.accountBound !== false;
    var totalScenes = Number(config.totalScenes) > 0 ? Number(config.totalScenes) : 0;
    var label = typeof config.classroomLabel === 'string' ? config.classroomLabel : '网页兼容课堂';
    var bottom = Number(config.bottom) > 0 ? Number(config.bottom) : 64;
    var legacyKey = 'campusmate:classroom-rewards:v1';
    var state = load();
    var unmatched = 0;
    var lastSceneId = '';

    function load() {
      try {
        return rules.normalize(JSON.parse(localStorage.getItem(key) || 'null'));
      } catch (_) {
        return rules.empty();
      }
    }

    function save() {
      try { localStorage.setItem(key, JSON.stringify(state)); } catch (_) {}
    }

    function sceneId() {
      var selectors = ['[data-scene-id]', '[data-testid="slide-canvas"][data-scene-id]'];
      for (var i = 0; i < selectors.length; i += 1) {
        var node = document.querySelector(selectors[i]);
        var value = node && node.getAttribute('data-scene-id');
        if (value) return String(value).slice(0, 128);
      }
      return '';
    }

    function title() {
      var node = document.querySelector('h1, [class*="text-xl"][class*="font-bold"]');
      var text = node && node.textContent ? node.textContent.trim() : '';
      return text || document.title || location.pathname;
    }

    function applyVisit() {
      var id = sceneId();
      if (!id) {
        unmatched += 1;
        render();
        return;
      }
      if (id === lastSceneId) return;
      lastSceneId = id;
      var outcome = rules.visit(state, id, totalScenes, new Date().toISOString());
      state = outcome.state;
      save();
      render();
    }

    function applyQuiz(scene, payload) {
      if (!scene) return;
      var outcome = rules.gradeFromAttempt(state, scene, payload, totalScenes, new Date().toISOString());
      if (!outcome.applied) return;
      state = outcome.state;
      save();
      render();
    }

    function installQuizInterceptor() {
      if (typeof root.fetch !== 'function' || root.fetch.__campusRewardsWrapped) return;
      var original = root.fetch;
      var wrapped = function () {
        var args = arguments;
        var requestUrl = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
        var promise = original.apply(this, args);
        try {
          if (String(requestUrl).indexOf('/quiz-attempt') >= 0) {
            promise.then(function (response) {
              if (!response || !response.ok || typeof response.clone !== 'function') return;
              var scene = '';
              var match = String(requestUrl).match(/scenes\/([^/?#]+)\/quiz-attempt/);
              if (match) scene = decodeURIComponent(match[1]);
              response.clone().json().then(function (payload) {
                applyQuiz(scene, payload);
              }).catch(function () {});
            }).catch(function () {});
          }
        } catch (_) {}
        return promise;
      };
      wrapped.__campusRewardsWrapped = true;
      root.fetch = wrapped;
    }

    function legacyExists() {
      try { return !!localStorage.getItem(legacyKey); } catch (_) { return false; }
    }

    function render() {
      var host = document.getElementById('campus-rewards');
      if (!host) {
        host = document.createElement('div');
        host.id = 'campus-rewards';
        document.body.appendChild(host);
      }
      var level = rules.levelOf(state.xp);
      var badges = state.achievements.map(function (id) {
        return '<span class="cr-badge">' + (rules.ACHIEVEMENT_LABELS[id] || id) + '</span>';
      }).join('');
      var ownership = accountBound
        ? '<small class="cr-owner">归属：' + escapeHtml(label) + '</small>'
        : '<small class="cr-owner">账号未确认，奖励仅保存在本机</small>';
      var unmatchedNote = unmatched > 0
        ? '<small class="cr-unmatched">当前页未匹配到稳定场景，未计入进度（' + unmatched + ' 次）</small>'
        : '';
      var legacyNote = legacyExists()
        ? '<small class="cr-legacy">旧版网页奖励未绑定账号，未并入本课堂</small>'
        : '';
      host.innerHTML = '<button id="campus-rewards-toggle" type="button">' +
        '<span class="cr-level">Lv.' + level.level + '</span>' +
        '<span class="cr-xp">' + state.xp + ' XP</span>' +
        '<span class="cr-combo">连击 ' + state.combo + '</span></button>' +
        '<div id="campus-rewards-panel"><strong>课堂进度</strong>' +
        ownership +
        '<div class="cr-bar"><i style="width:' + level.inLevel + '%"></i></div>' +
        '<small>再得 ' + level.toNext + ' XP 升到 Lv.' + (level.level + 1) + '</small>' +
        '<p>最高连击 ' + state.bestCombo + ' · 已学 ' + Object.keys(state.visited).length + ' 页</p>' +
        '<div class="cr-badges">' + (badges || '<em>继续翻页解锁成就</em>') + '</div>' +
        unmatchedNote + legacyNote + '</div>';
      var panel = host.querySelector('#campus-rewards-panel');
      panel.style.display = state.open ? 'block' : 'none';
      host.querySelector('#campus-rewards-toggle').onclick = function () {
        state.open = !state.open;
        save();
        panel.style.display = state.open ? 'block' : 'none';
      };
      save();
    }

    function escapeHtml(text) {
      return String(text).replace(/[&<>"']/g, function (ch) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
      });
    }

    function installStyle() {
      if (document.getElementById('campus-rewards-style')) return;
      var style = document.createElement('style');
      style.id = 'campus-rewards-style';
      style.textContent = '#campus-rewards{position:fixed;right:8px;bottom:' + bottom + 'px;z-index:9999;' +
        'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}' +
        '#campus-rewards-toggle{display:flex;align-items:center;gap:6px;border:1px solid rgba(21,59,52,.18);' +
        'background:rgba(251,249,241,.96);color:#153b34;border-radius:999px;padding:5px 9px;font-size:11px;' +
        'font-weight:700;box-shadow:0 6px 18px rgba(21,59,52,.16)}' +
        '#campus-rewards-toggle .cr-level{background:#153b34;color:#fbf9f1;border-radius:999px;padding:1px 6px}' +
        '#campus-rewards-toggle .cr-combo{color:#ad6845}' +
        '#campus-rewards-panel{display:none;width:230px;margin-top:6px;background:#fbf9f1;border:1px solid #e4dfce;' +
        'border-radius:14px;padding:10px;color:#22332d;box-shadow:0 16px 36px rgba(21,59,52,.18)}' +
        '#campus-rewards-panel strong{font-size:12px;color:#153b34}' +
        '.cr-bar{height:6px;border-radius:999px;background:#e4dfce;overflow:hidden;margin:7px 0 4px}' +
        '.cr-bar i{display:block;height:100%;background:#dab27a}' +
        '#campus-rewards-panel small{display:block;font-size:10px;color:#6c7a72;margin-top:4px}' +
        '#campus-rewards-panel p{font-size:10px;color:#6c7a72;margin:5px 0}' +
        '.cr-owner{color:#153b34 !important}' +
        '.cr-unmatched,.cr-legacy{color:#ad6845 !important}' +
        '.cr-badges{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}' +
        '.cr-badge{font-size:10px;background:rgba(21,59,52,.08);border-radius:999px;padding:2px 6px;color:#153b34}' +
        '.cr-badges em{font-size:10px;color:#8a9690}';
      document.head.appendChild(style);
    }

    function boot() {
      installStyle();
      installQuizInterceptor();
      applyVisit();
      render();
      setInterval(applyVisit, 1500);
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', boot);
    } else {
      boot();
    }
  }
});
