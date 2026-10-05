package com.example.campusai.ui.screens.courses

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.speech.RecognizerIntent
import android.webkit.ConsoleMessage
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import com.example.campusai.data.remote.ClassroomUrlPolicy
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.theme.Muted
import com.example.campusai.data.focus.voice.AndroidTextToSpeechSynthesizer
import android.os.Handler
import android.os.Looper
import org.json.JSONTokener
import org.json.JSONObject
import kotlinx.coroutines.launch

/** Some Android WebViews report a zero CSS viewport for `100vh` inside a Compose dialog. */
private val classroomViewportFix = """
    (function () {
      if (!document.body) return;
      if (window.__campusClassroomViewportFix) return;
      window.__campusClassroomViewportFix = true;
      function applyHeight() {
        var height = Math.round((window.visualViewport && window.visualViewport.height) ||
          window.innerHeight || document.documentElement.clientHeight || 0);
        if (!height || !document.body) return;
        var pixels = height + 'px';
        document.documentElement.style.setProperty('height', pixels, 'important');
        document.body.style.setProperty('height', pixels, 'important');
        Array.prototype.forEach.call(document.body.children, function (element) {
          if (element.classList && element.classList.contains('h-screen')) {
            element.style.setProperty('height', pixels, 'important');
          }
        });
      }
      applyHeight();
      window.addEventListener('resize', applyHeight);
      if (window.visualViewport) window.visualViewport.addEventListener('resize', applyHeight);
      new MutationObserver(applyHeight).observe(document.body, { childList: true });
    })();
""".trimIndent()

/** Keep the upstream desktop classroom readable in a narrow Android WebView. */
private val classroomMobileFix = """
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
""".trimIndent()

/** Read the speech text even when the narrow WebView hides the upstream bubble. */
private val classroomNarrationSnapshot = """
    (function () {
      var playing = !!document.querySelector('button[aria-label="Pause"]');
      var cards = Array.prototype.slice.call(document.querySelectorAll(
        '[aria-live="polite"][class*="group/bubble"], div[class*="max-h-[110px]"][class*="group/bubble"]'));
      var card = cards.find(function (node) {
        return node.querySelector('p') && node.querySelector('p').textContent.trim();
      });
      var spoken = card && card.querySelector('p');
      var qaSpeech = window.__campusQaSpeech || '';
      var qaEmpty = window.__campusQaEmpty === true;
      window.__campusQaSpeech = '';
      window.__campusQaEmpty = false;
      return JSON.stringify({ playing: playing,
        browserSpeaking: !!(window.speechSynthesis && window.speechSynthesis.speaking),
        text: spoken ? spoken.textContent.trim().slice(0, 6000) : '',
        qaSpeech: qaSpeech, qaEmpty: qaEmpty });
    })()
""".trimIndent()

