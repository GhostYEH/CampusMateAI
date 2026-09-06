import { useEffect, useState } from "react";
import { useApp } from "../app/AppContext.jsx";
import { getTypingDelay, getTypingFrame } from "./typingPlaceholder.js";

const TYPING_CONTROL_SELECTOR = [
  'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="file"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"]):not([type="date"]):not([type="time"]):not([type="datetime-local"]):not([type="month"]):not([type="week"]):not([type="color"])',
  "textarea",
].join(",");
const SOURCE_ATTRIBUTE = "data-typing-placeholder-source";
const ACTIVE_CLASS = "is-typing-placeholder";
const START_DELAY = 260;
const CURSOR_BLINK_INTERVAL = 560;

function getSource(control) {
  const storedSource = control.getAttribute(SOURCE_ATTRIBUTE);
  if (storedSource) return storedSource;

  const source = [
    control.getAttribute("placeholder"),
    control.getAttribute("aria-label"),
    control.labels?.[0]?.textContent,
  ].find((value) => value?.trim());
  const normalizedSource = source?.replace(/\s+/g, " ").trim() || "";
  if (normalizedSource) control.setAttribute(SOURCE_ATTRIBUTE, normalizedSource);
  return normalizedSource;
}

function isEmpty(control) {
  return !control.value && !control.disabled;
}

export default function TypingPlaceholderLayer() {
  const { reduceMotion } = useApp();
  const [systemReducedMotion, setSystemReducedMotion] = useState(() => window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false);

  useEffect(() => {
    const mediaQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mediaQuery) return undefined;
    const syncMotionPreference = () => setSystemReducedMotion(mediaQuery.matches);
    mediaQuery.addEventListener?.("change", syncMotionPreference);
    return () => mediaQuery.removeEventListener?.("change", syncMotionPreference);
  }, []);

  useEffect(() => {
    const states = new Map();
    const clearTimers = (state) => {
      window.clearTimeout(state.typingTimer);
      window.clearInterval(state.blinkTimer);
      state.typingTimer = undefined;
      state.blinkTimer = undefined;
    };
    const render = (control, state) => {
      control.setAttribute(SOURCE_ATTRIBUTE, state.source);
      control.setAttribute("placeholder", getTypingFrame(state.source, state.visibleCharacters, state.cursorVisible));
    };
    const stop = (control, restore = true) => {
      const state = states.get(control);
      if (!state) return;
      clearTimers(state);
      state.active = false;
      control.classList.remove(ACTIVE_CLASS);
      if (restore && control.isConnected) control.setAttribute("placeholder", state.source);
    };
    const start = (control) => {
      const source = getSource(control);
      if (!source) return;

      const state = states.get(control) || {
        source,
        active: false,
        visibleCharacters: 0,
        cursorVisible: true,
        typingTimer: undefined,
        blinkTimer: undefined,
      };
      state.source = source;
      states.set(control, state);
      clearTimers(state);
      if (reduceMotion || systemReducedMotion || !isEmpty(control)) {
        state.visibleCharacters = Array.from(source).length;
        state.cursorVisible = false;
        state.active = false;
        control.classList.remove(ACTIVE_CLASS);
        control.setAttribute("placeholder", source);
        return;
      }

      state.active = true;
      state.visibleCharacters = 0;
      state.cursorVisible = true;
      control.classList.add(ACTIVE_CLASS);
      render(control, state);

      const typeNextCharacter = () => {
        if (!state.active || !control.isConnected || !isEmpty(control)) {
          stop(control);
          return;
        }
        state.visibleCharacters += 1;
        state.cursorVisible = true;
        render(control, state);
        if (state.visibleCharacters < Array.from(state.source).length) {
          state.typingTimer = window.setTimeout(typeNextCharacter, getTypingDelay(68, 22));
        } else {
          state.typingTimer = undefined;
        }
      };

      state.typingTimer = window.setTimeout(typeNextCharacter, START_DELAY);
      state.blinkTimer = window.setInterval(() => {
        if (!state.active || !control.isConnected || !isEmpty(control)) {
          stop(control);
          return;
        }
        state.cursorVisible = !state.cursorVisible;
        render(control, state);
      }, CURSOR_BLINK_INTERVAL);
    };
    const register = (control) => {
      if (states.has(control)) return;
      if (getSource(control)) start(control);
    };
    const registerTree = (node) => {
      if (!(node instanceof Element)) return;
      if (node.matches(TYPING_CONTROL_SELECTOR)) register(node);
      node.querySelectorAll(TYPING_CONTROL_SELECTOR).forEach(register);
    };
    const unregisterTree = (node) => {
      if (!(node instanceof Element)) return;
      if (states.has(node)) {
        stop(node, false);
        states.delete(node);
      }
      node.querySelectorAll(TYPING_CONTROL_SELECTOR).forEach((control) => {
        if (states.has(control)) {
          stop(control, false);
          states.delete(control);
        }
      });
    };
    const handleInput = (event) => {
      const control = event.target;
      if (!(control instanceof Element) || !control.matches(TYPING_CONTROL_SELECTOR)) return;
      if (control.value) stop(control);
      else start(control);
    };

    document.querySelectorAll(TYPING_CONTROL_SELECTOR).forEach(register);
    document.addEventListener("input", handleInput, true);
    document.addEventListener("change", handleInput, true);
    const observer = new MutationObserver((records) => {
      records.forEach((record) => {
        record.addedNodes.forEach(registerTree);
        record.removedNodes.forEach(unregisterTree);
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      document.removeEventListener("input", handleInput, true);
      document.removeEventListener("change", handleInput, true);
      states.forEach((state, control) => {
        clearTimers(state);
        control.classList.remove(ACTIVE_CLASS);
        if (control.isConnected) control.setAttribute("placeholder", state.source);
      });
      states.clear();
    };
  }, [reduceMotion, systemReducedMotion]);

  return null;
}
