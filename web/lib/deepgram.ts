import { createClient } from "@deepgram/sdk";

function getClient() {
  const apiKey = process.env.DEEPGRAM_API_KEY;
  if (!apiKey) {
    throw new Error("DEEPGRAM_API_KEY is not set");
  }
  return createClient(apiKey);
}

/**
 * Speech-to-text. Takes raw audio bytes (e.g. webm/opus from MediaRecorder)
 * and returns the transcript text.
 */
export async function transcribeAudio(audio: ArrayBuffer): Promise<string> {
  const deepgram = getClient();
  const { result, error } = await deepgram.listen.prerecorded.transcribeFile(
    Buffer.from(audio),
    {
      model: "nova-2",
      smart_format: true,
      punctuate: true,
    }
  );

  if (error) {
    throw new Error(`Deepgram STT failed: ${error.message ?? error}`);
  }

  return result?.results?.channels?.[0]?.alternatives?.[0]?.transcript ?? "";
}

/**
 * Text-to-speech. Takes response text and returns MP3 audio bytes
 * for playback in the browser.
 */
export async function synthesizeSpeech(text: string): Promise<ArrayBuffer> {
  const deepgram = getClient();
  const response = await deepgram.speak.request(
    { text },
    {
      model: "aura-asteria-en",
      encoding: "mp3",
    }
  );

  const stream = await response.getStream();
  if (!stream) {
    throw new Error("Deepgram TTS returned no audio stream");
  }

  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value) chunks.push(value);
  }

  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const merged = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }

  return merged.buffer;
}
