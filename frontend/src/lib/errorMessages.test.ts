import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { messageForError } from "@/lib/errorMessages";

describe("messageForError", () => {
  it("uses an error-code override before the status override", () => {
    const error = new ApiError(409, "finalized", "DISTRIBUTION_FINALIZED");

    expect(
      messageForError(error, {
        codes: { DISTRIBUTION_FINALIZED: "確定済みです" },
        409: "競合しました",
      }),
    ).toBe("確定済みです");
  });

  it("uses a status override before the shared status message", () => {
    const error = new ApiError(401, "expired", "AUTH_INVALID_TOKEN");

    expect(messageForError(error, { 401: "ログインし直してください" })).toBe(
      "ログインし直してください",
    );
  });

  it("uses the shared status message when there is no override", () => {
    expect(messageForError(new ApiError(401, "expired"))).toBe(
      "セッションの有効期限が切れました。再度ログインしてください。",
    );
  });

  it("uses the caller fallback for an unknown API status", () => {
    expect(
      messageForError(new ApiError(418, "teapot"), {
        fallback: "読み込めませんでした",
      }),
    ).toBe("読み込めませんでした");
  });

  it("uses the network message for fetch failures", () => {
    expect(messageForError(new TypeError("Failed to fetch"))).toBe(
      "ネットワークに接続できませんでした。接続を確認してから再度お試しください。",
    );
  });

  it("uses the generic message when no fallback is provided", () => {
    expect(messageForError("boom")).toBe(
      "問題が発生しました。時間をおいて再度お試しください。",
    );
  });
});
