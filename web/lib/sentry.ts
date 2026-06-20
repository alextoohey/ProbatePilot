export async function withSentrySpan<T>(_name: string, action: () => Promise<T>): Promise<T> {
  return action();
}

