import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Brain, TrendingUp, Zap } from "lucide-react";
import { DropZone } from "../components/DropZone";
import { CapabilityBanner } from "../components/CapabilityBanner";
import { useCapabilities } from "../hooks/useCapabilities";
import { api } from "../lib/api";

export default function Landing() {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: capabilities, loading: capsLoading } = useCapabilities();

  const handleFile = async (file: File) => {
    setError(null);
    setUploading(true);
    try {
      const { job_id } = await api.upload(file);
      navigate(`/processing/${job_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed. Please try again.");
      setUploading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-16 flex flex-col items-center gap-14">
      {/* Hero */}
      <div className="text-center flex flex-col gap-4">
        <h1 className="text-4xl font-bold tracking-tight text-ink">
          How viral will your video be?
        </h1>
        <p className="text-ink-muted text-lg leading-relaxed max-w-xl">
          Upload your content and see how a human brain would respond —
          predicted by Meta's TRIBE v2 foundation model.
        </p>
      </div>

      {/* Capability banner */}
      <CapabilityBanner capabilities={capabilities} loading={capsLoading} />

      {/* Drop zone */}
      <DropZone onFile={handleFile} disabled={uploading} />
      {uploading && (
        <p className="text-accent text-sm animate-pulse -mt-8">Uploading…</p>
      )}
      {error && (
        <p className="text-bad text-sm -mt-8">{error}</p>
      )}

      {/* How it works */}
      <div className="w-full grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          {
            icon: <Zap className="w-5 h-5 text-accent" />,
            title: "Upload",
            body: "Drop any MP4, MOV, or WebM up to 60s.",
          },
          {
            icon: <Brain className="w-5 h-5 text-accent" />,
            title: "Predict",
            body: "TRIBE v2 predicts fMRI brain activity frame by frame.",
          },
          {
            icon: <TrendingUp className="w-5 h-5 text-accent" />,
            title: "Score",
            body: "See your virality score and edit to improve it.",
          },
        ].map(({ icon, title, body }) => (
          <div key={title} className="card p-5 flex flex-col gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
              {icon}
            </div>
            <p className="font-medium text-sm text-ink">{title}</p>
            <p className="text-xs text-ink-muted leading-relaxed">{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
