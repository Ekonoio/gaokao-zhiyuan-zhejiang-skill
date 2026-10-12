import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const outputDir =
  process.env.OUTPUT_DIR ??
  `${root}/outputs/final_plan`;
const previewDir =
  process.env.PREVIEW_DIR ??
  `${outputDir}/previews/final-workbook`;
const workbookName = process.env.WORKBOOK_NAME ?? "最终志愿方案.xlsx";
const workbookTitle =
  process.env.WORKBOOK_TITLE ?? "2026浙江普通类二段最终志愿方案";

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const workbook = Workbook.create();
const summary = workbook.worksheets.add("填报说明");

const allRows = JSON.parse(
  await fs.readFile(`${outputDir}/最终志愿数据.json`, "utf8"),
);
const undergraduateRows = allRows.filter((row) =>
  ["本科", "职业本科"].includes(row["学历层次"]),
);
const reviewRows = allRows.filter(
  (row) => row["填报状态"] === "必须人工确认",
);
const directRows = allRows.filter((row) => row["填报状态"] === "可直接填");
const undergraduateSheetName = `本科${undergraduateRows.length}个`;
const reviewSheetName = `人工确认${reviewRows.length}`;
const directSheetName = `直接填${directRows.length}`;
const undergraduateGaps = undergraduateRows
  .flatMap((row) =>
    ["2025位次差", "2024位次差", "2023位次差"].map((header) =>
      Number(row[header]),
    ),
  )
  .filter((value) => Number.isFinite(value));
const closestUndergraduateGap =
  undergraduateGaps.length > 0 ? Math.max(...undergraduateGaps) : null;
const headers = Object.keys(allRows[0]);
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
]);
const typedValue = (row, header, columnIndex) => {
  const value = row[header] ?? "";
  if ((columnIndex === 6 || columnIndex === 8) && /^\d+$/.test(value)) {
    return Number(value);
  }
  if (numericHeaders.has(header) && value !== "") {
    const number = Number(value);
    return Number.isFinite(number) ? number : value;
  }
  return value;
};

const imported = [];
for (const [sheetName, tableName, rows] of [
  ["最终80志愿", "Final80Table", allRows],
  [undergraduateSheetName, "UndergraduateTable", undergraduateRows],
  [reviewSheetName, "ReviewTable", reviewRows],
  [directSheetName, "DirectTable", directRows],
]) {
  const sheet = workbook.worksheets.add(sheetName);
  const matrix = [
    headers,
    ...rows.map((row) =>
      headers.map((header, columnIndex) => typedValue(row, header, columnIndex)),
    ),
  ];
  const rowCount = matrix.length;
  sheet.getRange(`A1:AK${rowCount}`).values = matrix;
  imported.push({ sheet, sheetName, tableName, rowCount });
}

