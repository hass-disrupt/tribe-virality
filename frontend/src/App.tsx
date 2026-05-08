import { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AppStateProvider, useAppState } from "./state/AppState";
import { Disclaimer } from "./components/Disclaimer";
import { ApiKeyGate } from "./components/ApiKeyGate";
import { TopBar } from "./components/TopBar";
import { DisclaimerFooter } from "./components/DisclaimerFooter";
import Landing from "./pages/Landing";
import Processing from "./pages/Processing";
import Results from "./pages/Results";
import { hasAckedDisclaimer } from "./lib/disclaimerAck";

function Gates({ children }: { children: React.ReactNode }) {
  const { state } = useAppState();
  const [acked, setAcked] = useState<boolean>(() => hasAckedDisclaimer());

  if (!acked) return <Disclaimer onAck={() => setAcked(true)} />;
  if (!state.apiKey) return <ApiKeyGate />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AppStateProvider>
      <Gates>
        <div className="min-h-screen flex flex-col">
          <TopBar />
          <main className="flex-1">
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/processing/:predictionId" element={<Processing />} />
              <Route path="/results/:attemptId" element={<Results />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <DisclaimerFooter />
        </div>
      </Gates>
    </AppStateProvider>
  );
}
