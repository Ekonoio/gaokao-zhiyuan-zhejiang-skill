import fs from "node:fs/promises";
import {
  FileBlob,
  SpreadsheetFile,
  Workbook,
} from "@oai/artifact-tool";

const root = process.cwd();
const outputDir =
  process.env.OUTPUT_DIR ??
  `${root}/outputs/final_plan`;
const previewDir =
  process.env.PREVIEW_DIR ??
  `${outputDir}/previews/final-delivery`;
const templatePath = `${root}/outputs/template_work/志愿录入模版转换.xlsx`;

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const allRows = JSON.parse(
  await fs.readFile(`${outputDir}/最终志愿数据.json`, "utf8"),
);
const additionRows = JSON.parse(
  await fs.readFile(`${outputDir}/新增与替换项目.json`, "utf8"),
);
const replacedRows = JSON.parse(
  await fs.readFile(`${outputDir}/被替换项目.json`, "utf8"),
);
const otherAiRows = JSON.parse(
  await fs.readFile(
    `${root}/outputs/other_ai_review/其他AI志愿筛查.json`,
    "utf8",
  ),
);

if (allRows.length !== 80) {
  throw new Error(`最终志愿必须为80项，实际为${allRows.length}项`);
}

const directRows = allRows.filter((row) => row["填报状态"] === "可直接填");
const manualRows = allRows.filter(
  (row) => row["填报状态"] === "必须人工确认",
);
const undergraduateRows = allRows.filter((row) =>
  ["本科", "职业本科"].includes(row["学历层次"]),
);

const priorityHeaders = [
  "志愿序号",
  "层级",
  "填报状态",
  "院校代码",
  "院校名称",
  "专业代码",
  "专业名称",
  "学历层次",
  "城市",
  "学费",
  "2026招生计划数",
  "2025位次差",
  "2024位次差",
  "2023位次差",
  "名单来源",
  "人工确认原因",
  "入选依据",
];
const finalHeaders = [
  ...priorityHeaders,
  ...Object.keys(allRows[0]).filter(
    (header) => !priorityHeaders.includes(header),
  ),
];
const otherAiHeaders = Object.keys(otherAiRows[0]);
const replacedHeaders = Object.keys(replacedRows[0]);
const numericHeaders = new Set([
  "志愿序号",
  "学制",
  "学费",
  "2026招生计划数",
  "2025最低分",
  "2025最低位次",
  "2024最低分",
  "2024最低位次",
  "2023最低分",
  "2023最低位次",
  "用户位次",
  "2025位次差",
  "2024位次差",
  "2023位次差",
  "原序号",
  "2026计划数",
  "历史年份数",
]);

