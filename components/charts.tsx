"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatDate, formatNumber } from "@/lib/api";
import type { AnalystAnswer, TrendPoint } from "@/lib/types";

type TooltipEntry = { color?: string; name?: string; value?: number | string };
function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <strong>
        {String(label).match(/^\d{4}-\d{2}-\d{2}/)
          ? formatDate(String(label))
          : label}
      </strong>
      {payload.map((entry) => (
        <p key={entry.name}>
          <span style={{ color: entry.color }}>{entry.name}</span>
          <span>
            {typeof entry.value === "number"
              ? formatNumber(entry.value, entry.name?.includes("rate") ? 2 : 0)
              : entry.value}
            {entry.name?.includes("rate") ? "%" : ""}
          </span>
        </p>
      ))}
    </div>
  );
}

const axisStyle = { fontSize: 11, fill: "var(--muted)" };

export function ProductTrend({
  data,
  metric = "searches",
}: {
  data: TrendPoint[];
  metric?: "searches" | "completion_rate" | "applications";
}) {
  const label =
    metric === "searches"
      ? "Search sessions"
      : metric === "applications"
        ? "Applications"
        : "Completion rate";
  return (
    <div
      className="chart-content"
      role="img"
      aria-label={`${label} over the selected period`}
    >
      <ResponsiveContainer width="100%" height={228}>
        <AreaChart
          data={data}
          margin={{ top: 5, right: 23, left: 5, bottom: 0 }}
          accessibilityLayer
        >
          <defs>
            <linearGradient id={`trend-${metric}`} x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="0%"
                stopColor="var(--accent-bright)"
                stopOpacity={0.2}
              />
              <stop
                offset="100%"
                stopColor="var(--accent-bright)"
                stopOpacity={0}
              />
            </linearGradient>
          </defs>
          <CartesianGrid
            stroke="var(--chart-grid)"
            vertical={false}
            strokeDasharray="3 4"
          />
          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={axisStyle}
            tickFormatter={(value) => formatDate(String(value), true)}
            minTickGap={35}
            dy={8}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={axisStyle}
            tickFormatter={(value: number) =>
              metric === "completion_rate"
                ? `${value}%`
                : value >= 1000
                  ? `${Math.round(value / 1000)}k`
                  : String(value)
            }
            width={43}
          />
          <Tooltip
            content={<ChartTooltip />}
            cursor={{ stroke: "var(--line)" }}
          />
          <Area
            type="monotone"
            dataKey={metric}
            name={label}
            stroke="var(--accent-bright)"
            strokeWidth={2.2}
            fill={`url(#trend-${metric})`}
            animationDuration={600}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ExperimentBars({
  data,
}: {
  data: { label: string; conversion_rate: number | null }[];
}) {
  return (
    <div
      className="chart-content"
      role="img"
      aria-label="Application conversion by experiment arm"
    >
      <ResponsiveContainer width="100%" height={230}>
        <BarChart
          data={data}
          margin={{ top: 5, right: 25, left: 5, bottom: 0 }}
          accessibilityLayer
        >
          <CartesianGrid
            stroke="var(--chart-grid)"
            vertical={false}
            strokeDasharray="3 4"
          />
          <XAxis
            dataKey="label"
            axisLine={false}
            tickLine={false}
            tick={{ ...axisStyle, fontSize: 10 }}
            tickFormatter={(label) => String(label)}
            dy={7}
          />
          <YAxis
            tick={axisStyle}
            axisLine={false}
            tickLine={false}
            tickFormatter={(value) => `${value}%`}
            width={43}
          />
          <Tooltip
            content={<ChartTooltip />}
            cursor={{ fill: "var(--accent-soft)", opacity: 0.4 }}
          />
          <Bar
            dataKey="conversion_rate"
            name="Conversion rate"
            fill="var(--accent-bright)"
            radius={[5, 5, 0, 0]}
            maxBarSize={66}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AnalystChart({
  chart,
}: {
  chart: NonNullable<AnalystAnswer["chart"]>;
}) {
  const shared = {
    data: chart.data,
    margin: { top: 7, right: 25, left: 3, bottom: 0 },
  };
  const elements = (
    <>
      <CartesianGrid
        stroke="var(--chart-grid)"
        vertical={false}
        strokeDasharray="3 4"
      />
      <XAxis
        dataKey={chart.x_key}
        tick={axisStyle}
        axisLine={false}
        tickLine={false}
        minTickGap={25}
        dy={8}
      />
      <YAxis tick={axisStyle} axisLine={false} tickLine={false} width={48} />
      <Tooltip content={<ChartTooltip />} />
    </>
  );
  return (
    <div
      className="chart-content analyst-chart"
      role="img"
      aria-label={chart.title}
    >
      <ResponsiveContainer width="100%" height={265}>
        {chart.type === "bar" ? (
          <BarChart {...shared} accessibilityLayer>
            {elements}
            <Bar
              dataKey={chart.y_key}
              name={chart.y_key.replaceAll("_", " ")}
              fill="var(--accent-bright)"
              radius={[5, 5, 0, 0]}
              maxBarSize={70}
            />
          </BarChart>
        ) : (
          <LineChart {...shared} accessibilityLayer>
            {elements}
            <Line
              type="monotone"
              dataKey={chart.y_key}
              name={chart.y_key.replaceAll("_", " ")}
              stroke="var(--accent-bright)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
