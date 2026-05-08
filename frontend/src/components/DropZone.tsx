import { useCallback, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { cn } from "../lib/cn";

interface DropZoneProps {
  onFile: (file: File) => void;
  disabled?: boolean;
}

const ACCEPT = ["video/mp4", "video/quicktime", "video/webm"];
const MAX_MB = 100;

export function DropZone({ onFile, disabled }: DropZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validate = (file: File): string | null => {
    if (!ACCEPT.includes(file.type) && !file.name.match(/\.(mp4|mov|webm)$/i)) {
      return "Please upload an MP4, MOV, or WebM video file.";
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      return `File exceeds ${MAX_MB} MB limit.`;
    }
    return null;
  };

  const handle = useCallback(
    (file: File) => {
      setError(null);
      const err = validate(file);
      if (err) { setError(err); return; }
      onFile(file);
    },
    [onFile],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handle(file);
    },
    [handle],
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handle(file);
    },
    [handle],
  );

  return (
    <div className="w-full flex flex-col items-center gap-3">
      <div
        onClick={() => !disabled && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={disabled ? undefined : onDrop}
        className={cn(
          "relative w-full max-w-2xl rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer select-none",
          "flex flex-col items-center justify-center gap-4 py-16 px-8 text-center",
          dragOver
            ? "border-accent bg-accent/5 shadow-glow"
            : "border-border-strong hover:border-accent/50 hover:bg-bg-raised",
          disabled && "opacity-50 cursor-not-allowed pointer-events-none",
        )}
      >
        <div className={cn(
          "rounded-full p-4 transition-colors",
          dragOver ? "bg-accent/20" : "bg-bg-raised"
        )}>
          <Upload className={cn("w-7 h-7", dragOver ? "text-accent" : "text-ink-muted")} />
        </div>
        <div>
          <p className="text-ink font-medium text-base">
            {dragOver ? "Drop to analyse" : "Drop your video here"}
          </p>
          <p className="text-ink-muted text-sm mt-1">or click to browse</p>
        </div>
        <p className="text-ink-dim text-xs font-mono">
          MP4 · MOV · WebM &nbsp;·&nbsp; ≤ 60 seconds &nbsp;·&nbsp; ≤ {MAX_MB} MB
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT.join(",")}
        className="hidden"
        onChange={onInputChange}
        disabled={disabled}
      />
      {error && (
        <p className="text-bad text-sm">{error}</p>
      )}
    </div>
  );
}
