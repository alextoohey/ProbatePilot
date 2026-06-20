import { NextRequest, NextResponse } from "next/server";
import { transcribeAudio } from "@/lib/deepgram";
import { withSentrySpan } from "@/lib/sentry";

export async function POST(request: NextRequest) {
  return withSentrySpan("voice.transcribe", async () => {
    const audio = await request.arrayBuffer();
    const transcript = await transcribeAudio(audio);
    return NextResponse.json({ transcript });
  });
}

