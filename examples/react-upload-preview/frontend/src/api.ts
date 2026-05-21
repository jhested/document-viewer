const BACKEND = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:5099";

export type Document = {
  key: string;
  name: string;
  size: number;
  lastModified: string;
};

export type PresignResponse = {
  uploadUrl: string;
  objectKey: string;
  contentType: string;
};

export type ViewerTokenResponse = {
  token: string;
  embedUrl: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${text ? `: ${text}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listDocuments: (user: string) =>
    request<Document[]>(`/api/documents?user=${encodeURIComponent(user)}`),

  presignUpload: (user: string, file: File) =>
    request<PresignResponse>("/api/uploads", {
      method: "POST",
      body: JSON.stringify({
        fileName: file.name,
        contentType: file.type || "application/octet-stream",
        user,
      }),
    }),

  mintViewerToken: (user: string, objectKey: string) =>
    request<ViewerTokenResponse>("/api/viewer-token", {
      method: "POST",
      body: JSON.stringify({ objectKey, user, case: "default" }),
    }),

  uploadToS3: async (presign: PresignResponse, file: File) => {
    const res = await fetch(presign.uploadUrl, {
      method: "PUT",
      headers: { "Content-Type": presign.contentType },
      body: file,
    });
    if (!res.ok) throw new Error(`S3 upload failed: ${res.status}`);
  },
};
