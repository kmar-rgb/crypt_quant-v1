import type { ScreenerRow } from "@/types/crypto";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function getScreenerRows(): Promise<ScreenerRow[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/screener`, {
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Screener request failed with ${response.status}`);
  }
  return response.json();
}
