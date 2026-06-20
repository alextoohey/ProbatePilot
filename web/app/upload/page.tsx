import { DocumentUpload } from "@/components/DocumentUpload";

export default function UploadPage() {
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-3xl font-semibold">Upload documents</h1>
      <DocumentUpload />
    </main>
  );
}

