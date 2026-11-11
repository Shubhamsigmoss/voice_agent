import { useEffect, useRef, useState } from "react";
import { fetchOutlets, sendChat, transcribe } from "./api.js";
import { MicIcon, PlayIcon, SendIcon, SpeakerIcon, StopIcon } from "./icons.jsx";
import ReportCard from "./ReportCard.jsx";
import { speak, stopSpeaking } from "./speech.js";
import { useRecorder } from "./useRecorder.js";

const SUGGESTIONS = [
  "What are today's sales?",
  "Show date-wise sales for this month",
  "Top 5 items this week",
  "Cash vs online collection today",
  "Compare today with the same day last week",
  "How much came from Swiggy and Zomato last month?",
];

let nextId = 1;

function clock(s) {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default function App() {
  const [messages, setMessages] = useState([]); // {id, role, content, visuals?, error?}
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(null); // null | "listening" | "transcribing" | "thinking"
  const [outlets, setOutlets] = useState([]);
  const [outletId, setOutletId] = useState(0);
  const [voiceOn, setVoiceOn] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [backendError, setBackendError] = useState("");
  const rec = useRecorder();
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    fetchOutlets()
      .then(setOutlets)
      .catch((e) => setBackendError(e.message));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  async function ask(text, fromVoice = false) {
    const q = text.trim();
    if (!q || (busy && !fromVoice)) return;
    stopSpeaking();
    setSpeaking(false);
    setInput("");
    const userMsg = { id: nextId++, role: "user", content: q };
    const history = [...messages, userMsg];
    setMessages(history);
    setBusy("thinking");
    try {
      const outlet = outlets.find((o) => o.id === Number(outletId));
      const res = await sendChat(
        history.filter((m) => !m.error).map(({ role, content }) => ({ role, content })),
        outlet ? { id: outlet.id, name: outlet.name } : null
      );
      setMessages((m) => [...m, { id: nextId++, role: "assistant", content: res.answer, visuals: res.visuals }]);
      if (voiceOn) {
        setSpeaking(true);
        speak(res.answer, () => setSpeaking(false));
      }
    } catch (e) {
      setMessages((m) => [...m, { id: nextId++, role: "assistant", content: `Couldn't get that report. ${e.message}`, error: true }]);
    } finally {
      setBusy(null);
    }
  }

  async function stopAndSend() {
    const blob = await rec.stop();
    if (!blob || blob.size < 1500) {
      setBusy(null);
      return;
    }
    setBusy("transcribing");
    try {
      const text = await transcribe(blob);
      if (text) await ask(text, true);
      else setBusy(null);
    } catch (e) {
      setMessages((m) => [...m, { id: nextId++, role: "assistant", content: `Couldn't hear that clearly. ${e.message}`, error: true }]);
      setBusy(null);
    }
  }

  async function toggleMic() {
    if (rec.recording) return stopAndSend();
    if (busy) return;
    stopSpeaking();
    setSpeaking(false);
    try {
      await rec.start(() => stopAndSend());
      setBusy("listening");
    } catch (e) {
      setMessages((m) => [
        ...m,
        { id: nextId++, role: "assistant", content: `The microphone is blocked. Allow microphone access in the browser and try again. (${e.message})`, error: true },
      ]);
    }
  }

  function replay(text) {
    stopSpeaking();
    setSpeaking(true);
    speak(text, () => setSpeaking(false));
  }

  const status =
    busy === "listening"
      ? `Listening ${clock(rec.seconds)}. Tap the mic again when you're done.`
      : busy === "transcribing"
      ? "Turning your voice into text…"
      : busy === "thinking"
      ? "Checking the numbers…"
      : speaking
      ? "Reading the answer aloud…"
      : "Tap the mic to ask, or type below.";

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="mark" aria-hidden>
            ₹
          </span>
          <span className="brand-name">Sales assistant</span>
        </div>
        <div className="controls">
          <label className="outlet">
            <span className="sr-only">Outlet</span>
            <select value={outletId} onChange={(e) => setOutletId(Number(e.target.value))}>
              <option value={0}>All outlets</option>
              {outlets.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          <button
            className="icon-btn"
            aria-pressed={voiceOn}
            aria-label={voiceOn ? "Answers are read aloud. Turn off" : "Answers are silent. Turn on reading aloud"}
            title={voiceOn ? "Reading answers aloud" : "Answers are silent"}
            onClick={() => {
              setVoiceOn((v) => !v);
              stopSpeaking();
              setSpeaking(false);
            }}
          >
            <SpeakerIcon muted={!voiceOn} />
          </button>
        </div>
      </header>

      {backendError && (
        <div className="banner" role="alert">
          Can't reach the sales server: {backendError}. Check that the backend is running, then reload this page.
        </div>
      )}

      <main className="thread">
        <div className="thread-inner">
          {messages.length === 0 && (
            <section className="empty">
              <h1>Ask about your sales</h1>
              <p>Speak in English, Hindi or Hinglish. You'll hear the answer and see the numbers here.</p>
              <ul className="suggest">
                {SUGGESTIONS.map((s) => (
                  <li key={s}>
                    <button onClick={() => ask(s)} disabled={!!busy}>
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {messages.map((m) =>
            m.role === "user" ? (
              <p key={m.id} className="q">
                {m.content}
              </p>
            ) : m.error ? (
              <p key={m.id} className="err" role="alert">
                {m.content}
              </p>
            ) : (
              <article key={m.id} className="a">
                <p className="answer">{m.content}</p>
                {voiceOn && (
                  <button className="replay" onClick={() => replay(m.content)}>
                    <PlayIcon /> Play answer
                  </button>
                )}
                {m.visuals?.map((v, i) => (
                  <ReportCard key={i} report={v} />
                ))}
              </article>
            )
          )}

          {busy === "thinking" && (
            <p className="thinking" aria-live="polite">
              Checking the numbers<span className="dots" aria-hidden />
            </p>
          )}
          <div ref={endRef} />
        </div>
      </main>

      <footer className="dock">
        <div className="dock-inner">
          <button
            type="button"
            className={`mic ${rec.recording ? "live" : ""}`}
            onClick={toggleMic}
            disabled={!!busy && !rec.recording}
            aria-label={rec.recording ? "Stop and send" : "Ask by voice"}
          >
            {rec.recording ? <StopIcon width={26} height={26} /> : <MicIcon width={28} height={28} />}
          </button>
          <form
            className="ask"
            onSubmit={(e) => {
              e.preventDefault();
              ask(input);
            }}
          >
            <label className="sr-only" htmlFor="q">
              Type a question
            </label>
            <input
              id="q"
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type a question"
              autoComplete="off"
              disabled={!!busy}
            />
            <button type="submit" className="send" disabled={!!busy || !input.trim()} aria-label="Ask">
              <SendIcon />
            </button>
          </form>
        </div>
        <p className={`status ${busy === "listening" ? "is-live" : ""}`} aria-live="polite">
          {status}
        </p>
      </footer>
    </div>
  );
}
