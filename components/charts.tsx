"use client";

import { useId, useMemo, useState, useSyncExternalStore } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatDate, formatNumber } from "@/lib/api";
import type { AnalystAnswer, TrendPoint } from "@/lib/types";
import "./chart-motion.css";

type ChartUnit = "percent" | "milliseconds" | "usd" | "number";
type TooltipEntry = {
  color?: string;
  name?: string;
  value?: number | string | null;
};

let motionQuery: MediaQueryList | undefined;
const motionSubscribers = new Set<() => void>();
function getMotionQuery() {
  return (motionQuery ??= window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ));
}
function notifyMotionSubscribers() {
  motionSubscribers.forEach((listener) => listener());
}
function subscribeMotion(listener: () => void) {
  const query = getMotionQuery();
  if (!motionSubscribers.size)
    query.addEventListener("change", notifyMotionSubscribers);
  motionSubscribers.add(listener);
  return () => {
    motionSubscribers.delete(listener);
    if (!motionSubscribers.size)
      query.removeEventListener("change", notifyMotionSubscribers);
  };
}
function useChartMotion() {
  const reduced = useSyncExternalStore(
    subscribeMotion,
    () => getMotionQuery().matches,
    () => true,
  );
  return !reduced;
}
function metricUnit(key: string): ChartUnit {
  if (key.includes("/")) return "number";
  if (key === "rate" || /_(rate|percent|percentage|pct)$/.test(key))
    return "percent";
  if (key.endsWith("_ms")) return "milliseconds";
  if (key.includes("usd")) return "usd";
  return "number";
}
function formatChartValue(value: number | null | undefined, unit: ChartUnit) {
  if (value == null || !Number.isFinite(value)) return "—";
  if (unit === "percent") return `${formatNumber(value, 2)}%`;
  if (unit === "milliseconds") return `${formatNumber(value)} ms`;
  if (unit === "usd") return `$${formatNumber(value, 4)}`;
  return formatNumber(value, 2);
}
function axisValue(value: number, unit: ChartUnit) {
  if (unit === "percent") return `${formatNumber(value, 1)}%`;
  if (unit === "usd") return `$${formatNumber(value, 2)}`;
  if (Math.abs(value) >= 1_000_000)
    return `${formatNumber(value / 1_000_000, 1)}m`;
  if (Math.abs(value) >= 1000) return `${formatNumber(value / 1000, 1)}k`;
  return formatNumber(value, 1);
}
function categoryLabel(value: string | number) {
  const label = String(value).replace(/ recommendation$/i, "");
  return label.length > 20 ? `${label.slice(0, 18)}…` : label;
}
function armColor(label: string, index = 0) {
  if (/manual|control|baseline/i.test(label)) return "var(--text-secondary)";
  if (/ollama|gpt-oss|gemma/i.test(label)) return "var(--blue)";
  if (/gpt|openrouter|openai/i.test(label)) return "var(--purple)";
  return ["var(--accent-bright)", "var(--purple)", "var(--blue)"][index % 3];
}
function ChartTooltip({
  active,
  payload,
  label,
  unit = "number",
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
  unit?: ChartUnit;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip motion-chart-tooltip">
      <strong>
        {String(label).match(/^\d{4}-\d{2}-\d{2}/)
          ? formatDate(String(label))
          : label}
      </strong>
      {payload.map((entry) => (
        <p key={entry.name}>
          <span style={{ color: entry.color }}>{entry.name}</span>
          <span>
            {typeof entry.value === "number" || entry.value == null
              ? formatChartValue(entry.value, unit)
              : entry.value}
          </span>
        </p>
      ))}
    </div>
  );
}
function ChartSegments<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="chart-segments" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
const axisStyle = { fontSize: 13, fill: "var(--text-secondary)" };
const grid = (
  <CartesianGrid
    stroke="var(--chart-grid)"
    vertical={false}
    strokeDasharray="3 5"
  />
);

