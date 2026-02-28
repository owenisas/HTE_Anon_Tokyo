/**
 * API route for removing watermarks
 * Server-side route that calls the Python backend watermark service
 */

import { NextRequest, NextResponse } from "next/server";

const WATERMARK_API_URL =
  process.env.WATERMARK_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    if (!body.text || !body.text.trim()) {
      return NextResponse.json(
        { error: "Text is required" },
        { status: 400 }
      );
    }

    // Call Python backend watermark strip service
    const response = await fetch(`${WATERMARK_API_URL}/api/watermark/strip`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: body.text,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      console.error("Backend error:", error);
      return NextResponse.json(
        { error: "Failed to remove watermark" },
        { status: response.status }
      );
    }

    const data = await response.json();

    return NextResponse.json({
      cleanText: data.clean_text,
      success: data.success,
    });
  } catch (error) {
    console.error("Watermark strip error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
