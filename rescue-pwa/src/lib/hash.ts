/**
 * hash.ts — Browser-side cryptographic and perceptual hashing.
 *
 * Privacy contract:
 *  - computeSha256: reads the file locally; bytes never leave the device.
 *  - computeDHash:  reads the file locally via an offscreen Canvas; bytes never
 *                   leave the device. Only the resulting 64-bit hex string may
 *                   be sent to the origin-lookup endpoint after explicit user
 *                   confirmation.
 *
 * NOTE: dHash is a PLACEHOLDER format until Member 3 confirms the exact
 * perceptual-hash algorithm/format accepted by GET /v1/ledger/lookup?phash=.
 * Update the algorithm here when that contract is finalised.
 */

/**
 * Compute the SHA-256 digest of a File/Blob entirely in the browser.
 * Returns a lowercase hex string.
 * The file bytes are never sent anywhere by this function.
 */
export async function computeSha256(file: File | Blob): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  return bufferToHex(hashBuffer);
}

/**
 * Compute a 64-bit difference hash (dHash) of an image file.
 *
 * Algorithm:
 *  1. Draw the image onto a 9×8 offscreen canvas.
 *  2. Convert to greyscale.
 *  3. For each row, compare adjacent pixels (8 comparisons × 8 rows = 64 bits).
 *  4. Return the 64-bit value as a 16-char lowercase hex string.
 *
 * This is a PLACEHOLDER until Member 3 confirms the exact hash format.
 * If the Canvas API is unavailable (e.g., in a Worker without OffscreenCanvas),
 * this function returns null instead of silently uploading the file.
 */
export async function computeDHash(file: File | Blob): Promise<string | null> {
  // Guard: Canvas API must be available.
  if (typeof document === 'undefined' && typeof OffscreenCanvas === 'undefined') {
    return null;
  }

  return new Promise((resolve, reject) => {
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);

    img.onload = () => {
      try {
        const WIDTH = 9;
        const HEIGHT = 8;

        let canvas: HTMLCanvasElement | OffscreenCanvas;
        let ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D;

        if (typeof OffscreenCanvas !== 'undefined') {
          canvas = new OffscreenCanvas(WIDTH, HEIGHT);
          ctx = canvas.getContext('2d') as OffscreenCanvasRenderingContext2D;
        } else {
          canvas = document.createElement('canvas');
          (canvas as HTMLCanvasElement).width = WIDTH;
          (canvas as HTMLCanvasElement).height = HEIGHT;
          ctx = (canvas as HTMLCanvasElement).getContext('2d') as CanvasRenderingContext2D;
        }

        if (!ctx) {
          URL.revokeObjectURL(objectUrl);
          resolve(null);
          return;
        }

        ctx.drawImage(img, 0, 0, WIDTH, HEIGHT);
        const imageData = ctx.getImageData(0, 0, WIDTH, HEIGHT);
        const data = imageData.data;

        // Convert to greyscale: 0.299R + 0.587G + 0.114B
        const grey: number[] = [];
        for (let i = 0; i < data.length; i += 4) {
          grey.push(
            Math.round(0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2])
          );
        }

        // Compute difference hash: 64 bits
        let hashBits = BigInt(0);
        for (let row = 0; row < HEIGHT; row++) {
          for (let col = 0; col < HEIGHT; col++) {
            const left = grey[row * WIDTH + col];
            const right = grey[row * WIDTH + col + 1];
            hashBits = (hashBits << BigInt(1)) | BigInt(left > right ? 1 : 0);
          }
        }

        URL.revokeObjectURL(objectUrl);
        resolve(hashBits.toString(16).padStart(16, '0'));
      } catch (err) {
        URL.revokeObjectURL(objectUrl);
        reject(err);
      }
    };

    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error('Failed to load image for perceptual hashing.'));
    };

    img.src = objectUrl;
  });
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function bufferToHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}