/** Route classroom Q&A to the configured server model and read the teacher's streamed reply aloud. */
private val classroomTeacherQuestionFix = """
    (function () {
      if (window.__campusTeacherQuestionFix) return;
      window.__campusTeacherQuestionFix = true;
      var originalFetch = window.fetch;
      window.fetch = function (input, init) {
        var rawUrl = typeof input === 'string' ? input : input && input.url;
        var path;
        try { path = new URL(rawUrl, location.href).pathname; } catch (_) { path = ''; }
        if (path !== '/api/chat' || !init || !init.body ||
            String(init.method || 'GET').toUpperCase() !== 'POST') {
          return originalFetch.apply(this, arguments);
        }
        try {
          var request = JSON.parse(init.body);
          if (!request.config || request.config.sessionType !== 'qa') {
            return originalFetch.apply(this, arguments);
          }
          var configs = Array.isArray(request.config.agentConfigs)
            ? request.config.agentConfigs : [];
          var selected = Array.isArray(request.config.agentIds)
            ? request.config.agentIds : [];
          var teacher = configs.find(function (agent) {
            return agent.role === 'teacher' && selected.indexOf(agent.id) !== -1;
          });
          if (teacher) {
            request.config.agentIds = [teacher.id];
            request.config.agentConfigs = [teacher];
          } else {
            // The generated roster may not have hydrated yet. The built-in teacher
            // is always available on the classroom server.
            request.config.agentIds = ['default-1'];
            delete request.config.agentConfigs;
            console.warn('CAMPUS_QA_TEACHER_FALLBACK');
          }
          delete request.config.triggerAgentId;
          // The browser can retain a model that this classroom server cannot use.
          // Let the server select its configured chat model for teacher Q&A.
          delete request.model;
          delete request.apiKey;
          delete request.baseUrl;
          delete request.providerType;
          delete request.thinking;
          request.thinkingConfig = { mode: 'disabled', enabled: false };
          return originalFetch.call(this, input, Object.assign({}, init, {
            body: JSON.stringify(request)
          })).then(function (response) {
            if (response.ok) {
              response.clone().text().then(function (body) {
                var spoken = '';
                var empty = false;
                body.split(/\r?\n/).forEach(function (line) {
                  if (line.indexOf('data: ') !== 0) return;
                  try {
                    var event = JSON.parse(line.slice(6));
                    if (event.type === 'text_delta' && event.data &&
                        typeof event.data.content === 'string') {
                      spoken += event.data.content;
                    } else if (event.type === 'done' && event.data &&
                               event.data.agentHadContent === false &&
                               event.data.totalAgents > 0) {
                      empty = true;
                    }
                  } catch (_) { /* Ignore incomplete SSE lines. */ }
                });
                spoken = spoken.replace(/\s+/g, ' ').trim().slice(0, 2000);
                if (spoken) window.__campusQaSpeech = spoken;
                else if (empty) window.__campusQaEmpty = true;
              }).catch(function () { /* The classroom still handles the stream. */ });
            }
            return response;
          });
        } catch (error) {
          console.warn('CAMPUS_QA_TEACHER_ROUTING_FAILED', String(error));
          return originalFetch.apply(this, arguments);
        }
      };
    })();
""".trimIndent()

