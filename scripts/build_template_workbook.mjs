import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = process.cwd();
const outputDir = `${root}/outputs/final_template_2026_460`;
const templatePath = `${root}/outputs/template_work/志愿录入模版转换.xlsx`;
const dataPath = `${outputDir}/模板录入数据.json`;
const previewDir =
  `${outputDir}/previews/template-final`;

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const workbook = await SpreadsheetFile.importXlsx(
  await FileBlob.load(templatePath),
);
const sheet = workbook.worksheets.getItem("Sheet1");
const rows = JSON.parse(await fs.readFile(dataPath, "utf8"));
if (rows.length !== 80) {
  throw new Error(`模板必须写入80项，实际为${rows.length}项`);
}

const header = await workbook.inspect({
  kind: "table",
  range: "Sheet1!A1:D3",
  include: "values,formulas",
  tableMaxRows: 3,
  tableMaxCols: 4,
});
const expectedHeader = ["院校代码", "院校名称", "专业代码", "专业名称"];
const headerValues = JSON.parse(header.ndjson).values[0];
if (JSON.stringify(headerValues) !== JSON.stringify(expectedHeader)) {
  throw new Error(`模板表头不符合预期：${JSON.stringify(headerValues)}`);
}

const typedRows = rows.map(([schoolCode, schoolName, majorCode, majorName]) => [
  /^\d+$/.test(schoolCode) ? Number(schoolCode) : schoolCode,
  schoolName,
  /^\d+$/.test(majorCode) ? Number(majorCode) : majorCode,
  majorName,
]);
sheet.getRange("A2:D81").values = typedRows;
sheet.getRange("A2:A81").format.numberFormat = "0000";
sheet.getRange("C2:C81").format.numberFormat = "000";
sheet.getRange("D1:D82").format.columnWidth = 48;

const finalCheck = await workbook.inspect({
  kind: "table",
  range: "Sheet1!A1:D81",
  include: "values,formulas",
  tableMaxRows: 81,
  tableMaxCols: 4,
});
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "template formula error scan",
});

for (const [range, fileName] of [
  ["A1:D20", "模板前20行.png"],
  ["A63:D82", "模板后20行.png"],
]) {
  const image = await workbook.render({
    sheetName: "Sheet1",
    range,
    scale: 1.6,
    format: "png",
  });
  await fs.writeFile(
    `${previewDir}/${fileName}`,
    new Uint8Array(await image.arrayBuffer()),
  );
}

const outputPath = `${outputDir}/最终志愿录入表.xlsx`;
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

console.log(
  JSON.stringify({
    header: header.ndjson,
    final: finalCheck.ndjson,
    errors: errors.ndjson,
    output: outputPath,
    previewDir,
  }),
);
