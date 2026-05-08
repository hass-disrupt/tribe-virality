import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// jsdom doesn't implement these by default.
if (!URL.createObjectURL) URL.createObjectURL = vi.fn(() => "blob:mock");
if (!URL.revokeObjectURL) URL.revokeObjectURL = vi.fn();

afterEach(() => {
  cleanup();
});
