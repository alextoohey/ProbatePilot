export async function transcribeAudio(_audio: ArrayBuffer): Promise<string> {
  return "Placeholder transcript. Wire Deepgram STT here.";
}

export async function synthesizeSpeech(_text: string): Promise<ArrayBuffer> {
  return new ArrayBuffer(0);
}

