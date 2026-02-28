/**
 * API route for embedding watermarks
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

    // Call Python backend watermark service
    const backendUrl = `${WATERMARK_API_URL}/api/watermark/embed`;
    console.log("Calling backend URL:", backendUrl);
    
    const response = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: body.text,
        issuer_id: body.issuer_id || 1,
        model_id: body.model_id || 42,
        key_id: body.key_id || 1,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      console.error("Backend error:", error);
      return NextResponse.json(
        { error: "Failed to embed watermark" },
        { status: response.status }
      );
    }

    const data = await response.json();

    return NextResponse.json({
      watermarkedText: data.watermarked_text,
      success: data.success,
    });
  } catch (error) {
    console.error("Watermark embed error:", error);
    return NextResponse.json(
      { error: "Internal server error", details: String(error) },
      { status: 500 }
    );
  }
}
