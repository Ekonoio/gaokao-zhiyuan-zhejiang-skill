import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const outputDir =
  `${process.cwd()}/outputs/input_review`;
const previewDir =
  `${outputDir}/previews/input-review`;
const inputs = [
  {
    label: "其他AI的80项",
    path: `${process.cwd()}/data/raw/other_ai_candidates.xlsx`,
  },
  {
    label: "已经筛选",
    path: `${process.cwd()}/data/raw/selected_candidates.xlsx`,
  },
];

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const results = [];
for (const input of inputs) {
  const workbook = await SpreadsheetFile.importXlsx(
    await FileBlob.load(input.path),
  );
  const sheets = await workbook.inspect({
    kind: "sheet",
    include: "id,name",
  });
  const sheet = workbook.worksheets.getItemAt(0);
  const table = await workbook.inspect({
    kind: "table",
    range: `${sheet.name}!A1:Z100`,
    include: "values,formulas",
    tableMaxRows: 100,
    tableMaxCols: 26,
  });
  const image = await workbook.render({
    sheetName: sheet.name,
    range: "A1:L25",
    scale: 1.2,
    format: "png",
  });
  await fs.writeFile(
    `${previewDir}/${input.label}.png`,
    new Uint8Array(await image.arrayBuffer()),
  );
  results.push({
    label: input.label,
    sheets: sheets.ndjson,
    table: table.ndjson,
  });
}

await fs.writeFile(
  `${outputDir}/workbook_inspection.json`,
  JSON.stringify(results, null, 2),
  "utf8",
);
console.log(JSON.stringify(results));