/** A classroom remains inside CampusMate; navigation is confined to its trusted origin. */
@Composable
internal fun ClassroomViewer(url: String, onClose: () -> Unit, repository: AppRepository? = null) {
    val context = LocalContext.current
    val origin = remember(url) { ClassroomUrlPolicy.originOf(url) }
    var webView by remember(url) { mutableStateOf<WebView?>(null) }
    var loading by remember(url) { mutableStateOf(true) }
    var pageFinished by remember(url) { mutableStateOf(false) }
    var loadError by remember(url) { mutableStateOf<String?>(null) }
    var speaking by remember(url) { mutableStateOf(false) }
    var speechError by remember(url) { mutableStateOf<String?>(null) }
    var transcript by remember(url) { mutableStateOf("") }
    var autoSpeaking by remember(url) { mutableStateOf(false) }
    var candidateSpeech by remember(url) { mutableStateOf("") }
    var candidateCount by remember(url) { mutableIntStateOf(0) }
    var lastNarratedSpeech by remember(url) { mutableStateOf("") }
    var pendingAudioRequest by remember(url) { mutableStateOf<PermissionRequest?>(null) }
    val speaker = remember(url) { AndroidTextToSpeechSynthesizer(context) }
    val mainHandler = remember { Handler(Looper.getMainLooper()) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(speechError) {
        if (speechError != null) {
            kotlinx.coroutines.delay(8000)
            speechError = null
        }
    }
    val nativeSpeechLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val spoken = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()?.trim().orEmpty()
            if (spoken.isNotBlank()) {
                speechError = null
                val quoted = JSONObject.quote(spoken)
                webView?.evaluateJavascript("""
                    (function () {
                      var input = document.querySelector('[data-testid="roundtable-non-presentation-input-panel"] textarea')
                        || document.querySelector('textarea');
                      if (!input) return false;
                      var setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
                      setter.call(input, $quoted);
                      input.dispatchEvent(new Event('input', { bubbles: true }));
                      input.focus();
                      return true;
                    })()
                """.trimIndent()) { inserted ->
                    if (inserted != "true") speechError = "已识别语音，但没找到提问框。请切换到课堂对话后重试。"
                }
            }
        }
    }
    val microphonePermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        val request = pendingAudioRequest
        pendingAudioRequest = null
        if (request != null) {
            if (granted && origin != null && ClassroomUrlPolicy.originOf(request.origin.toString()) == origin &&
                ClassroomUrlPolicy.originOf(webView?.url) == origin &&
                ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
            ) {
                request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
                speechError = null
            } else {
                request.deny()
                if (!granted) speechError = "麦克风未获授权。请在系统设置中允许录音后重试。"
            }
        }
    }
    BackHandler { if (webView?.canGoBack() == true) webView?.goBack() else onClose() }
    DisposableEffect(url) { onDispose {
        pendingAudioRequest?.deny()
        pendingAudioRequest = null
        speaker.shutdown(); webView?.stopLoading(); webView?.destroy()
    } }
    LaunchedEffect(pageFinished, loadError) {
        if (pageFinished && loadError == null) {
            kotlinx.coroutines.delay(10000)
            webView?.evaluateJavascript(
                "!(document.body?.innerText||'').trim() || document.body?.querySelector(':scope > .h-screen')?.getBoundingClientRect().height === 0",
            ) { result ->
                if (result == "true") {
                    loadError = "课堂网页已打开，但页面高度异常。请重新加载课堂。"
                }
            }
        }
    }
    LaunchedEffect(pageFinished, loadError) {
        while (pageFinished && loadError == null) {
            webView?.evaluateJavascript(classroomNarrationSnapshot) { raw ->
                val snapshot = runCatching {
                    JSONObject(JSONTokener(raw).nextValue() as String)
                }.getOrNull()
                val playing = snapshot?.optBoolean("playing") == true
                val browserSpeaking = snapshot?.optBoolean("browserSpeaking") == true
                val line = snapshot?.optString("text").orEmpty().trim()
                val qaSpeech = snapshot?.optString("qaSpeech").orEmpty().trim()
                transcript = line
                if (snapshot?.optBoolean("qaEmpty") == true) {
                    speechError = "老师这次没有生成回答，请重试提问。"
                }
                if (qaSpeech.isNotBlank() && !browserSpeaking && !speaking) {
                    speaker.stop()
                    autoSpeaking = false
                    lastNarratedSpeech = line
                    speaker.speak(qaSpeech.take(2000),
                        onDone = { },
                        onError = { message -> mainHandler.post { speechError = message } })
                } else if (!playing) {
                    if (autoSpeaking) { speaker.stop(); autoSpeaking = false }
                    candidateSpeech = ""; candidateCount = 0; lastNarratedSpeech = ""
                } else if (browserSpeaking) {
                    if (autoSpeaking) { speaker.stop(); autoSpeaking = false }
                    candidateSpeech = line; candidateCount = 2; lastNarratedSpeech = line
                } else if (!speaking && line.isNotBlank()) {
                    if (line == candidateSpeech) candidateCount++
                    else { candidateSpeech = line; candidateCount = 1 }
                    if (candidateCount >= 2 && line != lastNarratedSpeech) {
                        lastNarratedSpeech = line
                        autoSpeaking = true
                        speaker.speak(line,
                            onDone = { },
                            onError = { message -> mainHandler.post { autoSpeaking = false; speechError = message } })
                    }
                }
            }
            kotlinx.coroutines.delay(550)
        }
    }

    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Column(Modifier.fillMaxSize().background(Color(0xFFF2F1E8))
            .statusBarsPadding().navigationBarsPadding().imePadding()) {
            Row(Modifier.fillMaxWidth().height(56.dp).background(Color(0xFF153B34)), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onClose) { Icon(Icons.Default.ArrowBack, contentDescription = "返回互动课堂", tint = Color.White) }
                Text("互动课堂", color = Color.White, fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                IconButton(onClick = {
                    webView?.evaluateJavascript("""
                        (function () {
                          if (document.querySelector('[data-testid="roundtable-non-presentation-input-panel"] textarea')) return;
                          var chat = document.querySelector('div[class*="w-[140px]"] svg.lucide-message-square');
                          (chat && chat.closest('button'))?.click();
                        })()
                    """.trimIndent(), null)
                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                        putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
                        putExtra(RecognizerIntent.EXTRA_PROMPT, "说出你要问老师的问题")
                    }
                    try {
                        nativeSpeechLauncher.launch(intent)
                    } catch (_: Exception) {
                        speechError = "手机没有可用的语音识别服务，请使用文字提问。"
                    }
                }) {
                    Icon(Icons.Default.Mic, contentDescription = "语音输入问题", tint = Color.White)
                }
                IconButton(onClick = {
                    if (speaking) {
                        speaker.stop(); speaking = false
                    } else {
                        if (autoSpeaking) { speaker.stop(); autoSpeaking = false }
                        webView?.evaluateJavascript("""
                            (function () {
                              var center = document.elementFromPoint(innerWidth * .5, innerHeight * .42);
                              var scene = center && center.closest('[data-scene-id], [data-testid="slide-canvas"], .slide, main');
                              var text = (scene || document.querySelector('main') || document.body).innerText || '';
                              return text.trim().slice(0, 1800);
                            })()
                        """.trimIndent()) { raw ->
                            val text = runCatching { JSONTokener(raw).nextValue() as? String }.getOrNull()?.trim().orEmpty()
                            if (text.isBlank()) {
                                speechError = "本页没有可朗读的文字"
                            } else {
                                speechError = null; speaking = true
                                speaker.speak(text,
                                    onDone = { mainHandler.post { speaking = false } },
                                    onError = { message -> mainHandler.post { speaking = false; speechError = message } })
                            }
                        }
                    }
                }) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(if (speaking) Icons.Default.Stop else Icons.Default.VolumeUp,
                            contentDescription = if (speaking) "停止朗读" else "朗读当前页",
                            tint = Color.White, modifier = Modifier.size(20.dp))
                        Text(if (speaking) "停止" else "朗读", color = Color.White, fontSize = 10.sp)
                    }
                }
                if (loading) CircularProgressIndicator(Modifier.size(18.dp), color = Color.White, strokeWidth = 2.dp)
                Spacer(Modifier.width(18.dp))
            }
            Box(Modifier.weight(1f)) {
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
                    factory = {
                        WebView(context).apply {
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            // Next.js and the classroom renderer have a normal mobile
                            // browser path. Some dev WebViews append `; wv`, which makes
                            // the page take an incomplete embedded-browser branch.
                            settings.userAgentString = settings.userAgentString.replace("; wv", "")
                            settings.allowFileAccess = false
                            settings.allowContentAccess = false
                            settings.setSupportMultipleWindows(false)
                            settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
                            webChromeClient = object : WebChromeClient() {
                                override fun onPermissionRequest(request: PermissionRequest) {
                                    mainHandler.post {
                                        val audioOnly = request.resources.toSet() == setOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE)
                                        val trustedOrigin = origin != null && ClassroomUrlPolicy.originOf(request.origin.toString()) == origin &&
                                            ClassroomUrlPolicy.originOf(webView?.url) == origin
                                        if (!audioOnly || !trustedOrigin) {
                                            request.deny()
                                        } else if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                                            request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
                                            speechError = null
                                        } else {
                                            pendingAudioRequest?.deny()
                                            pendingAudioRequest = request
                                            microphonePermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                                        }
                                    }
                                }

                                override fun onPermissionRequestCanceled(request: PermissionRequest) {
                                    mainHandler.post {
                                        if (pendingAudioRequest === request) pendingAudioRequest = null
                                    }
                                }

                                override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                                    val detail = message.message()
                                    if (detail.contains("Speech recognition error") ||
                                        detail.contains("speech recognition", ignoreCase = true) && detail.contains("network")) {
                                        speechError = "网页语音识别连接失败。可点顶部麦克风使用手机语音输入，或直接打字。"
                                    }
                                    if (detail.contains("streamInterrupted", ignoreCase = true) ||
                                        detail.contains("totalAgents: 0")) {
                                        speechError = "老师没有生成回复。请稍后重试提问，并检查课堂模型服务额度。"
                                    }
                                    if (detail.contains("CAMPUS_QA_TEACHER_FALLBACK")) {
                                        speechError = "当前课堂老师配置未加载，已改用通用老师回答。"
                                    }
                                    if (detail.contains("CAMPUS_QA_TEACHER_ROUTING_FAILED")) {
                                        speechError = "提问未能指定老师，请重新打开课堂再试。"
                                    }
                                    if (message.messageLevel() == ConsoleMessage.MessageLevel.ERROR &&
                                        (detail.contains("Uncaught") || detail.contains("ChunkLoadError"))
                                    ) {
                                        loadError = "课堂网页脚本运行失败，请重新加载；若仍失败，请检查课堂服务。"
                                    }
                                    return super.onConsoleMessage(message)
                                }
                            }
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                                    ClassroomUrlPolicy.originOf(request.url.toString()) != origin

                                override fun onPageStarted(view: WebView, pageUrl: String?, favicon: Bitmap?) {
                                    pendingAudioRequest?.deny()
                                    pendingAudioRequest = null
                                    speaker.stop()
                                    speaking = false
                                    autoSpeaking = false
                                    lastNarratedSpeech = ""
                                    speechError = null
                                    transcript = ""
                                    loading = true
                                    pageFinished = false
                                    loadError = null
                                }

                                override fun onPageFinished(view: WebView, pageUrl: String?) {
                                    view.evaluateJavascript(classroomViewportFix, null)
                                    view.evaluateJavascript(classroomMobileFix, null)
                                    view.evaluateJavascript(classroomTeacherQuestionFix, null)
                                    if (ClassroomUrlPolicy.originOf(pageUrl) == origin) {
                                        scope.launch { repository?.recordClassroomEntry(url) }
                                    }
                                    loading = false
                                    pageFinished = true
                                }

                                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                                    if (request.isForMainFrame) {
                                        loading = false
                                        loadError = "课堂网页连接失败（错误码 ${error.errorCode}）。请检查课堂服务和手机网络。"
                                    }
                                }

                                override fun onReceivedHttpError(view: WebView, request: WebResourceRequest, errorResponse: WebResourceResponse) {
                                    if (request.isForMainFrame) {
                                        loading = false
                                        loadError = "课堂网页返回 HTTP ${errorResponse.statusCode}。请稍后重试。"
                                    }
                                }
                            }
                            webView = this
                            loadUrl(url)
                        }
                    },
                )
                if (loading) Text("课堂正在打开…", modifier = Modifier.align(Alignment.Center).background(Color(0xFFF2F1E8)).padding(12.dp), color = Muted)
                speechError?.let { Text(it, modifier = Modifier.align(Alignment.TopCenter)
                    .background(Color(0xFFF2F1E8)).padding(8.dp), color = Color(0xFF153B34)) }
                loadError?.let { message ->
                    Column(
                        Modifier.align(Alignment.Center).padding(24.dp).background(Color(0xFFF2F1E8)).padding(20.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(message, color = Color(0xFF153B34))
                        Spacer(Modifier.height(12.dp))
                        Button(onClick = { loadError = null; loading = true; pageFinished = false; webView?.reload() }) {
                            Text("重新加载")
                        }
                    }
                }
            }
            if (transcript.isNotBlank()) {
                Column(
                    Modifier.fillMaxWidth().background(Color.White).padding(horizontal = 16.dp, vertical = 8.dp),
                ) {
                    Text("课堂字幕", color = Muted, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    Text(
                        transcript,
                        modifier = Modifier.fillMaxWidth().heightIn(max = 88.dp).verticalScroll(rememberScrollState()),
                        color = Color(0xFF153B34), fontSize = 14.sp, lineHeight = 20.sp,
                    )
                }
            }
        }
    }
}
