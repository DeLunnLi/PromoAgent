import sharp from 'sharp';

export function shouldComposeXhsCover(platform, env = process.env) {
  const normalized = String(platform ?? 'xhs').trim().toLowerCase();
  if (!['xhs', 'xiaohongshu', 'redbook'].includes(normalized)) {
    return false;
  }
  return (env.SOURCE2LAUNCH_IMAGE_XHS_COMPOSE ?? env.STAR_UP_IMAGE_XHS_COMPOSE) !== 'false';
}

export async function composeVerticalCoverFromSquare(squareBuffer, { width, height }) {
  const targetWidth = Number(width);
  const targetHeight = Number(height);
  if (!Number.isFinite(targetWidth) || !Number.isFinite(targetHeight) || targetWidth <= 0 || targetHeight <= 0) {
    throw new Error('composeVerticalCoverFromSquare requires positive width and height.');
  }

  const resizedSquare = await sharp(squareBuffer)
    .resize(targetWidth, targetWidth, { fit: 'fill' })
    .toBuffer();

  const topPad = Math.max(0, targetHeight - targetWidth);
  if (topPad === 0) {
    return resizedSquare;
  }

  const { data, info } = await sharp(resizedSquare)
    .raw()
    .toBuffer({ resolveWithObject: true });

  const topColor = sampleAverageColor(data, info.width, info.channels, 0);
  const midColor = sampleAverageColor(data, info.width, info.channels, Math.floor(info.height * 0.15));

  const gradientTop = await sharp({
    create: {
      width: targetWidth,
      height: topPad,
      channels: 3,
      background: topColor
    }
  })
    .png()
    .toBuffer();

  const gradientMid = await sharp({
    create: {
      width: targetWidth,
      height: Math.max(1, Math.floor(topPad * 0.35)),
      channels: 3,
      background: midColor
    }
  })
    .png()
    .toBuffer();

  return sharp({
    create: {
      width: targetWidth,
      height: targetHeight,
      channels: 3,
      background: topColor
    }
  })
    .composite([
      { input: gradientMid, top: Math.floor(topPad * 0.2), left: 0 },
      { input: resizedSquare, top: topPad, left: 0 }
    ])
    .png()
    .toBuffer();
}

function sampleAverageColor(raw, width, channels, row) {
  const y = Math.min(Math.max(row, 0), Math.max(0, Math.floor(raw.length / (width * channels)) - 1));
  let r = 0;
  let g = 0;
  let b = 0;
  let count = 0;

  for (let x = 0; x < width; x += Math.max(1, Math.floor(width / 24))) {
    const offset = (y * width + x) * channels;
    r += raw[offset] ?? 255;
    g += raw[offset + 1] ?? 255;
    b += raw[offset + 2] ?? 255;
    count += 1;
  }

  return {
    r: Math.round(r / count),
    g: Math.round(g / count),
    b: Math.round(b / count)
  };
}
