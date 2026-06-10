import { copyFile, mkdir, readdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC_DIR = join(__dirname, "..", "node_modules", "flag-icons", "flags", "4x3");
const OUT_DIR = join(__dirname, "..", "site", "assets", "flags");

// Map FIFA 3-letter code → ISO 3166-1 alpha-2 code (flag-icons uses ISO codes).
const CODE_MAP = {
  USA: "us", POR: "pt", MEX: "mx", CAN: "ca",
  RSA: "za", CZE: "cz", MAR: "ma", HAI: "ht", UZB: "uz", COD: "cd",
  ARG: "ar", BRA: "br", FRA: "fr", ESP: "es", ENG: "gb-eng",
  GER: "de", NED: "nl", ITA: "it", BEL: "be", CRO: "hr",
  JPN: "jp", KOR: "kr", AUS: "au", SEN: "sn", CMR: "cm",
  EGY: "eg", NGA: "ng", COL: "co", URU: "uy", ECU: "ec",
  PER: "pe", CRC: "cr", NOR: "no", SWE: "se", DEN: "dk",
  SUI: "ch", QAT: "qa", BIH: "ba", CIV: "ci", NZL: "nz",
  KSA: "sa", CPV: "cv", IRQ: "iq", JOR: "jo", AUT: "at",
  ALG: "dz", GHA: "gh", PAN: "pa", IRN: "ir", TUN: "tn",
  TUR: "tr", PAR: "py", SCO: "gb-sct", CUW: "cw",
};

await mkdir(OUT_DIR, { recursive: true });
const available = new Set(await readdir(SRC_DIR));

let copied = 0;
const missing = [];
for (const [fifaCode, isoCode] of Object.entries(CODE_MAP)) {
  const filename = `${isoCode}.svg`;
  if (available.has(filename)) {
    await copyFile(join(SRC_DIR, filename), join(OUT_DIR, `${fifaCode}.svg`));
    copied += 1;
  } else {
    missing.push(`${fifaCode} (sought ${filename})`);
  }
}

console.log(`copied ${copied} flag SVGs to ${OUT_DIR}`);
if (missing.length) {
  console.warn(`missing: ${missing.join(", ")}`);
}
