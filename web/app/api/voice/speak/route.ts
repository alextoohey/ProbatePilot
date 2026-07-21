import { NextRequest, NextResponse } from "next/server";
import { isDeepgramConfigured, synthesizeSpeech } from "@/lib/deepgram";
import { withSentrySpan } from "@/lib/sentry";

export async function POST(request: NextRequest) {
  if (!isDeepgramConfigured()) {
    return NextResponse.json({ error: "voice_not_configured" }, { status: 503 });
  }
  return withSentrySpan("voice.speak", async () => {
    const { text } = await request.json();
    const audio = await synthesizeSpeech(text);
    return new Response(audio, {
      headers: { "content-type": "audio/mpeg" },
    });
  });
}

