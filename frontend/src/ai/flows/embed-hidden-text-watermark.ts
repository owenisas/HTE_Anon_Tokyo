/**
 * @fileOverview Client-side wrapper for embedding watermarks via API.
 *
 * This module calls the next.js API route to embed watermarks.
 * - Calls POST /api/watermark/embed to backend service
 * - Uses zero-width Unicode character encoding
 * - Includes CRC8 integrity checking
 *
 * Functions:
 * - embedHiddenTextWatermark - Embeds hidden watermark into text
 * - EmbedHiddenTextWatermarkInput - Input type
 * - EmbedHiddenTextWatermarkOutput - Return type
 */

export interface EmbedHiddenTextWatermarkInput {
  originalText: string;
}

export interface EmbedHiddenTextWatermarkOutput {
  watermarkedText: string;
}

/**
 * Embeds an invisible watermark into the provided text
 * @param input - Input object containing the original text
 * @returns Object with watermarked text
 * @throws Error if watermarking fails
 */
export async function embedHiddenTextWatermark(
  input: EmbedHiddenTextWatermarkInput
): Promise<EmbedHiddenTextWatermarkOutput> {
  try {
    // Call the backend API that uses the professional invisible-text-watermark library
    const response = await fetch('/api/watermark/embed', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text: input.originalText,
        issuer_id: 1,
        model_id: 42,
        key_id: 1,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Watermarking failed: ${error.error || 'Unknown error'}`);
    }

    const result = await response.json();
    
    return {
      watermarkedText: result.watermarkedText,
    };
  } catch (error) {
    throw new Error(
      `Failed to embed watermark: ${error instanceof Error ? error.message : 'Unknown error'}`
    );
  }
}
