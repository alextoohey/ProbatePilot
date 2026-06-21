"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string };
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html>
      <body>
        <main className="mx-auto max-w-3xl p-6">
          <h1 className="text-2xl font-semibold">Something went wrong</h1>
          <p className="mt-2 text-slate-600">
            The error has been logged. Please refresh and try again.
          </p>
        </main>
      </body>
    </html>
  );
}