function columnName(index) {
  let value = index;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function typedValue(row, header) {
  const value = row[header] ?? "";
  if (["院校代码", "专业代码", "2026院校代码", "2026专业代码"].includes(header)) {
    return /^\d+$/.test(String(value)) ? Number(value) : value;
  }
  if (numericHeaders.has(header) && value !== "") {
    const number = Number(value);
    return Number.isFinite(number) ? number : value;
  }
  return value;
}

function widthForHeader(header) {
  if (["志愿序号", "层级", "学历层次", "公民办"].includes(header)) return 9;
  if (["填报状态", "名单来源", "其他AI梯度", "审查结论"].includes(header)) {
    return 16;
  }
  if (["院校代码", "专业代码", "2026院校代码", "2026专业代码"].includes(header)) {
    return 11;
  }
  if (["院校名称", "院校"].includes(header)) return 28;
  if (["专业名称", "专业"].includes(header)) return 34;
  if (["人工确认原因", "入选依据", "不能用或调整原因", "替换原因"].includes(header)) {
    return 48;
  }
  if (["排序理由", "风险提示", "人工复核项", "数据来源"].includes(header)) {
    return 38;
  }
  if (["城市", "填报段次", "选科是否符合", "是否民办", "是否中外合作"].includes(header)) {
    return 12;
  }
  if (header.includes("位次") || header.includes("最低分")) return 14;
  if (header.includes("计划") || header === "学费" || header === "学制") return 13;
  return 18;
}

function addTableSheet(
  workbook,
  sheetName,
  tableName,
  rows,
  headers,
  options = {},
) {
  const sheet = workbook.worksheets.add(sheetName);
  const matrix = [
    headers,
    ...rows.map((row) => headers.map((header) => typedValue(row, header))),
  ];
  const rowCount = matrix.length;
  const lastColumn = columnName(headers.length);
  const fullRange = sheet.getRange(`A1:${lastColumn}${rowCount}`);
  fullRange.values = matrix;
  sheet.showGridLines = false;
  fullRange.format.font.name = "Microsoft YaHei";
  fullRange.format.font.size = 10;
  fullRange.format.verticalAlignment = "center";
  fullRange.format.wrapText = true;
  fullRange.format.rowHeight = options.rowHeight ?? 30;
  sheet.getRange(`A1:${lastColumn}1`).format = {
    fill: "#20323A",
    font: { bold: true, color: "#FFFFFF", size: 10 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange(`A1:${lastColumn}1`).format.rowHeight = 40;
  fullRange.format.borders = {
    insideHorizontal: { style: "thin", color: "#E3E8EA" },
    bottom: { style: "thin", color: "#AAB7BC" },
  };

  headers.forEach((header, index) => {
    const column = columnName(index + 1);
    sheet.getRange(`${column}1:${column}${rowCount}`).format.columnWidth =
      widthForHeader(header);
    if (numericHeaders.has(header)) {
      sheet.getRange(`${column}2:${column}${rowCount}`).format.numberFormat =
        "#,##0";
    }
    if (["院校代码", "2026院校代码"].includes(header)) {
      sheet.getRange(`${column}2:${column}${rowCount}`).format.numberFormat =
        "0000";
    }
    if (["专业代码", "2026专业代码"].includes(header)) {
      sheet.getRange(`${column}2:${column}${rowCount}`).format.numberFormat =
        "000";
    }
  });

  const statusColumn = headers.indexOf("填报状态") + 1;
  if (statusColumn > 0 && rowCount > 1) {
    const column = columnName(statusColumn);
    const range = sheet.getRange(`${column}2:${column}${rowCount}`);
    range.conditionalFormats.add("containsText", {
      text: "必须人工确认",
      format: {
        fill: "#FCE3E1",
        font: { bold: true, color: "#9B1C1C" },
      },
    });
    range.conditionalFormats.add("containsText", {
      text: "可直接填",
      format: {
        fill: "#DDF1E4",
        font: { bold: true, color: "#17613A" },
      },
    });
  }

  const tierColumn = headers.indexOf("层级") + 1;
  if (tierColumn > 0 && rowCount > 1) {
    const column = columnName(tierColumn);
    const range = sheet.getRange(`${column}2:${column}${rowCount}`);
    for (const [text, fill, color] of [
      ["冲", "#FCE8D5", "#9A4B00"],
      ["稳", "#E2ECF7", "#24547D"],
      ["保", "#DDF1E4", "#17613A"],
    ]) {
      range.conditionalFormats.add("containsText", {
        text,
        format: { fill, font: { bold: true, color } },
      });
    }
  }

  const reviewColumn = headers.indexOf("审查结论") + 1;
  if (reviewColumn > 0 && rowCount > 1) {
    const column = columnName(reviewColumn);
    const range = sheet.getRange(`${column}2:${column}${rowCount}`);
    for (const [text, fill, color] of [
      ["不可用", "#FCE3E1", "#9B1C1C"],
      ["有条件可用", "#FFF1CC", "#805B00"],
      ["可用", "#DDF1E4", "#17613A"],
    ]) {
      range.conditionalFormats.add("containsText", {
        text,
        format: { fill, font: { bold: true, color } },
      });
    }
  }

  const table = sheet.tables.add(
    `A1:${lastColumn}${rowCount}`,
    true,
    tableName,
  );
  table.style = "TableStyleMedium2";
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(options.freezeColumns ?? 3);
  return { sheet, rowCount, lastColumn };
}

const workbook = Workbook.create();
const summary = workbook.worksheets.add("填报说明");
const finalSheet = addTableSheet(
  workbook,
  "最终80志愿",
  "Final80Table",
  allRows,
  finalHeaders,
  { freezeColumns: 3 },
);
const additionsSheet = addTableSheet(
  workbook,
  "新增22项",
  "AdditionsTable",
  additionRows,
  finalHeaders,
  { freezeColumns: 3 },
);
const replacedSheet = addTableSheet(
  workbook,
  "替换4项",
  "ReplacedTable",
  replacedRows,
  replacedHeaders,
  { freezeColumns: 2 },
);
const otherAiSheet = addTableSheet(
  workbook,
  "其他AI筛查",
  "OtherAiReviewTable",
  otherAiRows,
  otherAiHeaders,
  { freezeColumns: 5 },
);
const directSheetName = `可直接填${directRows.length}`;
const directSheet = addTableSheet(
  workbook,
  directSheetName,
  "DirectTable",
  directRows,
  finalHeaders,
  { freezeColumns: 3 },
);
const manualSheetName = `必须确认${manualRows.length}`;
const manualSheet = addTableSheet(
  workbook,
  manualSheetName,
  "ManualTable",
  manualRows,
  finalHeaders,
  { freezeColumns: 3 },
);
const undergraduateSheetName = `本科${undergraduateRows.length}项`;
const undergraduateSheet = addTableSheet(
  workbook,
  undergraduateSheetName,
  "UndergraduateTable",
  undergraduateRows,
  finalHeaders,
  { freezeColumns: 3 },
);

summary.showGridLines = false;
summary.mergeCells("A1:H1");
summary.getRange("A1").values = [["2026浙江普通类二段最终志愿方案"]];
summary.getRange("A1:H1").format = {
  fill: "#20323A",
  font: { bold: true, color: "#FFFFFF", size: 18, name: "Microsoft YaHei" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
summary.getRange("A1:H1").format.rowHeight = 40;

summary.getRange("A3:A11").values = [
  ["最终志愿数"],
  ["冲"],
  ["稳"],
  ["保"],
  ["本科"],
  ["可直接填"],
  ["必须人工确认"],
  ["保档需确认专业"],
  ["保档最高学费"],
];
summary.getRange("B3:B11").formulas = [
  ["=COUNTA('最终80志愿'!$A$2:$A$81)"],
  ['=COUNTIF(\'最终80志愿\'!$B$2:$B$81,"冲")'],
  ['=COUNTIF(\'最终80志愿\'!$B$2:$B$81,"稳")'],
  ['=COUNTIF(\'最终80志愿\'!$B$2:$B$81,"保")'],
  [
    '=COUNTIF(\'最终80志愿\'!$H$2:$H$81,"本科")+COUNTIF(\'最终80志愿\'!$H$2:$H$81,"职业本科")',
  ],
  ['=COUNTIF(\'最终80志愿\'!$C$2:$C$81,"可直接填")'],
  ['=COUNTIF(\'最终80志愿\'!$C$2:$C$81,"必须人工确认")'],
  [
    '=COUNTIFS(\'最终80志愿\'!$B$2:$B$81,"保",\'最终80志愿\'!$C$2:$C$81,"必须人工确认")',
  ],
  ['=MAXIFS(\'最终80志愿\'!$J$2:$J$81,\'最终80志愿\'!$B$2:$B$81,"保")'],
];
summary.getRange("D3:D11").values = [
  ["考生"],
  ["分数 / 位次"],
  ["选科"],
  ["填报段次"],
  ["地域限制"],
  ["新增项目"],
  ["其他AI直接可用"],
  ["其他AI条件可用"],
  ["其他AI不可用"],
];
summary.getRange("E3:E8").values = [
  ["浙江2026考生，男"],
  ["460 / 220000"],
  ["思想政治、历史、地理"],
  ["普通类二段"],
  ["不去东北；江西仅南昌"],
  ["22项均公办专科、学费低于1万元"],
];
summary.getRange("E9:E11").formulas = [
  [
    '=COUNTIF(\'其他AI筛查\'!$E$2:$E$80,"可用")+COUNTIF(\'其他AI筛查\'!$E$2:$E$80,"可用（已保留）")',
  ],
  ['=COUNTIF(\'其他AI筛查\'!$E$2:$E$80,"有条件可用")'],
  ['=COUNTIF(\'其他AI筛查\'!$E$2:$E$80,"不可用")'],
];
summary.getRange("A3:A11").format = {
  fill: "#DCE8EA",
  font: { bold: true, color: "#20323A" },
};
summary.getRange("B3:B11").format = {
  fill: "#F6F8F8",
  font: { bold: true, color: "#111827", size: 14 },
  numberFormat: "#,##0",
};
summary.getRange("D3:D11").format = {
  fill: "#E8E4D8",
  font: { bold: true, color: "#3D3526" },
};
summary.getRange("E3:E11").format = {
  fill: "#FBFAF6",
  wrapText: true,
};
summary.getRange("A3:B11").format.borders = {
  preset: "all",
  style: "thin",
  color: "#B8C5C9",
};
summary.getRange("D3:E11").format.borders = {
  preset: "all",
  style: "thin",
  color: "#CCC4B3",
};

summary.mergeCells("A13:H13");
summary.getRange("A13").values = [["填报与安全底线"]];
summary.getRange("A13:H13").format = {
  fill: "#3E5F68",
  font: { bold: true, color: "#FFFFFF" },
};
const notes = [
  "1. 严格按“最终80志愿”的序号1至80录入，不自行把稳、保项目移到冲档前面。",
  "2. 冲25、稳40、保15偏激进；15个保档必须全部愿意就读并完整填报，不能空缺。",
  "3. 保档中6个是相邻专业，历史和硬条件合格，但必须先确认专业愿意度，否则不能视为真实保底。",
  "4. 原表中1个1.6万元稳档和3个1.38万元保档已替换；最终稳保均低于1万元/年。",
  "5. 两个本科均为民办且历史位次差大，只作低概率冲刺；确认1.5万元学费和真实就读意愿。",
  "6. 听力情况待确认未作硬排除；提交前仍须逐校核对2026招生章程、体检及听力条款。",
  "7. 填报当天在浙江官方系统再次核对院校代码、专业代码、剩余计划、学费和校区。",
];
notes.forEach((note, index) => {
  const row = 14 + index;
  summary.mergeCells(`A${row}:H${row}`);
  summary.getRange(`A${row}`).values = [[note]];
  summary.getRange(`A${row}:H${row}`).format = {
    fill: index % 2 === 0 ? "#F6F8F8" : "#FFFFFF",
    wrapText: true,
    font: { color: "#263238" },
  };
  summary.getRange(`A${row}:H${row}`).format.rowHeight = 30;
});
summary.getRange("A1:H20").format.font.name = "Microsoft YaHei";
summary.getRange("A1:H20").format.verticalAlignment = "center";
summary.getRange("A1:A20").format.columnWidth = 19;
summary.getRange("B1:B20").format.columnWidth = 14;
summary.getRange("C1:C20").format.columnWidth = 3;
summary.getRange("D1:D20").format.columnWidth = 19;
summary.getRange("E1:H20").format.columnWidth = 24;
summary.freezePanes.freezeRows(1);

const summaryCheck = await workbook.inspect({
  kind: "table",
  range: "填报说明!A1:H20",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 8,
});
const finalCheck = await workbook.inspect({
  kind: "table",
  range: "最终80志愿!A1:Q12",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 17,
});
const detailErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 200 },
  summary: "detailed workbook formula error scan",
});

const previewSpecs = [
  ["填报说明", "A1:H20", "01-填报说明.png"],
  ["最终80志愿", "A1:Q18", "02-最终80志愿.png"],
  ["新增22项", "A1:Q18", "03-新增22项.png"],
  ["替换4项", `A1:F${replacedSheet.rowCount}`, "04-替换4项.png"],
  ["其他AI筛查", "A1:S18", "05-其他AI筛查.png"],
  [directSheetName, "A1:Q16", "06-可直接填.png"],
  [manualSheetName, "A1:Q16", "07-必须确认.png"],
  [
    undergraduateSheetName,
    `A1:Q${undergraduateSheet.rowCount}`,
    "08-本科.png",
  ],
];
for (const [sheetName, range, fileName] of previewSpecs) {
  const image = await workbook.render({
    sheetName,
    range,
    scale: 1.15,
    format: "png",
  });
  await fs.writeFile(
    `${previewDir}/${fileName}`,
    new Uint8Array(await image.arrayBuffer()),
  );
}
const finalBottom = await workbook.render({
  sheetName: "最终80志愿",
  range: "A64:Q81",
  scale: 1.15,
  format: "png",
});
await fs.writeFile(
  `${previewDir}/09-最终80志愿末尾.png`,
  new Uint8Array(await finalBottom.arrayBuffer()),
);

const detailPath = `${outputDir}/2026浙江二段最终80志愿_冲25稳40保15.xlsx`;
const detailOutput = await SpreadsheetFile.exportXlsx(workbook);
await detailOutput.save(detailPath);

const templateWorkbook = await SpreadsheetFile.importXlsx(
  await FileBlob.load(templatePath),
);
const templateSheet = templateWorkbook.worksheets.getItem("Sheet1");
const headerCheck = await templateWorkbook.inspect({
  kind: "table",
  range: "Sheet1!A1:D3",
  include: "values,formulas",
  tableMaxRows: 3,
  tableMaxCols: 4,
});
const expectedHeader = ["院校代码", "院校名称", "专业代码", "专业名称"];
const headerValues = JSON.parse(headerCheck.ndjson).values[0];
if (JSON.stringify(headerValues) !== JSON.stringify(expectedHeader)) {
  throw new Error(`模板表头不符合预期：${JSON.stringify(headerValues)}`);
}
const templateRows = [...allRows]
  .sort((left, right) => Number(left["志愿序号"]) - Number(right["志愿序号"]))
  .map((row) => [
    /^\d+$/.test(String(row["院校代码"]))
      ? Number(row["院校代码"])
      : row["院校代码"],
    row["院校名称"],
    /^\d+$/.test(String(row["专业代码"]))
      ? Number(row["专业代码"])
      : row["专业代码"],
    row["专业名称"],
  ]);
templateSheet.getRange("A2:D81").values = templateRows;
templateSheet.getRange("A2:A81").format.numberFormat = "0000";
templateSheet.getRange("C2:C81").format.numberFormat = "000";
templateSheet.getRange("B1:B82").format.columnWidth = 42;
templateSheet.getRange("D1:D82").format.columnWidth = 48;
const templateCheck = await templateWorkbook.inspect({
  kind: "table",
  range: "Sheet1!A1:D81",
  include: "values,formulas",
  tableMaxRows: 81,
  tableMaxCols: 4,
});
const templateErrors = await templateWorkbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "template formula error scan",
});
for (const [range, fileName] of [
  ["A1:D20", "10-导入模板前20行.png"],
  ["A63:D81", "11-导入模板后19行.png"],
]) {
  const image = await templateWorkbook.render({
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
const templateXlsxPath = `${outputDir}/志愿录入模板_最终80.xlsx`;
const templateOutput = await SpreadsheetFile.exportXlsx(templateWorkbook);
await templateOutput.save(templateXlsxPath);

console.log(
  JSON.stringify({
    detailPath,
    templateXlsxPath,
    previews: previewSpecs.length + 3,
    summaryCheck: summaryCheck.ndjson,
    finalCheck: finalCheck.ndjson,
    detailErrors: detailErrors.ndjson,
    templateErrors: templateErrors.ndjson,
    templateRows: JSON.parse(templateCheck.ndjson).values.length - 1,
  }),
);
