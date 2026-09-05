export function createUnityBridge(iframe, targetOrigin = globalThis.location?.origin || "*") {
  const send = (type, value) => iframe?.contentWindow?.postMessage({ source: "campusmate", type, value }, targetOrigin);
  return {
    setSpeaking: (value) => send("speech-state", Boolean(value)),
    setSpeechLevel: (value) => send("speech-level", Math.max(0, Math.min(1, Number(value) || 0))),
    stop: () => send("speech-stop", true),
  };
}
