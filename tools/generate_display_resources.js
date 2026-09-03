const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..", "..");
const gfxFonts = path.join(root, "libraries", "Adafruit-GFX-Library-1.11.10", "Fonts");
const fontNames = ["FreeSans9pt7b", "FreeMono9pt7b", "FreeMonoBold9pt7b", "Org_01"];

function values(block) {
  const source = block.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  return Array.from(source.matchAll(/0[xX]([0-9a-fA-F]{2})/g), match =>
    parseInt(match[1], 16));
}

function wrappedHex(bytes, indent = "    ") {
  const hex = Buffer.from(bytes).toString("hex");
  const lines = [];
  for (let offset = 0; offset < hex.length; offset += 96) {
    lines.push(`${indent}b"${hex.slice(offset, offset + 96)}"`);
  }
  return lines.join("\n");
}

function parseFont(name) {
  const source = fs.readFileSync(path.join(gfxFonts, `${name}.h`), "utf8");
  const bitmapMatch = source.match(new RegExp(`${name}Bitmaps\\[\\][\\s\\S]*?= \\{([\\s\\S]*?)\\};`));
  const glyphMatch = source.match(new RegExp(`${name}Glyphs\\[\\][\\s\\S]*?= \\{([\\s\\S]*?)\\};`));
  const fontMatch = source.match(new RegExp(`${name}[^=]*= \\{[\\s\\S]*?0x([0-9A-Fa-f]+),\\s*0x([0-9A-Fa-f]+),\\s*(\\d+)\\s*\\};`));
  if (!bitmapMatch || !glyphMatch || !fontMatch) {
    throw new Error(`Unable to parse ${name}`);
  }

  const bitmap = values(bitmapMatch[1]);
  const glyphs = [];
  for (const match of glyphMatch[1].matchAll(/\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\}/g)) {
    const offset = Number(match[1]);
    glyphs.push(offset & 0xff, offset >> 8, Number(match[2]), Number(match[3]),
      Number(match[4]), Number(match[5]) & 0xff, Number(match[6]) & 0xff);
  }
  return {
    bitmap,
    glyphs,
    first: parseInt(fontMatch[1], 16),
    last: parseInt(fontMatch[2], 16),
    yAdvance: Number(fontMatch[3]),
  };
}

const output = [
  '"""Exact Adafruit GFX fonts and T-Echo-Lite monochrome background."""',
  "",
  "from binascii import unhexlify",
  "",
];

for (const name of fontNames) {
  const font = parseFont(name);
  output.push(`${name.toUpperCase()} = (`, "    unhexlify(", wrappedHex(font.bitmap, "        "), "    ),",
    "    unhexlify(", wrappedHex(font.glyphs, "        "), "    ),",
    `    ${font.first}, ${font.last}, ${font.yAdvance},`, ")", "");
}

const imagePath = path.join(root, "examples", "T-Echo-Lite", "Sleep_Wake_Up",
  "material_monochrome_176x192px.h");
const imageSource = fs.readFileSync(imagePath, "utf8");
const imageMatch = imageSource.match(/gImage_1\[4224\][^=]*=\s*\{([\s\S]*?)\};/);
if (!imageMatch) {
  throw new Error("Unable to parse gImage_1");
}
const image = values(imageMatch[1]);
if (image.length !== 4224) {
  throw new Error(`Expected 4224 image bytes, got ${image.length}`);
}
output.push("MATERIAL_MONOCHROME_192X176 = unhexlify(", wrappedHex(image), ")", "");

const target = path.join(__dirname, "..", "lib", "gfx_resources.py");
fs.writeFileSync(target, output.join("\n"), "ascii");
console.log(`Generated ${target}`);
