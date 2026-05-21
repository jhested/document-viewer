import { useCallback, useEffect, useState } from "react";
import { api, type Document } from "./api";

export default function App() {
  const [user, setUser] = useState<string>(() => localStorage.getItem("user") ?? "");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selected, setSelected] = useState<Document | null>(null);
  const [embedUrl, setEmbedUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!user) return;
    try {
      setDocuments(await api.listDocuments(user));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [user]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const onUpload = async (file: File) => {
    setError(null);
    setUploading(true);
    try {
      const presign = await api.presignUpload(user, file);
      await api.uploadToS3(presign, file);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const onPreview = async (doc: Document) => {
    setError(null);
    setSelected(doc);
    setEmbedUrl(null);
    try {
      const r = await api.mintViewerToken(user, doc.key);
      setEmbedUrl(r.embedUrl);
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
            if (e.key === "Enter") {
              const v = (e.target as HTMLInputElement).value.trim();
              if (/^[A-Za-z0-9._-]{1,64}$/.test(v)) {
                localStorage.setItem("user", v);
                setUser(v);
              }
            }
          }}
        />
        <small>letters, digits, dot, dash, underscore — up to 64 chars</small>
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
            setSelected(null);
            setEmbedUrl(null);
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
                <li key={d.key} className={selected?.key === d.key ? "selected" : ""}>
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
          {embedUrl ? (
            <iframe src={embedUrl} title="document preview" />
          ) : (
            <div className="empty">
              <p>{selected ? "loading…" : "Select a document on the left to preview."}</p>
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
