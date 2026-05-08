import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Disclaimer } from "../Disclaimer";
import { DISCLAIMER_VERSION, hasAckedDisclaimer } from "../../lib/disclaimerAck";

describe("Disclaimer", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders required headings", () => {
    render(<Disclaimer onAck={() => {}} />);
    expect(screen.getByText(/About this tool/i)).toBeInTheDocument();
    expect(screen.getByText(/About TRIBE v2/i)).toBeInTheDocument();
    expect(screen.getByText(/Accuracy & limitations/i)).toBeInTheDocument();
    expect(screen.getByText(/Liability/i)).toBeInTheDocument();
  });

  it("Continue button is disabled until checkbox is ticked", async () => {
    const user = userEvent.setup();
    render(<Disclaimer onAck={() => {}} />);
    const button = screen.getByRole("button", { name: /continue/i });
    expect(button).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    expect(button).toBeEnabled();
  });

  it("clicking Continue writes ack flag and calls onAck", async () => {
    const onAck = vi.fn();
    const user = userEvent.setup();
    render(<Disclaimer onAck={onAck} />);
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(onAck).toHaveBeenCalledOnce();
    expect(hasAckedDisclaimer()).toBe(true);
    const stored = JSON.parse(localStorage.getItem("tribe_virality.disclaimer_ack")!);
    expect(stored.version).toBe(DISCLAIMER_VERSION);
    expect(typeof stored.ackedAt).toBe("string");
  });

  it("readOnly mode hides the checkbox and Continue button", () => {
    render(<Disclaimer readOnly onAck={() => {}} />);
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByRole("button", { name: /continue/i })).toBeNull();
  });
});
