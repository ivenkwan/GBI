/** TypeScript types for Flint Chart integration. */

export interface ChartAssemblyInput {
  chartType: string;
  encodings: Record<string, { field: string }>;
  baseSize: { width: number; height: number };
  semantic_types?: Record<string, "Category" | "Quantity" | "Temporal">;
  data: {
    values?: Record<string, unknown>[];
    url?: string;
  };
}

export type ChartBackend = "vegalite" | "echarts" | "chartjs";

export type ChartOutputFormat = "png" | "svg";