export function ProductTrend({
  data,
  metric = "searches",
}: {
  data: TrendPoint[];
  metric?: "searches" | "completion_rate" | "applications";
}) {
  const [view, setView] = useState<"area" | "line">("area");
  const animate = useChartMotion();
  const gradientId = `product-trend-${useId().replaceAll(":", "")}`;
  const label =
    metric === "searches"
      ? "Search sessions"
      : metric === "applications"
        ? "Applications"
        : "Completion rate";
  const unit = metric === "completion_rate" ? "percent" : "number";
  const shared = {
    data,
    margin: { top: 13, right: 21, left: 1, bottom: 0 },
    accessibilityLayer: true,
  };
  const elements = (
    <>
      {grid}
      <XAxis
        dataKey="date"
        axisLine={false}
        tickLine={false}
        tick={axisStyle}
        tickFormatter={(value) => formatDate(String(value), true)}
        minTickGap={32}
        dy={8}
      />
      <YAxis
        axisLine={false}
        tickLine={false}
        tick={axisStyle}
        tickFormatter={(value: number) => axisValue(value, unit)}
        width={52}
        domain={[0, "auto"]}
      />
      <Tooltip
        content={<ChartTooltip unit={unit} />}
        cursor={{ stroke: "var(--line)" }}
      />
    </>
  );
  return (
    <div
      className="chart-content motion-chart"
      role="group"
      aria-label={`${label} over the selected period`}
    >
      <div className="chart-controls">
        <span className="chart-control-context">Daily values</span>
        <ChartSegments
          label="Product trend display"
          value={view}
          options={[
            { value: "area", label: "Area" },
            { value: "line", label: "Line" },
          ]}
          onChange={setView}
        />
      </div>
      <div
        className="chart-animated-plot"
        data-motion={animate ? "animated" : "reduced"}
      >
        <ResponsiveContainer width="100%" height={250} minWidth={0}>
          {view === "area" ? (
            <AreaChart {...shared}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor="var(--accent-bright)"
                    stopOpacity={0.28}
                  />
                  <stop
                    offset="100%"
                    stopColor="var(--accent-bright)"
                    stopOpacity={0.015}
                  />
                </linearGradient>
              </defs>
              {elements}
              <Area
                type="monotone"
                dataKey={metric}
                name={label}
                stroke="var(--accent-bright)"
                strokeWidth={2.7}
                fill={`url(#${gradientId})`}
                activeDot={{
                  r: 5,
                  stroke: "var(--surface-solid)",
                  strokeWidth: 2,
                }}
                isAnimationActive={animate}
                animationDuration={800}
                animationEasing="ease-out"
              />
            </AreaChart>
          ) : (
            <LineChart {...shared}>
              {elements}
              <Line
                type="monotone"
                dataKey={metric}
                name={label}
                stroke="var(--accent-bright)"
                strokeWidth={2.7}
                dot={data.length < 20 ? { r: 3, strokeWidth: 0 } : false}
                activeDot={{
                  r: 5,
                  stroke: "var(--surface-solid)",
                  strokeWidth: 2,
                }}
                isAnimationActive={animate}
                animationDuration={800}
                animationEasing="ease-out"
              />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function ExperimentBars({
  data,
}: {
  data: { label: string; conversion_rate: number | null }[];
}) {
  const [order, setOrder] = useState<"arm" | "rate">("arm");
  const animate = useChartMotion();
  const rows = useMemo(
    () =>
      order === "rate"
        ? [...data].sort(
            (left, right) =>
              (right.conversion_rate ?? -Infinity) -
              (left.conversion_rate ?? -Infinity),
          )
        : data,
    [data, order],
  );
  return (
    <div
      className="chart-content motion-chart"
      role="group"
      aria-label="Application conversion by experiment arm"
    >
      <div className="chart-controls">
        <span className="chart-control-context">Conversion (%)</span>
        <ChartSegments
          label="Experiment chart order"
          value={order}
          options={[
            { value: "arm", label: "Arm order" },
            { value: "rate", label: "Highest first" },
          ]}
          onChange={setOrder}
        />
      </div>
      <div
        className="chart-animated-plot"
        data-motion={animate ? "animated" : "reduced"}
      >
        <ResponsiveContainer width="100%" height={260} minWidth={0}>
          <BarChart
            data={rows}
            margin={{ top: 29, right: 17, left: 1, bottom: 0 }}
            accessibilityLayer
          >
            {grid}
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ ...axisStyle, fontSize: 12 }}
              tickFormatter={categoryLabel}
              minTickGap={12}
              dy={8}
              height={42}
            />
            <YAxis
              tick={axisStyle}
              axisLine={false}
              tickLine={false}
              tickFormatter={(value) => `${formatNumber(value, 1)}%`}
              width={52}
              domain={[0, "auto"]}
            />
            <Tooltip
              content={<ChartTooltip unit="percent" />}
              cursor={{ fill: "var(--accent-soft)", opacity: 0.5 }}
            />
            <Bar
              dataKey="conversion_rate"
              name="Conversion rate"
              radius={[8, 8, 0, 0]}
              maxBarSize={72}
              isAnimationActive={animate}
              animationDuration={850}
              animationEasing="ease-out"
            >
              {rows.map((row) => (
                <Cell
                  key={row.label}
                  fill={armColor(row.label, data.indexOf(row))}
                />
              ))}
              <LabelList
                dataKey="conversion_rate"
                position="top"
                offset={10}
                fill="var(--text)"
                fontSize={13}
                fontWeight={600}
                formatter={(value) =>
                  typeof value === "number"
                    ? formatChartValue(value, "percent")
                    : ""
                }
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-arm-key" aria-label="Experiment arm values">
        {data.map((row, index) => (
          <span key={row.label}>
            <i style={{ background: armColor(row.label, index) }} />
            {row.label.replace(/ recommendation$/i, "")}
            <strong>{formatChartValue(row.conversion_rate, "percent")}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

export function AnalystChart({
  chart,
}: {
  chart: NonNullable<AnalystAnswer["chart"]>;
}) {
  const [chosenView, setChosenView] = useState<"bar" | "line" | null>(null);
  const view = chosenView ?? chart.type;
  const animate = useChartMotion();
  const unit = metricUnit(chart.y_key);
  const label = chart.y_key.replaceAll("_", " ");
  const isDate = chart.x_key === "date";
  const shared = {
    data: chart.data,
    margin: { top: 25, right: 20, left: 1, bottom: 0 },
    accessibilityLayer: true,
  };
  const elements = (
    <>
      {grid}
      <XAxis
        dataKey={chart.x_key}
        tick={{ ...axisStyle, fontSize: 12 }}
        axisLine={false}
        tickLine={false}
        tickFormatter={(value) =>
          isDate ? formatDate(String(value), true) : categoryLabel(value)
        }
        minTickGap={24}
        dy={8}
        height={42}
      />
      <YAxis
        tick={axisStyle}
        axisLine={false}
        tickLine={false}
        width={58}
        domain={[0, "auto"]}
        tickFormatter={(value) => axisValue(value, unit)}
      />
      <Tooltip
        content={<ChartTooltip unit={unit} />}
        cursor={{
          stroke: "var(--line)",
          fill: "var(--accent-soft)",
          opacity: 0.6,
        }}
      />
    </>
  );
  return (
    <div
      className="chart-content analyst-chart motion-chart"
      role="group"
      aria-label={chart.title}
    >
      <div className="chart-controls">
        <span className="chart-control-context">
          {unit === "percent"
            ? "Values in %"
            : unit === "milliseconds"
              ? "Values in ms"
              : unit === "usd"
                ? "Values in USD"
                : "Measured values"}
        </span>
        <ChartSegments
          label="AI visualization display"
          value={view}
          options={[
            { value: "bar", label: "Bars" },
            { value: "line", label: "Line" },
          ]}
          onChange={setChosenView}
        />
      </div>
      <div
        className="chart-animated-plot"
        data-motion={animate ? "animated" : "reduced"}
      >
        <ResponsiveContainer width="100%" height={285} minWidth={0}>
          {view === "bar" ? (
            <BarChart {...shared}>
              {elements}
              <Bar
                dataKey={chart.y_key}
                name={label}
                fill="var(--accent-bright)"
                radius={[8, 8, 0, 0]}
                maxBarSize={72}
                isAnimationActive={animate}
                animationDuration={850}
                animationEasing="ease-out"
              >
                {chart.x_key === "variant" || chart.x_key === "arm"
                  ? chart.data.map((row, index) => (
                      <Cell
                        key={String(row[chart.x_key])}
                        fill={armColor(String(row[chart.x_key]), index)}
                      />
                    ))
                  : null}
                {chart.data.length <= 7 ? (
                  <LabelList
                    dataKey={chart.y_key}
                    position="top"
                    offset={10}
                    fill="var(--text)"
                    fontSize={13}
                    fontWeight={600}
                    formatter={(value) =>
                      typeof value === "number"
                        ? formatChartValue(value, unit)
                        : ""
                    }
                  />
                ) : null}
              </Bar>
            </BarChart>
          ) : (
            <LineChart {...shared}>
              {elements}
              <Line
                type={isDate ? "monotone" : "linear"}
                dataKey={chart.y_key}
                name={label}
                stroke="var(--accent-bright)"
                strokeWidth={2.7}
                dot={
                  chart.data.length <= 30 ? { r: 3.5, strokeWidth: 0 } : false
                }
                activeDot={{
                  r: 5,
                  stroke: "var(--surface-solid)",
                  strokeWidth: 2,
                }}
                connectNulls={false}
                isAnimationActive={animate}
                animationDuration={850}
                animationEasing="ease-out"
              />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
      {!isDate && view === "line" ? (
        <p className="chart-display-note">
          Categories follow the supplied order; the line connects comparison
          points.
        </p>
      ) : null}
    </div>
  );
}
