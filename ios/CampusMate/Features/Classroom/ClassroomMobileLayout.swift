import Foundation

/// 受管课堂 WebView 在窄屏上的布局修正：压缩头栏与对话区、给对话区加可拖拽手柄，
/// 并让课件支持双指缩放。脚本与 Android `classroomMobileFix` 保持同一份契约，
/// 避免 iOS 与 Android 在同一个课堂里出现两套交互。
enum ClassroomMobileLayout {
    static let script = #"""
    (function () {
      if (document.getElementById('campus-mobile-classroom-style')) return;
      var style = document.createElement('style');
      style.id = 'campus-mobile-classroom-style';
      style.textContent = `
        nextjs-portal { display: none !important; }
        @media (max-width: 700px) {
          header.h-20 { height: 66px !important; padding: 4px 12px !important; gap: 6px !important; }
          header.h-20 > div:first-child > button:first-child { display: none !important; }
          header.h-20 > div:first-child { min-width: 0 !important; flex: 1 1 auto !important; }
          header.h-20 h1 { font-size: 16px !important; line-height: 20px !important;
            white-space: normal !important; display: -webkit-box !important;
            -webkit-line-clamp: 2; -webkit-box-orient: vertical;
            overflow: hidden !important; max-height: 40px !important; }
          header.h-20 > div:last-child { max-width: 136px !important; flex: 0 0 auto !important;
            overflow-x: auto !important; }
          div[class*="h-[192px]"][class*="backdrop-blur"],
          div[class*="rounded-[2.5rem]"][class*="backdrop-blur"] {
            backdrop-filter: none !important; -webkit-backdrop-filter: none !important;
          }
          div[class*="h-[192px]"][class*="backdrop-blur"] {
            height: var(--campus-dialogue-height, 192px) !important;
            min-height: 120px !important;
            flex-shrink: 0 !important;
          }
          div[class*="w-[90px]"][class*="shrink-0"] { width: 72px !important; }
          div[class*="w-[140px]"][class*="shrink-0"] {
            width: 82px !important; padding-top: 4px !important;
          }
          div[class*="w-[140px]"][class*="shrink-0"] > div:first-child {
            display: none !important;
          }
          [data-testid="roundtable-non-presentation-card"] {
            padding-left: 4px !important; padding-right: 4px !important;
            border-radius: 16px !important; overflow: visible !important;
          }
          [data-testid="roundtable-non-presentation-input-stage"] {
            left: 4px !important; right: 4px !important; bottom: 6px !important;
          }
          [data-testid="roundtable-non-presentation-input-panel"] {
            width: 100% !important; max-width: 100% !important;
            min-width: 0 !important; padding: 5px !important; gap: 2px !important;
          }
          [data-testid="roundtable-non-presentation-input-panel"] textarea {
            min-width: 0 !important; font-size: 16px !important;
          }
          .campus-dialogue-grip {
            position: absolute; z-index: 100; left: 50%; top: -16px;
            transform: translateX(-50%); width: 88px; height: 24px;
            border-radius: 14px; border: 1px solid #9ca6b7;
            background: rgba(255,255,255,.96); box-shadow: 0 2px 9px #18274435;
            touch-action: none; display: flex; align-items: center; justify-content: center;
          }
          .campus-dialogue-grip::after {
            content: ''; width: 38px; height: 4px; border-radius: 4px;
            background: #506782;
          }
          .campus-slide-reset {
            position: absolute; z-index: 120; right: 12px; bottom: 12px;
            border: 0; border-radius: 16px; padding: 8px 12px;
            color: #fff; background: #172747; font-size: 13px;
            box-shadow: 0 3px 12px #17274755;
          }
          [aria-live="polite"][class*="group/bubble"],
          div[class*="max-h-[110px]"][class*="group/bubble"] {
            display: none !important;
          }
        }
      `;
      document.head.appendChild(style);
      function attachGrip() {
        var panel = document.querySelector('div[class*="h-[192px]"][class*="backdrop-blur"]');
        if (!panel || panel.querySelector('.campus-dialogue-grip')) return;
        var grip = document.createElement('div');
        grip.className = 'campus-dialogue-grip';
        grip.setAttribute('role', 'separator');
        grip.setAttribute('aria-label', '拖动调整课件与对话区域');
        panel.appendChild(grip);
        var startY = 0, startHeight = 192;
        grip.addEventListener('pointerdown', function (event) {
          startY = event.clientY;
          startHeight = panel.getBoundingClientRect().height;
          grip.setPointerCapture(event.pointerId);
          event.preventDefault();
        });
        grip.addEventListener('pointermove', function (event) {
          if (!grip.hasPointerCapture(event.pointerId)) return;
          var upper = Math.min(320, Math.max(180, innerHeight * .48));
          var next = Math.max(120, Math.min(upper, startHeight - (event.clientY - startY)));
          panel.style.setProperty('--campus-dialogue-height', next + 'px');
          event.preventDefault();
        });
      }
      attachGrip();
      new MutationObserver(attachGrip).observe(document.body, { childList: true, subtree: true });
      function attachSlideZoom() {
        var canvas = document.querySelector('[class*="group/canvas"]');
        var area = canvas && canvas.firstElementChild;
        var slide = area && area.firstElementChild;
        if (!area || !slide || !slide.className.includes('aspect-[16/9]')) return;
        if (area.__campusZoom) {
          if (area.__campusZoomSlide !== slide) {
            area.__campusZoomSlide = slide;
            area.__campusZoomSetSlide(slide);
          }
          return;
        }
        area.__campusZoom = true;
        area.__campusZoomSlide = slide;
        var scale = 1, x = 0, y = 0, startDistance = 0;
        var startScale = 1, startX = 0, startY = 0, touchX = 0, touchY = 0;
        var reset = document.createElement('button');
        reset.className = 'campus-slide-reset';
        reset.textContent = '恢复原尺寸';
        reset.style.display = 'none';
        area.appendChild(reset);
        function draw() {
          slide.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(' + scale + ')';
          slide.style.transformOrigin = 'center center';
          reset.style.display = scale > 1.01 ? 'block' : 'none';
        }
        reset.addEventListener('click', function (event) {
          event.stopPropagation(); scale = 1; x = 0; y = 0; draw();
        });
        area.__campusZoomSetSlide = function (nextSlide) {
          slide = nextSlide; scale = 1; x = 0; y = 0; draw();
        };
        area.addEventListener('touchstart', function (event) {
          if (event.touches.length === 2) {
            var a = event.touches[0], b = event.touches[1];
            startDistance = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
            startScale = scale; startX = x; startY = y;
            touchX = (a.clientX + b.clientX) / 2;
            touchY = (a.clientY + b.clientY) / 2;
          } else if (event.touches.length === 1 && scale > 1) {
            touchX = event.touches[0].clientX; touchY = event.touches[0].clientY;
            startX = x; startY = y;
          }
        }, { passive: true });
        area.addEventListener('touchmove', function (event) {
          if (event.touches.length === 2 && startDistance > 0) {
            var a = event.touches[0], b = event.touches[1];
            scale = Math.max(1, Math.min(3, startScale * Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY) / startDistance));
            x = startX + ((a.clientX + b.clientX) / 2 - touchX);
            y = startY + ((a.clientY + b.clientY) / 2 - touchY);
            if (scale === 1) { x = 0; y = 0; }
            draw(); event.preventDefault();
          } else if (event.touches.length === 1 && scale > 1) {
            x = startX + event.touches[0].clientX - touchX;
            y = startY + event.touches[0].clientY - touchY;
            draw(); event.preventDefault();
          }
        }, { passive: false });
      }
      attachSlideZoom();
      new MutationObserver(attachSlideZoom).observe(document.body, { childList: true, subtree: true });
    })();
"""#
}
