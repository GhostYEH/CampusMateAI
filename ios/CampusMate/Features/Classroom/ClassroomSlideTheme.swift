import Foundation

/// 受管课堂 WebView 里的讲义配色修正（与 Web 原生课堂的 CampusMate 模板一致）。
enum ClassroomSlideTheme {
    static let script = #"""
    (function () {
      if (!document.body || window.__campusSlideThemeFix) return;
      window.__campusSlideThemeFix = true;
      var INK = '#153B34';
      var PAPER = '#F2F1E8';
      var LEGACY = ['rgb(51, 51, 51)', 'rgb(0, 0, 0)', 'rgb(17, 24, 39)',
        'rgb(31, 41, 55)', 'rgb(34, 34, 34)'];
      function paint() {
        Array.prototype.forEach.call(document.querySelectorAll('.screen-element'), function (element) {
          var color = window.getComputedStyle(element).color;
          if (LEGACY.indexOf(color) >= 0) element.style.setProperty('color', INK, 'important');
        });
        Array.prototype.forEach.call(document.querySelectorAll('[class*="bg-position-center"]'), function (element) {
          var color = window.getComputedStyle(element).backgroundColor;
          if (color === 'rgb(255, 255, 255)' || color === 'rgba(0, 0, 0, 0)') {
            element.style.setProperty('background-color', PAPER, 'important');
          }
        });
      }
      var frame = 0;
      function schedule() {
        if (frame) return;
        frame = window.requestAnimationFrame(function () { frame = 0; paint(); });
      }
      paint();
      new MutationObserver(schedule).observe(document.body, {
        childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class'],
      });
      window.addEventListener('resize', schedule);
    })();
"""#
}
