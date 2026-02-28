'use server';
/**
 * @fileOverview A Genkit flow for detecting hidden text watermarks.
 *
 * This flow now uses the professional invisible-text-watermark library via the backend API
 * instead of relying on LLM-based detection. This provides:
 * - Deterministic detection using structural analysis
 * - CRC8 integrity checking of watermark payloads
 * - Extracted metadata (issuer_id, model_id, key_id, etc)
 *
 * - detectWatermark - A function that detects hidden watermarks in text.
 * - DetectWatermarkInput - The input type for the detectWatermark function.
 * - DetectWatermarkOutput - The return type for the detectWatermark function.
 */

import {z} from 'genkit';

const DetectWatermarkInputSchema = z.object({
  text: z.string().describe('The text to analyze for hidden watermarks.'),
});
export type DetectWatermarkInput = z.infer<typeof DetectWatermarkInputSchema>;

const DetectWatermarkOutputSchema = z.object({
  isWatermarked: z.boolean().describe('Whether a hidden watermark was detected.'),
  confidenceScore: z.number().min(0).max(100).describe('The confidence score (0-100).'),
  message: z.string().describe('A detailed message about the detection results.'),
});
export type DetectWatermarkOutput = z.infer<typeof DetectWatermarkOutputSchema>;

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
