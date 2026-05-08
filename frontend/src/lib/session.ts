const KEY = "tribe-virality:session-id";

export function getSessionId(): string {
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(KEY, id);
  }
  return id;
}

export function resetSession(): void {
  localStorage.removeItem(KEY);
}
