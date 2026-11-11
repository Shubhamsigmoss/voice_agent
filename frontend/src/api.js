const BASE = import.meta.env.VITE_API_BASE || "";

async function handle(res) {
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function fetchOutlets() {
  return handle(await fetch(`${BASE}/api/outlets`));
}

export async function sendChat(messages, outlet) {
  return handle(
    await fetch(`${BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, outlet }),
    })
  );
}

export async function transcribe(blob) {
  const ext = blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") ? "mp4" : "webm";
  const fd = new FormData();
  fd.append("audio", blob, `question.${ext}`);
  const data = await handle(await fetch(`${BASE}/api/stt`, { method: "POST", body: fd }));
  return data.text;
}
