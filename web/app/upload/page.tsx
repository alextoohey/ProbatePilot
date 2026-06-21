import { redirect } from "next/navigation";

// Document upload now lives inside the app shell (Documents tab). Redirect legacy /upload.
export default function UploadPage() {
  redirect("/");
}
