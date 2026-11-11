// Browser built-in Text-to-Speech (free, good enough for testing).
// For production, replace with Azure / Sarvam / ElevenLabs TTS.

const hasDevanagari = (s) => /[ऀ-ॿ]/.test(s);

function pickVoice(lang) {
  const voices = window.speechSynthesis?.getVoices() || [];
  return (
    voices.find((v) => v.lang === lang) ||
    voices.find((v) => v.lang?.startsWith(lang.split("-")[0])) ||
    null
  );
}

// "Rs 1,25,430" -> "1,25,430 rupees" so it is pronounced correctly
function speakable(text) {
  return text
    .replace(/(?:Rs\.?|₹|INR)\s?([\d,]+(?:\.\d+)?)/g, "$1 rupees")
    .replace(/[*_#`]/g, "");
}

export function speak(text, onEnd) {
  if (!window.speechSynthesis || !text) return onEnd?.();
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(speakable(text));
  const lang = hasDevanagari(text) ? "hi-IN" : "en-IN";
  u.lang = lang;
  const voice = pickVoice(lang) || pickVoice("hi-IN");
  if (voice) u.voice = voice;
  u.rate = 1.02;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
}

export function stopSpeaking() {
  window.speechSynthesis?.cancel();
}

// Chrome loads voices asynchronously
if (typeof window !== "undefined" && window.speechSynthesis) {
  window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
}
