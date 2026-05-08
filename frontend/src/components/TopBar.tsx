import { Link } from "react-router-dom";
import { KeyChip } from "./KeyChip";

export function TopBar() {
  return (
    <header className="border-b border-border-subtle bg-bg/80 backdrop-blur-sm sticky top-0 z-20">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-3">
        <Link to="/" className="flex items-center gap-3">
          <div className="relative w-6 h-6 flex-shrink-0">
            <div className="absolute inset-0 rounded-full border border-accent/60" />
            <div className="absolute inset-[5px] rounded-full bg-accent/90" />
          </div>
          <span className="font-semibold text-sm tracking-tight text-ink">Tribe Virality</span>
        </Link>
        <span className="ml-auto flex items-center gap-3">
          <KeyChip />
        </span>
      </div>
    </header>
  );
}
