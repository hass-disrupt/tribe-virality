import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { ApiKeyGate } from "../ApiKeyGate";
import { AppStateProvider, useAppState } from "../../state/AppState";

const wrap = ({ children }: { children: ReactNode }) => (
  <AppStateProvider>{children}</AppStateProvider>
);

function StateProbe() {
  const { state } = useAppState();
  return <div data-testid="probe">{state.apiKey ?? "none"}</div>;
}

describe("ApiKeyGate", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("Continue is disabled until token field is non-empty", async () => {
    const user = userEvent.setup();
    render(
      <>
        <ApiKeyGate />
        <StateProbe />
      </>,
      { wrapper: wrap },
    );
    const button = screen.getByRole("button", { name: /continue/i });
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText(/replicate api token/i), "r8_x");
    expect(button).toBeEnabled();
  });

  it("on 200 stores key and account", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ username: "alice", type: "user" }), {
        status: 200, headers: { "content-type": "application/json" },
      }),
    );
    const user = userEvent.setup();
    render(
      <>
        <ApiKeyGate />
        <StateProbe />
      </>,
      { wrapper: wrap },
    );
    await user.type(screen.getByLabelText(/replicate api token/i), "r8_good");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(screen.getByTestId("probe").textContent).toBe("r8_good"));
  });

  it("on 401 shows inline error and does NOT store key", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("nope", { status: 401 }));
    const user = userEvent.setup();
    render(
      <>
        <ApiKeyGate />
        <StateProbe />
      </>,
      { wrapper: wrap },
    );
    await user.type(screen.getByLabelText(/replicate api token/i), "r8_bad");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(screen.getByText(/didn'?t work/i)).toBeInTheDocument());
    expect(screen.getByTestId("probe").textContent).toBe("none");
  });

  it("on network error shows generic error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    const user = userEvent.setup();
    render(<ApiKeyGate />, { wrapper: wrap });
    await user.type(screen.getByLabelText(/replicate api token/i), "r8_x");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(screen.getByText(/couldn'?t reach replicate/i)).toBeInTheDocument());
  });
});
