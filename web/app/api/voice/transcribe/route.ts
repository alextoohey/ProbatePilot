import { NextRequest, NextResponse } from "next/server";
import { isDeepgramConfigured, transcribeAudio } from "@/lib/deepgram";
import { withSentrySpan } from "@/lib/sentry";

export async function POST(request: NextRequest) {
  if (!isDeepgramConfigured()) {
    return NextResponse.json({ error: "voice_not_configured" }, { status: 503 });
  }
  return withSentrySpan("voice.transcribe", async () => {
    const audio = await request.arrayBuffer();
    const transcript = await transcribeAudio(audio);
    return NextResponse.json({ transcript });
  });
}

