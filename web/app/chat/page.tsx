import { ChatInterface } from "@/components/ChatInterface";
import { VoiceButton } from "@/components/VoiceButton";

export default function ChatPage() {
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <header>
        <h1 className="text-3xl font-semibold">Estate chat</h1>
      </header>
      <VoiceButton />
      <ChatInterface />
    </main>
  );
}

