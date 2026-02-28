/**
 * API route for detecting watermarks
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

    // Call Python backend watermark detection service
    const backendUrl = `${WATERMARK_API_URL}/api/watermark/detect`;
    console.log("Calling backend URL:", backendUrl);
    
    const response = await fetch(backendUrl, {
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
        { error: "Failed to detect watermark" },
        { status: response.status }
      );
    }

    const data = await response.json();

    return NextResponse.json({
      isWatermarked: data.is_watermarked,
      confidenceScore: data.confidence_score,
      message: data.message,
      payloads: data.payloads,
    });
  } catch (error) {
    console.error("Watermark detection error:", error);
    return NextResponse.json(
      { error: "Internal server error", details: String(error) },
      { status: 500 }
    );
  }
}
