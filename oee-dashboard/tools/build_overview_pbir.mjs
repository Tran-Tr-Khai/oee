import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardDir = path.resolve(scriptDir, "..");
const visualsDir = path.join(
  dashboardDir,
  "oee_dashboard.Report",
  "definition",
  "pages",
  "40c30aa543ec00d96e94",
  "visuals",
);
const schema =
  "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.11.0/schema.json";

if (path.basename(visualsDir) !== "visuals") {
  throw new Error(`Refusing to rebuild unexpected path: ${visualsDir}`);
}

const literal = (value) => ({ expr: { Literal: { Value: value } } });
const bool = (value) => literal(value ? "true" : "false");
const number = (value) => literal(`${value}D`);
const integer = (value) => literal(`${value}L`);
const text = (value) => literal(`'${value.replaceAll("'", "''")}'`);
const fill = (color) => ({ solid: { color: text(color) } });
const measureFill = (table, measure) => ({
  solid: {
    color: {
      expr: measureField(table, measure),
    },
  },
});

const COLORS = {
  ink: "#101828",
  muted: "#667085",
  subtle: "#98A2B3",
  border: "#E4E7EC",
  canvas: "#F7F8FA",
  white: "#FFFFFF",
  yellow: "#F6C90E",
  yellowSoft: "#FFF8D6",
  green: "#2FA66A",
  red: "#E63946",
  navy: "#344054",
};

const FONT_DISPLAY = "Bahnschrift SemiBold";
const FONT_BODY = "Aptos";

const columnField = (table, property) => ({
  Column: {
    Expression: { SourceRef: { Entity: table } },
    Property: property,
  },
});

const measureField = (table, property) => ({
  Measure: {
    Expression: { SourceRef: { Entity: table } },
    Property: property,
  },
});

const columnProjection = (table, property, active = false) => ({
  field: columnField(table, property),
  queryRef: `${table}.${property}`,
  nativeQueryRef: property,
  ...(active ? { active: true } : {}),
});

const measureProjection = (table, property) => ({
  field: measureField(table, property),
  queryRef: `${table}.${property}`,
  nativeQueryRef: property,
});

const position = (x, y, width, height, z, tabOrder = z) => ({
  x,
  y,
  z,
  height,
  width,
  tabOrder,
});

const transparentVco = () => ({
  background: [{ properties: { show: bool(false) } }],
  border: [{ properties: { show: bool(false) } }],
  dropShadow: [{ properties: { show: bool(false) } }],
  padding: [
    {
      properties: {
        top: number(0),
        bottom: number(0),
        left: number(0),
        right: number(0),
      },
    },
  ],
  visualHeader: [{ properties: { show: bool(false) } }],
});

const containerVco = ({
  titleValue = "",
  background = COLORS.white,
  border = COLORS.border,
  shadow = true,
  radius = 12,
  padding = 10,
  titleSize = 11,
} = {}) => ({
  background: [
    {
      properties: {
        show: bool(true),
        color: fill(background),
        transparency: number(0),
      },
    },
  ],
  border: [
    {
      properties: {
        show: bool(Boolean(border)),
        color: fill(border || COLORS.border),
        width: number(1),
        radius: number(radius),
      },
    },
  ],
  dropShadow: [
    {
      properties: {
        show: bool(shadow),
        preset: text("Bottom"),
        position: text("Outer"),
        color: fill(COLORS.ink),
        transparency: number(94),
      },
    },
  ],
  title: [
    {
      properties: {
        show: bool(Boolean(titleValue)),
        text: text(titleValue),
        fontColor: fill(COLORS.ink),
        fontFamily: text(FONT_DISPLAY),
        fontSize: number(titleSize),
        bold: bool(true),
        titleWrap: bool(false),
      },
    },
  ],
  spacing: [
    {
      properties: {
        customizeSpacing: bool(true),
        spaceBelowTitleArea: number(4),
      },
      selector: { id: "default" },
    },
  ],
  padding: [
    {
      properties: {
        top: number(padding),
        bottom: number(padding),
        left: number(padding),
        right: number(padding),
      },
    },
  ],
  visualHeader: [{ properties: { show: bool(false) } }],
});

