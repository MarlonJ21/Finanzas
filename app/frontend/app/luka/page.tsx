"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Bot, Mic, Play, Send, Square, Trash2, Volume2 } from "lucide-react";
import { getApiBase } from "../../lib/api";

type Message = {
  role: "user" | "assistant";
  text: string;
  card?: Record<string, any> | null;
  audio?: boolean;
  fallback_used?: boolean;
  fallback_reason?: string | null;
  provider?: string;
  model?: string | null;
};
const prompts = ["¿Cómo voy este mes?", "¿En qué he gastado más?", "¿Cuánto puedo gastar?", "¿Puedo comprar algo de $80?", "¿Cómo voy esta quincena?"];

function formatModelTag(provider?: string, model?: string | null, fallback?: boolean) {
  if (fallback || provider === "deterministic") {
    return { name: "Modo Local", type: "local" };
  }
  if (provider === "deepseek") {
    return { name: "DeepSeek V3", type: "deepseek" };
  }
  if (provider === "kimi") {
    return { name: "Kimi", type: "kimi" };
  }
  if (provider === "gemini") {
    return { name: "Gemini", type: "gemini" };
  }
  if (provider === "openrouter") {
    const short = model ? model.split("/").pop()?.replace(/:free$/, "") : "AI";
    return { name: `OpenRouter · ${short}`, type: "openrouter" };
  }
  if (provider === "groq") {
    return { name: "Groq", type: "groq" };
  }
  return { name: provider ? provider.toUpperCase() : "IA", type: "ai" };
}

