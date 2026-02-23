import { HttpErrorResponse } from "@angular/common/http";

export function extractApiErrorMessages(err: unknown, generic: string): string[] {
  // Angular HttpErrorResponse
  if (err instanceof HttpErrorResponse) {
    // Network / CORS / no response body
    if (err.status === 0) {
      return ['Network error. Please check your connection and try again.'];
    }

    const body = err.error;

    // Sometimes backend returns plain text
    if (typeof body === 'string' && body.trim().length > 0) {
      return [body];
    }

    // Sometimes backend returns { message: "..."} or { error: "..."}
    if (body && typeof body === 'object') {
      // @ts-ignore
      const obj = body as AnyObj;

      // Your FastAPI/Pydantic-like shape: { detail: [{ msg: ... }, ...] }
      if (Array.isArray(obj.detail)) {
        const msgs = obj.detail
          .map((d: any) => (typeof d?.msg === 'string' ? d.msg : null))
          .filter((m: string | null): m is string => !!m && m.trim().length > 0);

        if (msgs.length) return msgs;
      }

      // Other common shapes
      if (typeof obj.message === 'string' && obj.message.trim()) return [obj.message];
      if (typeof obj.error === 'string' && obj.error.trim()) return [obj.error];

      // Sometimes nested: { error: { message: "..." } }
      if (obj.error && typeof obj.error === 'object' && typeof obj.error.message === 'string') {
        const m = obj.error.message.trim();
        if (m) return [m];
      }
    }

    // Fallback to Angular’s message (includes status text)
    if (typeof err.message === 'string' && err.message.trim()) {
      return [err.message];
    }

    return [generic];
  }

  // Non-HttpErrorResponse errors
  if (typeof err === 'string' && err.trim()) return [err];
  // @ts-ignore
  if (err && typeof err === 'object' && typeof (err as AnyObj).message === 'string') {
    // @ts-ignore
    const m = (err as AnyObj).message.trim();
    if (m) return [m];
  }

  return [generic];
}

export function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.innerText = text;
  return div.innerHTML;
}
