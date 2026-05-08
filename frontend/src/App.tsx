import { Route, Routes } from "react-router-dom";
import Landing from "./pages/Landing";
import Processing from "./pages/Processing";
import Results from "./pages/Results";
import { TopBar } from "./components/TopBar";
import { DisclaimerFooter } from "./components/DisclaimerFooter";

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <TopBar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/processing/:jobId" element={<Processing />} />
          <Route path="/results/:attemptId" element={<Results />} />
        </Routes>
      </main>
      <DisclaimerFooter />
    </div>
  );
}
