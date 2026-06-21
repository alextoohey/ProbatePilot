import { redirect } from "next/navigation";

// The chat now lives inside the app shell (Chat tab). Redirect legacy /chat to it.
export default function ChatPage() {
  redirect("/");
}
