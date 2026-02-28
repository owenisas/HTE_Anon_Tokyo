/**
 * @fileOverview Client-side wrapper for detecting watermarks via API.
 *
 * This module calls the next.js API route to detect watermarks.
 * - Calls POST /api/watermark/detect to backend service
 * - Returns confidence score and metadata extraction
 * - Uses zero-width Unicode character analysis
 * - Includes CRC8 integrity verification
 *
 * Functions:
 * - detectWatermark - Detects hidden watermarks in text
 * - DetectWatermarkInput - Input type
 * - DetectWatermarkOutput - Return type
 */

export interface DetectWatermarkInput {
  text: string;
}

export interface DetectWatermarkOutput {
  isWatermarked: boolean;
  confidenceScore: number;
  message: string;
}

/**
 * Detects if text contains an invisible watermark
 * @param input - Input object containing the text to analyze
 * @returns Object with detection result and confidence score
 * @throws Error if detection fails
 */
export async function detectWatermark(
  input: DetectWatermarkInput
): Promise<DetectWatermarkOutput> {
  try {
    // Call the backend API that uses the professional invisible-text-watermark library
    const response = await fetch('/api/watermark/detect', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text: input.text,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Detection failed: ${error.error || 'Unknown error'}`);
    }

    const result = await response.json();

    return {
      isWatermarked: result.isWatermarked,
      confidenceScore: result.confidenceScore,
      message: result.message,
    };
  } catch (error) {
    throw new Error(
      `Failed to detect watermark: ${error instanceof Error ? error.message : 'Unknown error'}`
    );
  }
}