function formatInline(text: string) {
  const parts = text.split(/(\*\*[^*]+?\*\*|`[^`]+?`|\*[^*]+?\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
      return <strong key={idx}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
      return <code key={idx} className="luka-code">{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length >= 2) {
      return <em key={idx}>{part.slice(1, -1)}</em>;
    }
    return part;
  });
}

function FormattedText({ content }: { content: string }) {
  const paragraphs = content.split(/\n\n+/);
  return (
    <div className="luka-formatted-text">
      {paragraphs.map((para, pIdx) => {
        const lines = para.split("\n");
        const isList = lines.length > 1 && lines.every((l) => /^\s*[-*•]\s+/.test(l));
        if (isList) {
          return (
            <ul key={pIdx} className="luka-list">
              {lines.map((line, lIdx) => (
                <li key={lIdx}>{formatInline(line.replace(/^\s*[-*•]\s+/, ""))}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={pIdx}>
            {lines.map((line, lIdx) => (
              <span key={lIdx}>
                {lIdx > 0 && <br />}
                {formatInline(line)}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}

export default function LukaPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recorded, setRecorded] = useState<Blob | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [autoVoice, setAutoVoice] = useState(true);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const recognitionRef = useRef<any>(null);
  const speechTranscriptRef = useRef<string>("");
  const [transcribedPreview, setTranscribedPreview] = useState("");

  useEffect(() => {
    setAutoVoice(localStorage.getItem("luka-auto-voice") !== "false");
    return () => {
      stream.current?.getTracks().forEach((track) => track.stop());
      if (timer.current) clearInterval(timer.current);
      window.speechSynthesis?.cancel();
      try { recognitionRef.current?.stop(); } catch {}
    };
  }, []);

  function speak(text: string) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const clean = text.replace(/[*_`#]/g, "").trim();
    const utterance = new SpeechSynthesisUtterance(clean);
    const voices = window.speechSynthesis.getVoices();
    utterance.voice = voices.find((v) => ["es-VE", "es-419", "es-US", "es-ES"].includes(v.lang)) ?? null;
    utterance.lang = utterance.voice?.lang ?? "es-419";
    window.speechSynthesis.speak(utterance);
  }

  async function send(text = input, fromAudio = false) {
    const message = text.trim();
    if (!message || busy) return;
    setBusy(true); setError(""); setInput(""); setTranscribedPreview("");
    setMessages((items) => [...items, { role: "user", text: message, audio: fromAudio }]);
    try {
      const response = await fetch(`${getApiBase()}/luka/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, conversation_id: conversationId || undefined, page_context: { route: "/luka" }, response_mode: fromAudio ? "audio" : "text", history: messages.slice(-6).map(({ role, text }) => ({ role, content: text })) }),
      });
      if (!response.ok) throw new Error("No pude consultar tus números ahora. Intenta otra vez en un momento.");
      const data = await response.json();
      setConversationId(data.conversation_id);
      setMessages((items) => [...items, {
        role: "assistant",
        text: data.message,
        card: data.structured_cards,
        fallback_used: data.fallback_used,
        fallback_reason: data.fallback_reason,
        provider: data.provider,
        model: data.model,
      }]);
      if (fromAudio && autoVoice) speak(data.message);
    } catch (e) { setError(e instanceof Error ? e.message : "No pude enviar tu mensaje."); }
    finally { setBusy(false); }
  }

  async function startRecording() {
    setError("");
    const SpeechRecognitionClass = typeof window !== "undefined" ? ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition) : null;

    if (SpeechRecognitionClass) {
      try {
        const recognizer = new SpeechRecognitionClass();
        recognizer.lang = "es-VE";
        recognizer.continuous = true;
        recognizer.interimResults = true;

        recognizer.onstart = () => {
          setRecording(true);
          setSeconds(0);
        };

        recognizer.onresult = (event: any) => {
          let full = "";
          for (let i = 0; i < event.results.length; ++i) {
            full += event.results[i][0].transcript;
          }
          if (full.trim()) {
            speechTranscriptRef.current = full.trim();
            setInput(full.trim());
            setTranscribedPreview(full.trim());
          }
        };

        recognizer.onerror = (event: any) => {
          console.warn("SpeechRec error:", event.error);
          if (event.error === "not-allowed" || event.error === "permission-denied") {
            setError("Permiso de micrófono denegado. Permite el micrófono en tu navegador.");
          } else if (event.error === "network") {
            setError("No se pudo conectar al servicio de voz. Puedes escribir tu pregunta.");
          }
          stopRecording();
        };

        recognizer.onend = () => {
          setRecording(false);
          if (timer.current) clearInterval(timer.current);
        };

        recognizer.start();
        recognitionRef.current = recognizer;
        setRecording(true);
        setSeconds(0);

        timer.current = setInterval(() => setSeconds((n) => {
          if (n >= 59) { stopRecording(); return 60; }
          return n + 1;
        }), 1000);
        return;
      } catch (err) {
        console.warn("SpeechRecognition start failed, falling back to MediaRecorder", err);
      }
    }

    // Fallback: MediaRecorder if SpeechRecognition is not supported
    try {
      speechTranscriptRef.current = "";
      setTranscribedPreview("");
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = media;
      chunks.current = [];
      const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((type) => MediaRecorder.isTypeSupported(type));
      const instance = new MediaRecorder(media, mime ? { mimeType: mime } : undefined);
      recorder.current = instance;
      instance.ondataavailable = (event) => { if (event.data.size) chunks.current.push(event.data); };
      instance.onstop = () => {
        setRecorded(new Blob(chunks.current, { type: instance.mimeType || "audio/webm" }));
        media.getTracks().forEach((track) => track.stop());
      };
      instance.start();
      setRecording(true);
      setSeconds(0);
      timer.current = setInterval(() => setSeconds((n) => {
        if (n >= 59) { stopRecording(); return 60; }
        return n + 1;
      }), 1000);
    } catch {
      setError("No pude acceder al micrófono. Puedes escribir tu pregunta.");
    }
  }

  function stopRecording() {
    setRecording(false);
    if (timer.current) clearInterval(timer.current);
    try { recognitionRef.current?.stop(); } catch {}
    try { recorder.current?.stop(); } catch {}
  }

  async function sendRecording() {
    const textToSend = speechTranscriptRef.current.trim() || input.trim();
    if (textToSend) {
      speechTranscriptRef.current = "";
      setRecorded(null);
      setTranscribedPreview("");
      await send(textToSend, true);
      return;
    }

    if (!recorded || busy) return;
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("file", recorded, "voice.webm");
    try {
      const res = await fetch(`${getApiBase()}/luka/transcribe`, { method: "POST", body: form });
      if (!res.ok) throw new Error("No pude procesar el audio ahora mismo. Puedes escribir tu pregunta.");
      const data = await res.json();
      setRecorded(null);
      setTranscribedPreview("");
      if (!data.text) throw new Error("No logré entender el audio. Puedes escribir tu pregunta.");
      setBusy(false);
      await send(data.text, true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No pude procesar el audio.");
      setBusy(false);
    }
  }

  function submit(event: FormEvent) { event.preventDefault(); void send(); }

  return <section className="luka-page">
    <header className="luka-header"><span className="luka-avatar"><Bot size={23} /></span><div><p className="eyebrow">Asistente financiero personal</p><h1>LUKA</h1><p className="subtle">Pregúntame por tus gastos o simula una compra.</p></div><label className="luka-voice-toggle"><input type="checkbox" checked={autoVoice} onChange={(e) => { setAutoVoice(e.target.checked); localStorage.setItem("luka-auto-voice", String(e.target.checked)); }} /> Voz al enviar audio</label></header>
    <div className="luka-chat" aria-live="polite">
      {!messages.length ? <div className="luka-welcome"><span className="luka-avatar large"><Bot size={30} /></span><h2>¿En qué te ayudo?</h2><p>Reviso tus números reales y también podemos simular compras.</p><div className="luka-prompts">{prompts.map((q) => <button className="secondary-button" key={q} onClick={() => void send(q)}>{q}</button>)}</div></div> : null}
      {messages.map((m, i) => {
        const tag = m.role === "assistant" ? formatModelTag(m.provider, m.model, m.fallback_used) : null;
        return (
          <article className={`luka-message ${m.role}`} key={i}>
            <div className="luka-bubble">
              {m.audio ? <span className="luka-transcript">Tú · audio · transcripción</span> : null}
              <FormattedText content={m.text} />
              {m.role === "assistant" && tag ? (
                <div className="luka-bubble-footer">
                  <div
                    className={`luka-model-tag ${tag.type}`}
                    title={m.fallback_reason || `Motor: ${tag.name}`}
                  >
                    <span className={`luka-tag-dot ${tag.type}`} />
                    <span>{tag.name}</span>
                    {m.fallback_used && m.fallback_reason ? (
                      <span className="luka-tag-hint">· {m.fallback_reason}</span>
                    ) : null}
                  </div>
                  <button className="luka-play" onClick={() => speak(m.text)} title="Escuchar respuesta">
                    <Volume2 size={13} />
                    <span>Escuchar</span>
                  </button>
                </div>
              ) : null}
            </div>
            {m.card ? <DataCard card={m.card} /> : null}
          </article>
        );
      })}
      {busy ? <p className="luka-thinking">Luka está revisando tus números…</p> : null}
    </div>
    {error ? <div className="alert-item red" role="alert">{error}</div> : null}
    {recording ? (
      <div className="luka-recording">
        <span className="luka-record-dot" /> Grabando {`0:${String(seconds).padStart(2, "0")}`}
        {transcribedPreview ? <span style={{ marginLeft: 8, opacity: 0.8, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>"{transcribedPreview}"</span> : null}
        <button className="secondary-button" onClick={() => { recorder.current?.stop(); setRecording(false); setRecorded(null); setTranscribedPreview(""); if (timer.current) clearInterval(timer.current); try { recognitionRef.current?.stop(); } catch {} }}>Cancelar</button>
        <button className="primary-button" onClick={stopRecording}><Square size={15} /> Detener</button>
      </div>
    ) : (recorded || transcribedPreview) ? (
      <div className="luka-recording">
        <span>Audio listo · {seconds}s{transcribedPreview ? ` ("${transcribedPreview.length > 30 ? transcribedPreview.slice(0, 30) + '...' : transcribedPreview}")` : ""}</span>
        <button className="ghost-button" aria-label="Descartar audio" onClick={() => { setRecorded(null); setTranscribedPreview(""); }}><Trash2 size={17} /></button>
        <button className="primary-button" disabled={busy} onClick={() => void sendRecording()}><Send size={15} /> Transcribir y enviar</button>
      </div>
    ) : null}
    <form className="luka-composer" onSubmit={submit}><button type="button" className="luka-mic" aria-label={recording ? "Detener grabación" : "Grabar audio"} disabled={busy} onClick={() => recording ? stopRecording() : void startRecording()}><Mic size={20} /></button><input aria-label="Escribe tu pregunta" value={input} onChange={(e) => setInput(e.target.value)} maxLength={4000} placeholder="Pregúntale a LUKA…" /><button className="primary-button" type="submit" disabled={!input.trim() || busy}><Send size={17} /><span>Enviar</span></button></form>
    <p className="luka-disclaimer">LUKA consulta y simula; no cambia tus datos financieros.</p>
  </section>;
}

function DataCard({ card }: { card: Record<string, any> }) {
  const pairs: [string, any][] = [];
  const add = (key: string, label: string) => { if (card[key] !== undefined && card[key] !== null && typeof card[key] !== "object") pairs.push([label, card[key]]); };
  add("price_usd", "Compra"); add("monthly_available_before", "Disponible mensual antes"); add("monthly_available_after", "Disponible mensual después");
  add("monthly_available_after_down_payment", "Disponible tras la inicial"); add("safe_to_spend_before", "Safe to Spend antes"); add("safe_to_spend_after", "Safe to Spend después");
  add("biweekly_available_before", "Quincena antes"); add("biweekly_available_after", "Quincena después"); add("down_payment_usd", "Inicial"); add("financed_amount", "Monto financiado");
  add("installment_usd", "Monto por cuota"); add("new_future_commitment", "Compromiso futuro");
  const items = card.items as { label?: string; amount_usd?: number }[] | undefined;
  if (!pairs.length && !items?.length) return null;
  return <div className="luka-card">{pairs.map(([label, value]) => <div key={label}><span>{label}</span><strong>{typeof value === "number" ? `$${value.toFixed(2)}` : String(value)}</strong></div>)}{items?.map((item, i) => <div key={i}><span>{item.label}</span><strong>${Number(item.amount_usd ?? 0).toFixed(2)}</strong></div>)}</div>;
}
