'use server';
/**
 * @fileOverview A Genkit flow for embedding a hidden, imperceptible watermark into text.
 *
 * This flow now uses the professional invisible-text-watermark library via the backend API
 * instead of relying on LLM-based watermarking. This provides:
 * - Cryptographically secure watermarks
 * - Structured metadata embedding with CRC8 integrity checking
 * - Zero-width Unicode character encoding
 *
 * - embedHiddenTextWatermark - A function that embeds a hidden watermark into text.
 * - EmbedHiddenTextWatermarkInput - The input type for the embedHiddenTextWatermark function.
 * - EmbedHiddenTextWatermarkOutput - The return type for the embedHiddenTextWatermark function.
 */

import {z} from 'genkit';

const EmbedHiddenTextWatermarkInputSchema = z.object({
  originalText: z
    .string()
    .describe('The original text into which a hidden watermark will be embedded.'),
});
export type EmbedHiddenTextWatermarkInput = z.infer<
  typeof EmbedHiddenTextWatermarkInputSchema
>;

const EmbedHiddenTextWatermarkOutputSchema = z.object({
  watermarkedText: z
    .string()
    .describe('The text with an imperceptible, hidden watermark embedded.'),
});
export type EmbedHiddenTextWatermarkOutput = z.infer<
  typeof EmbedHiddenTextWatermarkOutputSchema
>;

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