const titleOnlyVco = (titleValue) => ({
  ...transparentVco(),
  title: [
    {
      properties: {
        show: bool(true),
        text: text(titleValue),
        fontColor: fill(COLORS.ink),
        fontFamily: text(FONT_DISPLAY),
        fontSize: number(10),
        bold: bool(true),
        titleWrap: bool(false),
      },
    },
  ],
  spacing: [
    {
      properties: {
        customizeSpacing: bool(true),
        spaceBelowTitleArea: number(2),
      },
      selector: { id: "default" },
    },
  ],
});

const baseVisual = (name, visualPosition, visual) => ({
  $schema: schema,
  name,
  position: visualPosition,
  visual,
  filterConfig: { filters: [] },
});

const textboxVisual = ({
  id,
  x,
  y,
  width,
  height,
  z,
  paragraphs,
  vco = transparentVco(),
}) =>
  baseVisual(id, position(x, y, width, height, z), {
    visualType: "textbox",
    objects: {
      general: [
        {
          properties: {
            paragraphs: paragraphs.map((paragraph) => ({
              textRuns: [
                {
                  value: paragraph.value,
                  textStyle: {
                    fontFamily: paragraph.fontFamily || FONT_BODY,
                    fontSize: `${paragraph.fontSize || 10}px`,
                    color: paragraph.color || COLORS.ink,
                    ...(paragraph.bold ? { fontWeight: "bold" } : {}),
                  },
                },
              ],
              horizontalTextAlignment: paragraph.alignment || "left",
            })),
          },
        },
      ],
    },
    visualContainerObjects: vco,
  });

const panelVisual = ({
  id,
  x,
  y,
  width,
  height,
  z,
  background = COLORS.white,
  shadow = true,
}) =>
  textboxVisual({
    id,
    x,
    y,
    width,
    height,
    z,
    paragraphs: [{ value: "" }],
    vco: containerVco({
      background,
      shadow,
      padding: 0,
    }),
  });

const shapeVisual = ({
  id,
  x,
  y,
  width,
  height,
  z,
  color,
}) =>
  baseVisual(id, position(x, y, width, height, z), {
    visualType: "shape",
    objects: {
      shape: [{ properties: { tileShape: text("rectangle") } }],
      fill: [
        {
          properties: {
            fillColor: fill(color),
            transparency: number(0),
          },
          selector: { id: "default" },
        },
      ],
      outline: [
        {
          properties: { show: bool(false) },
          selector: { id: "default" },
        },
      ],
    },
    visualContainerObjects: transparentVco(),
  });

const cardVisual = ({
  id,
  x,
  y,
  width,
  height,
  z,
  table,
  measure,
  label = "",
  valueColor = COLORS.ink,
  valueColorMeasure,
  labelColor = COLORS.muted,
  fontSize = 24,
  labelSize = 9,
  bold = true,
  valueAlign = "left",
  showLabel = true,
  wrap = false,
  vco = transparentVco(),
}) =>
  baseVisual(id, position(x, y, width, height, z), {
    visualType: "cardVisual",
    query: {
      queryState: {
        Data: {
          projections: [measureProjection(table, measure)],
        },
      },
    },
    objects: {
      value: [
        {
          properties: {
            show: bool(true),
            fontFamily: text(bold ? FONT_DISPLAY : FONT_BODY),
            fontSize: number(fontSize),
            bold: bool(bold),
            fontColor: valueColorMeasure
              ? measureFill(table, valueColorMeasure)
              : fill(valueColor),
            horizontalAlignment: text(valueAlign),
            showBlankAs: text("--"),
            textWrap: bool(wrap),
          },
          selector: { id: "default" },
        },
      ],
      label: [
        {
          properties: {
            show: bool(showLabel),
            text: text(label),
            fontFamily: text(FONT_BODY),
            fontSize: number(labelSize),
            fontColor: fill(labelColor),
            position: text("belowValue"),
            horizontalAlignment: text(valueAlign),
            textWrap: bool(wrap),
          },
          selector: { id: "default" },
        },
      ],
      outline: [
        {
          properties: { show: bool(false) },
          selector: { id: "default" },
        },
      ],
      layout: [
        {
          properties: {
            topOuterMargin: integer(0),
            bottomOuterMargin: integer(0),
            leftOuterMargin: integer(0),
            rightOuterMargin: integer(0),
            paddingUniform: integer(0),
          },
          selector: { id: "default" },
        },
      ],
    },
    visualContainerObjects: vco,
    drillFilterOtherVisuals: true,
  });

