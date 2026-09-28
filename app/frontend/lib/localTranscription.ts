import { pipeline } from "@huggingface/transformers";

function loadTranscriber() {
  return pipeline("automatic-speech-recognition", "Xenova/whisper-tiny", { device: "wasm" });
}

let transcriberPromise: ReturnType<typeof loadTranscriber> | null = null;

export async function transcribeLocally(recording: Blob): Promise<string> {
  transcriberPromise ??= loadTranscriber();
  const transcriber = await transcriberPromise;
  const audioContext = new AudioContext();
  try {
    const decoded = await audioContext.decodeAudioData(await recording.arrayBuffer());
    const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * 16000), 16000);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const audio = await offline.startRendering();
    const result = await transcriber(audio.getChannelData(0), {
      language: "spanish",
      task: "transcribe",
      chunk_length_s: 30,
      stride_length_s: 5,
    });
    return String((result as { text?: string }).text || "").trim();
  } finally {
    await audioContext.close();
  }
}
