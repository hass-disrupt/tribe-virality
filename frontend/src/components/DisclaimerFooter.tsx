import { useState } from "react";
import { Disclaimer } from "./Disclaimer";

export function DisclaimerFooter() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <footer className="border-t border-border-subtle mt-auto py-5 px-6">
        <p className="max-w-6xl mx-auto text-xs text-ink-dim leading-relaxed text-center">
          Research-grade approximation · CC-BY-NC-4.0 · Non-commercial · No
          guarantee of real-world performance ·{" "}
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="underline underline-offset-2 hover:text-ink"
          >
            Read full disclaimer
          </button>
        </p>
      </footer>
      {open && (
        <div
          className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 overflow-auto"
          onClick={() => setOpen(false)}
        >
          <div onClick={(e) => e.stopPropagation()}>
            <Disclaimer readOnly onAck={() => setOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}