const slicerVisual = ({
  id,
  x,
  width,
  z,
  table,
  column,
  mode,
  label,
}) =>
  baseVisual(id, position(x, 7, width, 76, z), {
    visualType: "slicer",
    query: {
      queryState: {
        Values: {
          projections: [columnProjection(table, column)],
        },
      },
    },
    objects: {
      data: [{ properties: { mode: text(mode) } }],
      header: [
        {
          properties: {
            show: bool(true),
            text: text(label),
          },
        },
      ],
    },
    visualContainerObjects: containerVco({
      shadow: false,
      padding: 0,
      radius: 10,
    }),
    drillFilterOtherVisuals: true,
  });

const axisStyle = {
  categoryAxis: [
    {
      properties: {
        show: bool(true),
        axisType: text("Scalar"),
        fontFamily: text(FONT_BODY),
        fontSize: number(8),
        labelColor: fill(COLORS.muted),
        showAxisTitle: bool(false),
        gridlineShow: bool(false),
      },
    },
  ],
  valueAxis: [
    {
      properties: {
        show: bool(true),
        fontFamily: text(FONT_BODY),
        fontSize: number(8),
        labelColor: fill(COLORS.muted),
        showAxisTitle: bool(false),
        gridlineShow: bool(true),
        gridlineThickness: number(1),
        gridlineColor: fill(COLORS.border),
        gridlineTransparency: number(0),
        gridlineStyle: text("solid"),
      },
    },
  ],
};

const lineChartVisual = ({
  id,
  x,
  y,
  width,
  height,
  z,
  titleValue,
  series,
}) =>
  baseVisual(id, position(x, y, width, height, z), {
    visualType: "lineChart",
    query: {
      queryState: {
        Category: {
          projections: [columnProjection("gld_date_dim", "date", true)],
        },
        Y: {
          projections: series.map((item) =>
            measureProjection(item.table, item.measure),
          ),
        },
      },
      sortDefinition: {
        sort: [
          {
            field: columnField("gld_date_dim", "date"),
            direction: "Ascending",
          },
        ],
        isDefaultSort: true,
      },
    },
    objects: {
      ...axisStyle,
      legend: [
        {
          properties: {
            show: bool(true),
            position: text("TopRight"),
            showTitle: bool(false),
            fontFamily: text(FONT_BODY),
            fontSize: number(8),
            labelColor: fill(COLORS.muted),
            legendMarkerRendering: text("lineAndMarker"),
          },
        },
      ],
      lineStyles: series.map((item) => ({
        properties: {
          strokeShow: bool(true),
          strokeWidth: number(item.width || 2.3),
          strokeColor: fill(item.color),
          strokeTransparency: number(0),
          lineStyle: text(item.style || "solid"),
          showMarker: bool(false),
          markerShape: text("circle"),
          markerSize: number(4),
          markerColor: fill(item.color),
          lineChartType: text("smooth"),
        },
        selector: {
          metadata: `${item.table}.${item.measure}`,
        },
      })),
    },
    visualContainerObjects: containerVco({
      titleValue,
      titleSize: 10,
      padding: 9,
    }),
    drillFilterOtherVisuals: true,
  });

