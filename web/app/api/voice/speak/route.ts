import { NextRequest } from "next/server";
import { synthesizeSpeech } from "@/lib/deepgram";
import { withSentrySpan } from "@/lib/sentry";

export async function POST(request: NextRequest) {
  return withSentrySpan("voice.speak", async () => {
    const { text } = await request.json();
    const audio = await synthesizeSpeech(text);
    return new Response(audio, {
      headers: { "content-type": "audio/mpeg" },
    });
  });
}