summary.showGridLines = false;
summary.mergeCells("A1:H1");
summary.getRange("A1").values = [[workbookTitle]];
summary.getRange("A1:H1").format = {
  fill: "#20323A",
  font: { bold: true, color: "#FFFFFF", size: 18 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
summary.getRange("A1:H1").format.rowHeight = 38;

summary.getRange("A3:A9").values = [
  ["最终志愿数"],
  ["冲"],
  ["稳"],
  ["保"],
  ["本科"],
  ["可直接填"],
  ["必须人工确认"],
];
summary.getRange("B3:B9").formulas = [
  ["=COUNTA('最终80志愿'!$C$2:$C$81)"],
  ['=COUNTIF(\'最终80志愿\'!$D$2:$D$81,"冲")'],
  ['=COUNTIF(\'最终80志愿\'!$D$2:$D$81,"稳")'],
  ['=COUNTIF(\'最终80志愿\'!$D$2:$D$81,"保")'],
  [
    '=COUNTIF(\'最终80志愿\'!$E$2:$E$81,"本科")+COUNTIF(\'最终80志愿\'!$E$2:$E$81,"职业本科")',
  ],
  ['=COUNTIF(\'最终80志愿\'!$A$2:$A$81,"可直接填")'],
  ['=COUNTIF(\'最终80志愿\'!$A$2:$A$81,"必须人工确认")'],
];
summary.getRange("D3:E8").values = [
  ["考生分数", 460],
  ["原始位次", 220000],
  ["选科", "政治、历史、地理"],
  ["填报段次", "普通类二段"],
  [
    "本科结论",
    `${undergraduateRows.length}个民办本科，仅低概率冲刺`,
  ],
  ["听力处理", "听力情况待确认不作硬排除；章程明确限制时复核"],
];
summary.getRange("A3:A9").format = {
  fill: "#DCE8EA",
  font: { bold: true, color: "#20323A" },
};
summary.getRange("B3:B9").format = {
  fill: "#F6F8F8",
  font: { bold: true, color: "#111827", size: 14 },
  numberFormat: "0",
};
summary.getRange("D3:D8").format = {
  fill: "#E8E4D8",
  font: { bold: true, color: "#3D3526" },
};
summary.getRange("E3:E8").format = {
  fill: "#FBFAF6",
  wrapText: true,
};
summary.getRange("A3:B9").format.borders = {
  preset: "all",
  style: "thin",
  color: "#B8C5C9",
};
summary.getRange("D3:E8").format.borders = {
  preset: "all",
  style: "thin",
  color: "#CCC4B3",
};

summary.mergeCells("A11:H11");
summary.getRange("A11").values = [["使用规则"]];
summary.getRange("A11:H11").format = {
  fill: "#3E5F68",
  font: { bold: true, color: "#FFFFFF" },
};
const notes = [
  "1. 按“最终80志愿”中的志愿序号从1到80填报，不按录取概率重新排序。",
  "2. “可直接填”表示当前个性化计划、选科、学费和公民办属性已通过规则；提交前仍须核对官方系统代码。",
  "3. “必须人工确认”完成确认后仍按原序号填报；不要因确认而擅自打乱其余志愿。",
  "4. 电子商务仅作转专业跳板，转专业失败时不得把它当稳保志愿。",
  closestUndergraduateGap === null
    ? "5. 当前推荐表未保留本科志愿。"
    : `5. 所选本科历史最近位次仍比考生靠前${Math.abs(closestUndergraduateGap)}位，${undergraduateRows.length}个本科全部只作低概率冲刺。`,
];
for (let index = 0; index < notes.length; index += 1) {
  const row = 12 + index;
  summary.mergeCells(`A${row}:H${row}`);
  summary.getRange(`A${row}`).values = [[notes[index]]];
  summary.getRange(`A${row}:H${row}`).format = {
    fill: index % 2 === 0 ? "#F6F8F8" : "#FFFFFF",
    wrapText: true,
    font: { color: "#263238" },
  };
  summary.getRange(`A${row}:H${row}`).format.rowHeight = 28;
}
summary.getRange("A1:H16").format.font.name = "Microsoft YaHei";
summary.getRange("A1:H16").format.verticalAlignment = "center";
summary.getRange("A1:A16").format.columnWidth = 18;
summary.getRange("B1:B16").format.columnWidth = 14;
summary.getRange("C1:C16").format.columnWidth = 3;
summary.getRange("D1:D16").format.columnWidth = 16;
summary.getRange("E1:H16").format.columnWidth = 22;
summary.freezePanes.freezeRows(1);

for (const { sheet, tableName, rowCount } of imported) {
  sheet.showGridLines = false;
  const fullRange = sheet.getRange(`A1:AK${rowCount}`);
  fullRange.format.font.name = "Microsoft YaHei";
  fullRange.format.font.size = 10;
  fullRange.format.verticalAlignment = "center";
  fullRange.format.wrapText = true;
  fullRange.format.rowHeight = 28;
  sheet.getRange("A1:AK1").format = {
    fill: "#20323A",
    font: { bold: true, color: "#FFFFFF", size: 10 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange("A1:AK1").format.rowHeight = 38;
  sheet.getRange(`A1:AK${rowCount}`).format.borders = {
    insideHorizontal: { style: "thin", color: "#E3E8EA" },
    bottom: { style: "thin", color: "#AAB7BC" },
  };

  sheet.getRange(`A1:A${rowCount}`).format.columnWidth = 13;
  sheet.getRange(`B1:B${rowCount}`).format.columnWidth = 42;
  sheet.getRange(`C1:F${rowCount}`).format.columnWidth = 9;
  sheet.getRange(`G1:G${rowCount}`).format.columnWidth = 12;
  sheet.getRange(`H1:H${rowCount}`).format.columnWidth = 24;
  sheet.getRange(`I1:I${rowCount}`).format.columnWidth = 11;
  sheet.getRange(`J1:J${rowCount}`).format.columnWidth = 34;
  sheet.getRange(`K1:L${rowCount}`).format.columnWidth = 12;
  sheet.getRange(`M1:M${rowCount}`).format.columnWidth = 8;
  sheet.getRange(`N1:Y${rowCount}`).format.columnWidth = 13;
  sheet.getRange(`Z1:AG${rowCount}`).format.columnWidth = 16;
  sheet.getRange(`AH1:AI${rowCount}`).format.columnWidth = 45;
  sheet.getRange(`AJ1:AJ${rowCount}`).format.columnWidth = 36;
  sheet.getRange(`AK1:AK${rowCount}`).format.columnWidth = 25;
  sheet.getRange(`N2:Y${rowCount}`).format.numberFormat = "#,##0";
  sheet.getRange(`G2:G${rowCount}`).format.numberFormat = "0000";
  sheet.getRange(`I2:I${rowCount}`).format.numberFormat = "000";

  if (rowCount > 1) {
    sheet.getRange(`A2:A${rowCount}`).conditionalFormats.add("containsText", {
      text: "必须人工确认",
      format: {
        fill: "#FCE3E1",
        font: { bold: true, color: "#9B1C1C" },
      },
    });
    sheet.getRange(`A2:A${rowCount}`).conditionalFormats.add("containsText", {
      text: "可直接填",
      format: {
        fill: "#DDF1E4",
        font: { bold: true, color: "#17613A" },
      },
    });
    sheet.getRange(`D2:D${rowCount}`).conditionalFormats.add("containsText", {
      text: "冲",
      format: { fill: "#FCE8D5", font: { bold: true, color: "#9A4B00" } },
    });
    sheet.getRange(`D2:D${rowCount}`).conditionalFormats.add("containsText", {
      text: "稳",
      format: { fill: "#E2ECF7", font: { bold: true, color: "#24547D" } },
    });
    sheet.getRange(`D2:D${rowCount}`).conditionalFormats.add("containsText", {
      text: "保",
      format: { fill: "#DDF1E4", font: { bold: true, color: "#17613A" } },
    });
  }

  const table = sheet.tables.add(`A1:AK${rowCount}`, true, tableName);
  table.style = "TableStyleMedium2";
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(4);
}

const summaryCheck = await workbook.inspect({
  kind: "table",
  range: "填报说明!A1:H16",
  include: "values,formulas",
  tableMaxRows: 16,
  tableMaxCols: 8,
});
const finalCheck = await workbook.inspect({
  kind: "table",
  range: "最终80志愿!A1:O12",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 15,
});
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});

for (const [sheetName, range, fileName] of [
  ["填报说明", "A1:H16", "填报说明.png"],
  ["最终80志愿", "A1:O16", "最终80志愿.png"],
  [undergraduateSheetName, `A1:O${Math.min(16, undergraduateRows.length + 1)}`, "本科.png"],
  [reviewSheetName, `A1:O${Math.min(16, reviewRows.length + 1)}`, "人工确认.png"],
  [directSheetName, `A1:O${Math.min(16, directRows.length + 1)}`, "直接填.png"],
]) {
  const previewSheet = workbook.worksheets.getItem(sheetName);
  if (sheetName !== "填报说明") {
    previewSheet.freezePanes.unfreeze();
  }
  const preview = await workbook.render({
    sheetName,
    range,
    scale: 1.2,
    format: "png",
  });
  await fs.writeFile(
    `${previewDir}/${fileName}`,
    new Uint8Array(await preview.arrayBuffer()),
  );
  if (sheetName !== "填报说明") {
    previewSheet.freezePanes.freezeRows(1);
    previewSheet.freezePanes.freezeColumns(4);
  }
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/${workbookName}`);

console.log(
  JSON.stringify({
    summary: summaryCheck.ndjson,
    final: finalCheck.ndjson,
    errors: errors.ndjson,
    output: `${outputDir}/${workbookName}`,
    previewDir,
  }),
);
