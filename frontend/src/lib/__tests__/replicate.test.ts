import { describe, it, expect, vi, beforeEach } from "vitest";
import { replicateFetch, validateToken, ReplicateAuthError, ReplicateNetworkError } from "../replicate";

describe("replicateFetch", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("sends Authorization header to the proxy path", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }),
    );
    await replicateFetch({ apiKey: "r8_test" }, "/v1/account");
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toBe("/replicate-api/v1/account");
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer r8_test");
  });

  it("throws ReplicateAuthError on 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("unauthorized", { status: 401 }),
    );
    await expect(replicateFetch({ apiKey: "bad" }, "/v1/account")).rejects.toBeInstanceOf(ReplicateAuthError);
  });

  it("throws ReplicateNetworkError on 5xx", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("err", { status: 502 }));
    await expect(replicateFetch({ apiKey: "x" }, "/v1/account")).rejects.toBeInstanceOf(ReplicateNetworkError);
  });

  it("scrubs Authorization from thrown error message", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new Error("connect failed Authorization: Bearer r8_secret"),
    );
    try {
      await replicateFetch({ apiKey: "r8_secret" }, "/v1/account");
      throw new Error("should have thrown");
    } catch (e) {
      expect(String((e as Error).message)).not.toContain("r8_secret");
      expect(String((e as Error).message)).not.toContain("Bearer");
    }
  });
});

describe("validateToken", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("returns account info on 200", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ username: "u", type: "user" }), {
        status: 200, headers: { "content-type": "application/json" },
      }),
    );
    const acct = await validateToken("r8_x");
    expect(acct).toEqual({ username: "u", type: "user" });
  });

  it("rejects with ReplicateAuthError on 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("nope", { status: 401 }));
    await expect(validateToken("bad")).rejects.toBeInstanceOf(ReplicateAuthError);
  });
});