const barChartVisual = ({
  id,
  x,
  y,
  width,
  height,
  z,
  titleValue,
  table,
  measure,
  color,
}) =>
  baseVisual(id, position(x, y, width, height, z), {
    visualType: "clusteredBarChart",
    query: {
      queryState: {
        Category: {
          projections: [
            columnProjection("gld_machine_dim", "machine", true),
          ],
        },
        Y: {
          projections: [measureProjection(table, measure)],
        },
      },
      sortDefinition: {
        sort: [
          {
            field: measureField(table, measure),
            direction: "Descending",
          },
        ],
        isDefaultSort: true,
      },
    },
    objects: {
      categoryAxis: [
        {
          properties: {
            show: bool(true),
            fontFamily: text(FONT_BODY),
            fontSize: number(8),
            labelColor: fill(COLORS.navy),
            showAxisTitle: bool(false),
            gridlineShow: bool(false),
            maxMarginFactor: integer(30),
          },
        },
      ],
      valueAxis: [
        {
          properties: {
            show: bool(true),
            fontFamily: text(FONT_BODY),
            fontSize: number(8),
            labelColor: fill(COLORS.muted),
            showAxisTitle: bool(false),
            gridlineShow: bool(true),
            gridlineThickness: number(1),
            gridlineColor: fill(COLORS.border),
          },
        },
      ],
      dataPoint: [
        {
          properties: {
            defaultColor: fill(color),
            fill: fill(color),
            fillTransparency: number(0),
            borderShow: bool(false),
          },
        },
      ],
      labels: [
        {
          properties: {
            show: bool(true),
            fontFamily: text(FONT_BODY),
            fontSize: number(8),
            color: fill(COLORS.navy),
          },
        },
      ],
      layout: [
        {
          properties: {
            clusteredGapSize: number(22),
          },
        },
      ],
    },
    visualContainerObjects: titleOnlyVco(titleValue),
    drillFilterOtherVisuals: true,
  });

