const fs = require('node:fs');
const path = require('node:path');
const sharp = require('../../.tmp/slides-grab-runtime/node_modules/sharp');

const previewDir = path.resolve(__dirname, 'gate-preview');
const outputDir = path.resolve(__dirname, 'qa-contact-sheets');
const files = fs.readdirSync(previewDir).filter(name => /^slide-\d+\.png$/.test(name)).sort();

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  const width = 480;
  const height = 270;
  const columns = 3;
  const rows = 3;
  const perSheet = columns * rows;

  for (let offset = 0; offset < files.length; offset += perSheet) {
    const group = files.slice(offset, offset + perSheet);
    const layers = [];
    for (let index = 0; index < group.length; index += 1) {
      const input = await sharp(path.join(previewDir, group[index])).resize(width, height, { fit: 'fill' }).png().toBuffer();
      layers.push({ input, left: (index % columns) * width, top: Math.floor(index / columns) * height });
    }
    const sheetNo = Math.floor(offset / perSheet) + 1;
    await sharp({ create: { width: columns * width, height: rows * height, channels: 3, background: '#D7DEE9' } })
      .composite(layers)
      .png()
      .toFile(path.join(outputDir, `sheet-${sheetNo}.png`));
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
