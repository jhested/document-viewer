import { useEffect, useState } from "react";
import { api, USER_PATTERN, type Document } from "./api";

type Preview = { doc: Document; url: string | null };

export default function App() {
  const [user, setUser] = useState<string>(() => localStorage.getItem("user") ?? "");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api.listDocuments(user).then(setDocuments).catch((e) => setError((e as Error).message));
  }, [user]);

  const onUpload = async (file: File) => {
    setError(null);
    setUploading(true);
    try {
      const presign = await api.presignUpload(user, file);
      await api.uploadToS3(presign, file);
      setDocuments(await api.listDocuments(user));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const onPreview = async (doc: Document) => {
    setError(null);
    setPreview({ doc, url: null });
    try {
      const r = await api.mintViewerToken(user, doc.key);
      // Guard against a stale resolve: only update if this is still the
      // doc the user is looking at.
      setPreview((curr) => (curr?.doc.key === doc.key ? { doc, url: r.embedUrl } : curr));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (!user) {
    return (
      <div className="login">
        <h1>document-viewer demo</h1>
        <p>Enter a username — uploads are namespaced under it.</p>
        <input
          autoFocus
          placeholder="username"
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            const v = (e.target as HTMLInputElement).value.trim();
            if (USER_PATTERN.test(v)) {
              localStorage.setItem("user", v);
              setUser(v);
            } else {
              setError("invalid username — letters, digits, dot, dash, underscore only");
            }
          }}
        />
        <small>letters, digits, dot, dash, underscore — up to 64 chars</small>
        {error && <div className="error">{error}</div>}
      </div>
    );
  }

  return (
    <div className="app">
      <header>
        <h1>document-viewer demo</h1>
        <span className="user">{user}</span>
        <button
          onClick={() => {
            localStorage.removeItem("user");
            setUser("");
            setDocuments([]);
            setPreview(null);
          }}
        >
          logout
        </button>
      </header>

      {error && <div className="error">{error}</div>}

      <div className="body">
        <section className="sidebar">
          <label className="upload">
            <input
              type="file"
              disabled={uploading}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onUpload(f);
                e.target.value = "";
              }}
            />
            <span>{uploading ? "uploading…" : "+ upload a document"}</span>
          </label>

          {documents.length === 0 ? (
            <p className="muted">No documents yet.</p>
          ) : (
            <ul>
              {documents.map((d) => (
                <li key={d.key} className={preview?.doc.key === d.key ? "selected" : ""}>
                  <button onClick={() => onPreview(d)}>
                    <span className="name">{d.name}</span>
                    <small>{(d.size / 1024).toFixed(1)} KB</small>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <main>
          {preview?.url ? (
            <iframe src={preview.url} title="document preview" />
          ) : (
            <div className="empty">
              <p>{preview ? "loading…" : "Select a document on the left to preview."}</p>
              <p className="muted small">
                The preview pane is the document-viewer's <code>/embed/{"{jwt}"}</code> page
                served by the viewer-api itself; this React app only mints the token.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