const visuals = [
  shapeVisual({
    id: "0a1b2c3d4e5f60718293",
    x: 24,
    y: 20,
    width: 4,
    height: 52,
    z: 1,
    color: COLORS.yellow,
  }),
  textboxVisual({
    id: "1b2c3d4e5f60718293a4",
    x: 42,
    y: 15,
    width: 530,
    height: 62,
    z: 2,
    paragraphs: [
      {
        value: "FACTORY OPERATIONS CONTROL TOWER",
        fontFamily: FONT_DISPLAY,
        fontSize: 21,
        color: COLORS.ink,
        bold: true,
      },
      {
        value: "252 status-monitored machines  |  Health  >  Driver  >  Action",
        fontFamily: FONT_BODY,
        fontSize: 10,
        color: COLORS.muted,
      },
    ],
  }),
  cardVisual({
    id: "2c3d4e5f60718293a4b5",
    x: 580,
    y: 22,
    width: 218,
    height: 42,
    z: 3,
    table: "gld_production_daily_fact",
    measure: "Reporting Date Label",
    fontSize: 9,
    bold: true,
    showLabel: false,
    valueColor: COLORS.navy,
    valueAlign: "right",
  }),
  slicerVisual({
    id: "3d4e5f60718293a4b5c6",
    x: 814,
    width: 210,
    z: 4,
    table: "gld_date_dim",
    column: "date",
    mode: "Between",
    label: "DATE RANGE",
  }),
  slicerVisual({
    id: "4e5f60718293a4b5c6d7",
    x: 1040,
    width: 216,
    z: 5,
    table: "gld_machine_dim",
    column: "machine",
    mode: "Dropdown",
    label: "MACHINE",
  }),

  panelVisual({
    id: "5f60718293a4b5c6d7e8",
    x: 24,
    y: 96,
    width: 420,
    height: 158,
    z: 10,
    background: COLORS.yellowSoft,
  }),
  shapeVisual({
    id: "60718293a4b5c6d7e8f9",
    x: 24,
    y: 96,
    width: 5,
    height: 158,
    z: 11,
    color: COLORS.yellow,
  }),
  textboxVisual({
    id: "718293a4b5c6d7e8f90a",
    x: 46,
    y: 108,
    width: 170,
    height: 24,
    z: 12,
    paragraphs: [
      {
        value: "FACTORY HEALTH SCORE V1",
        fontFamily: FONT_DISPLAY,
        fontSize: 10,
        color: COLORS.navy,
        bold: true,
      },
    ],
  }),
  cardVisual({
    id: "8293a4b5c6d7e8f90a1b",
    x: 46,
    y: 128,
    width: 156,
    height: 100,
    z: 13,
    table: "gld_production_daily_fact",
    measure: "Factory Health at Reporting Date %",
    label: "PROVISIONAL COMPOSITE",
    fontSize: 40,
    labelSize: 9,
    valueColor: COLORS.ink,
  }),
  cardVisual({
    id: "93a4b5c6d7e8f90a1b2c",
    x: 218,
    y: 126,
    width: 190,
    height: 48,
    z: 14,
    table: "gld_production_daily_fact",
    measure: "Factory Health Status",
    label: "CURRENT STATE",
    fontSize: 18,
    labelSize: 8,
    valueColor: COLORS.ink,
  }),
  cardVisual({
    id: "a4b5c6d7e8f90a1b2c3d",
    x: 218,
    y: 175,
    width: 198,
    height: 62,
    z: 15,
    table: "gld_production_daily_fact",
    measure: "Factory Health Insight",
    fontSize: 10,
    bold: false,
    showLabel: false,
    valueColor: COLORS.navy,
    wrap: true,
  }),

  panelVisual({
    id: "b5c6d7e8f90a1b2c3d4e",
    x: 460,
    y: 96,
    width: 796,
    height: 158,
    z: 10,
  }),
  textboxVisual({
    id: "c6d7e8f90a1b2c3d4e5f",
    x: 482,
    y: 108,
    width: 300,
    height: 22,
    z: 12,
    paragraphs: [
      {
        value: "WHAT IS DRIVING HEALTH?",
        fontFamily: FONT_DISPLAY,
        fontSize: 10,
        color: COLORS.navy,
        bold: true,
      },
    ],
  }),
  shapeVisual({
    id: "d7e8f90a1b2c3d4e5f60",
    x: 719,
    y: 132,
    width: 1,
    height: 98,
    z: 12,
    color: COLORS.border,
  }),
  shapeVisual({
    id: "e8f90a1b2c3d4e5f6071",
    x: 980,
    y: 132,
    width: 1,
    height: 98,
    z: 12,
    color: COLORS.border,
  }),
  cardVisual({
    id: "f90a1b2c3d4e5f607182",
    x: 484,
    y: 132,
    width: 210,
    height: 74,
    z: 13,
    table: "gld_production_daily_fact",
    measure: "Production at Reporting Date Mts",
    label: "DAILY OUTPUT  |  252 MACHINES",
    fontSize: 27,
    labelSize: 9,
  }),
  cardVisual({
    id: "0a1c2e3f4b5d60718293",
    x: 484,
    y: 205,
    width: 210,
    height: 30,
    z: 13,
    table: "gld_production_daily_fact",
    measure: "Production vs Previous 7D %",
    label: "vs previous 7D average",
    fontSize: 11,
    labelSize: 8,
    valueColorMeasure: "Production Change Color",
  }),
  cardVisual({
    id: "1b2d3f4a5c60718293e4",
    x: 744,
    y: 132,
    width: 210,
    height: 74,
    z: 13,
    table: "gld_machine_status_daily_fact",
    measure: "Availability at Reporting Date %",
    label: "MACHINE AVAILABILITY",
    fontSize: 27,
    labelSize: 9,
    valueColor: COLORS.green,
  }),
  cardVisual({
    id: "2c3e4a5b6d718293f405",
    x: 744,
    y: 205,
    width: 210,
    height: 30,
    z: 13,
    table: "gld_machine_status_daily_fact",
    measure: "Availability vs Previous 7D %",
    label: "vs previous 7 days",
    fontSize: 11,
    labelSize: 8,
    valueColorMeasure: "Availability Change Color",
  }),
  cardVisual({
    id: "3d4f5b6c7e8293a40516",
    x: 1004,
    y: 132,
    width: 220,
    height: 60,
    z: 13,
    table: "gld_production_daily_fact",
    measure: "Plan Attainment at Reporting Date %",
    label: "PLAN ATTAINMENT",
    fontSize: 27,
    labelSize: 9,
    valueColor: COLORS.ink,
  }),
  cardVisual({
    id: "4e5a6c7d8f93b4051627",
    x: 1004,
    y: 192,
    width: 220,
    height: 24,
    z: 13,
    table: "gld_production_daily_fact",
    measure: "Plan vs Previous 7D %",
    label: "vs previous 7 days",
    fontSize: 11,
    labelSize: 8,
    valueColorMeasure: "Plan Change Color",
  }),
  cardVisual({
    id: "4f5a6b7c8d9e0f1a2b3c",
    x: 1004,
    y: 220,
    width: 220,
    height: 18,
    z: 13,
    table: "gld_production_daily_fact",
    measure: "Plan Coverage Label at Reporting Date",
    fontSize: 8,
    bold: false,
    showLabel: false,
    valueColor: COLORS.muted,
  }),

  lineChartVisual({
    id: "5f6b7d8e9a04c5162738",
    x: 24,
    y: 270,
    width: 758,
    height: 225,
    z: 20,
    titleValue: "PRODUCTION PULSE  |  Actual vs 7-day average",
    series: [
      {
        table: "gld_production_daily_fact",
        measure: "Production Through Reporting Date Mts",
        color: COLORS.yellow,
        width: 2.7,
      },
      {
        table: "gld_production_daily_fact",
        measure: "Production 7D Average",
        color: COLORS.muted,
        width: 1.8,
        style: "dashed",
      },
    ],
  }),
  lineChartVisual({
    id: "6a7c8e9f0b15d6273849",
    x: 798,
    y: 270,
    width: 458,
    height: 225,
    z: 21,
    titleValue: "AVAILABILITY PULSE  |  Actual vs 7-day average",
    series: [
      {
        table: "gld_machine_status_daily_fact",
        measure: "Availability %",
        color: COLORS.green,
        width: 2.7,
      },
      {
        table: "gld_machine_status_daily_fact",
        measure: "Availability 7D Average %",
        color: COLORS.muted,
        width: 1.8,
        style: "dashed",
      },
    ],
  }),

  panelVisual({
    id: "7b8d9f0a1c26e7384950",
    x: 24,
    y: 510,
    width: 1232,
    height: 190,
    z: 30,
  }),
  textboxVisual({
    id: "8c9e0a1b2d37f8495061",
    x: 44,
    y: 520,
    width: 430,
    height: 22,
    z: 31,
    paragraphs: [
      {
        value: "ACTION REQUIRED  |  WHERE TO INTERVENE",
        fontFamily: FONT_DISPLAY,
        fontSize: 10,
        color: COLORS.ink,
        bold: true,
      },
    ],
  }),
  barChartVisual({
    id: "9d0f1b2c3e48a9506172",
    x: 44,
    y: 548,
    width: 362,
    height: 138,
    z: 32,
    titleValue: "LOSS HOTSPOTS  |  Scheduled-time loss hours",
    table: "gld_machine_status_daily_fact",
    measure: "Lost Hours at Reporting Date",
    color: COLORS.red,
  }),
  shapeVisual({
    id: "0e1a2c3d4f59b0617283",
    x: 420,
    y: 548,
    width: 1,
    height: 134,
    z: 32,
    color: COLORS.border,
  }),
  barChartVisual({
    id: "1f2b3d4e5a60c1728394",
    x: 436,
    y: 548,
    width: 362,
    height: 138,
    z: 32,
    titleValue: "PLAN RISK  |  Largest shortfall mts",
    table: "gld_production_daily_fact",
    measure: "Plan Gap at Reporting Date Mts",
    color: COLORS.yellow,
  }),
  shapeVisual({
    id: "2a3c4e5f6b71d2839405",
    x: 812,
    y: 548,
    width: 1,
    height: 134,
    z: 32,
    color: COLORS.border,
  }),
  textboxVisual({
    id: "3b4d5f6a7c82e3940516",
    x: 832,
    y: 548,
    width: 380,
    height: 20,
    z: 32,
    paragraphs: [
      {
        value: "OPERATIONAL SIGNALS",
        fontFamily: FONT_DISPLAY,
        fontSize: 9,
        color: COLORS.navy,
        bold: true,
      },
    ],
  }),
  cardVisual({
    id: "4c5e6a7b8d93f4051627",
    x: 832,
    y: 568,
    width: 184,
    height: 52,
    z: 33,
    table: "gld_machine_status_daily_fact",
    measure: "Critical Machine Count at Reporting Date",
    label: "MACHINES <75% AVAIL.",
    fontSize: 19,
    labelSize: 7,
    valueColor: COLORS.red,
  }),
  cardVisual({
    id: "5d6f7b8c9e04a5162738",
    x: 1040,
    y: 568,
    width: 184,
    height: 52,
    z: 33,
    table: "gld_machine_status_daily_fact",
    measure: "Telemetry Conflict Count at Reporting Date",
    label: "OUTPUT WITH 0H RUNNING",
    fontSize: 19,
    labelSize: 7,
    valueColor: COLORS.red,
  }),
  cardVisual({
    id: "6e7a8c9d0f15b6273849",
    x: 832,
    y: 642,
    width: 184,
    height: 38,
    z: 33,
    table: "gld_machine_status_daily_fact",
    measure: "Missing Status Machine Count at Reporting Date",
    label: "MISSING STATUS SIGNAL",
    fontSize: 19,
    labelSize: 7,
    valueColor: COLORS.navy,
  }),
  cardVisual({
    id: "7f8b9d0e1a26c7384950",
    x: 1040,
    y: 642,
    width: 184,
    height: 38,
    z: 33,
    table: "gld_production_daily_fact",
    measure: "Plan Coverage at Reporting Date %",
    label: "PLAN COVERAGE",
    fontSize: 19,
    labelSize: 7,
    valueColor: COLORS.navy,
  }),
  textboxVisual({
    id: "8f901a2b3c4d5e6f7182",
    x: 832,
    y: 620,
    width: 380,
    height: 18,
    z: 33,
    paragraphs: [
      {
        value: "DATA QUALITY",
        fontFamily: FONT_DISPLAY,
        fontSize: 8,
        color: COLORS.navy,
        bold: true,
      },
    ],
  }),
];

fs.rmSync(visualsDir, { recursive: true, force: true });
fs.mkdirSync(visualsDir, { recursive: true });

for (const visualDefinition of visuals) {
  const visualDir = path.join(visualsDir, visualDefinition.name);
  fs.mkdirSync(visualDir, { recursive: true });
  fs.writeFileSync(
    path.join(visualDir, "visual.json"),
    `${JSON.stringify(visualDefinition, null, 2)}\n`,
    "utf8",
  );
}

console.log(`Built ${visuals.length} Overview visuals in ${visualsDir}`);
